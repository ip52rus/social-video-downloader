"""Instance-local adaptation of yt-dlp's Instagram product mapping.

Only this guarded boundary depends on the installed extractor's internal schema.
No HTTP interception, recursive result processing or persistent raw responses.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from yt_dlp.extractor.instagram import InstagramIE, _pk_to_id

from social_video_downloader.domain.carousel import CarouselItemKind
from social_video_downloader.domain.errors import MetadataExtractionError


@dataclass(frozen=True, slots=True)
class ItemEvidence:
    item_id: str | None
    mapped_id: str | None
    kind: CarouselItemKind
    signals: tuple[str, ...]
    unavailable: bool


def _identity(value):
    # Never synthesize IDs from positions, titles or temporary media locators.
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    text = str(value)
    return (
        text
        if (len(text) <= 64 and text.isascii() and text.isdecimal() and not text.startswith("0"))
        else None
    )


def _unavailable(item):
    return bool(
        item.get("is_private")
        or item.get("needs_auth")
        or item.get("has_drm")
        or item.get("availability") not in {None, "public"}
    )


def _has_images(item):
    images = item.get("image_versions2")
    candidates = images.get("candidates") if isinstance(images, Mapping) else None
    if not isinstance(candidates, list):
        return False
    for candidate in candidates:
        locator = candidate.get("url") if isinstance(candidate, Mapping) else None
        if not isinstance(locator, str):
            continue
        try:
            parts = urlsplit(locator)
            if parts.scheme in {"https", "http"} and parts.hostname:
                return True
        except ValueError:
            continue
    return False


def _classify(item):
    signals = []
    video = (
        item.get("is_video") is True
        or item.get("__typename") == "GraphVideo"
        or bool(item.get("video_versions"))
        or bool(item.get("video_dash_manifest"))
        or bool(item.get("video_codec"))
        or item.get("video_duration") is not None
    )
    photo_marker = item.get("is_video") is False or item.get("__typename") == "GraphImage"
    media_type = item.get("media_type")
    numeric_photo_marker = type(media_type) is int and media_type == 1
    if item.get("is_video") is True:
        signals.append("is_video_true")
    if item.get("__typename") == "GraphVideo":
        signals.append("graph_video")
    if item.get("video_versions"):
        signals.append("video_versions")
    if item.get("video_dash_manifest"):
        signals.append("video_manifest")
    if item.get("video_codec") or item.get("video_duration") is not None:
        signals.append("video_metadata")
    if photo_marker:
        signals.append("photo_marker")
    if _has_images(item):
        signals.append("image_versions")
    # Numeric markers need image corroboration and must never override video evidence.
    if (
        (media_type is not None and (type(media_type) is not int or media_type not in {1, 2}))
        or (video and (photo_marker or media_type == 1))
        or (photo_marker and media_type == 2)
        or (item.get("video_versions") is not None and not isinstance(item["video_versions"], list))
        or (item.get("is_video") is not None and type(item["is_video"]) is not bool)
        or any(
            item.get(key) is not None and not isinstance(item[key], str)
            for key in ("__typename", "video_codec", "video_dash_manifest")
        )
    ):
        return CarouselItemKind.UNKNOWN, (*signals, "conflicting_or_invalid_type")
    if video:
        return CarouselItemKind.VIDEO, tuple(signals)
    if (photo_marker or numeric_photo_marker) and _has_images(item):
        if numeric_photo_marker:
            signals.append("media_type_photo")
        return CarouselItemKind.PHOTO, tuple(signals)
    return CarouselItemKind.UNKNOWN, tuple(signals)


class CarouselInstagramIE(InstagramIE):
    """Register explicitly on one YoutubeDL instance, never globally."""

    @classmethod
    def ie_key(cls):
        return "Instagram"

    def _extract_product_media(self, product_media):
        item_id = _identity(product_media.get("pk"))
        # Reject malformed IDs before upstream base-N conversion (negative IDs
        # are not safe input to that helper). Keep identity unknown, never invent it.
        safe_media = (
            product_media
            if item_id is not None
            else {key: value for key, value in product_media.items() if key != "pk"}
        )
        result = super()._extract_product_media(safe_media)
        mapped_id = _pk_to_id(item_id) if item_id is not None else None
        kind, signals = _classify(product_media)
        result["_carousel_item_evidence"] = ItemEvidence(
            item_id, mapped_id, kind, signals, _unavailable(product_media)
        )
        return result

    def _extract_product(self, product_info, *args, **kwargs):
        # Only the exact known carousel list shape is trusted. Upstream filtering
        # of malformed members must not silently shorten our original publication.
        product = (
            product_info[0]
            if isinstance(product_info, list) and len(product_info) == 1
            else product_info
        )
        if not isinstance(product, Mapping):
            raise MetadataExtractionError("Unrecognized Instagram carousel metadata shape.")
        has_source = "carousel_media" in product
        source = product.get("carousel_media")
        # A guarded empty playlist is deliberately incomplete, so existing provider
        # facts report INVALID_METADATA without exposing or processing a partial set.
        invalid = {
            "_type": "playlist",
            "entries": [],
            "_carousel_source_count": len(source) if isinstance(source, list) else None,
        }
        if has_source and (
            not isinstance(source, list)
            or any(not isinstance(item, Mapping) or "carousel_media" in item for item in source)
        ):
            return invalid
        if _identity(product.get("pk")) is None:
            product_info = {key: value for key, value in product.items() if key != "pk"}
        if isinstance(source, list) and not source:
            return {
                "_type": "playlist",
                "entries": [],
                "_carousel_source_count": 0,
                "_carousel_unavailable": _unavailable(product),
            }
        result = super()._extract_product(product_info, *args, **kwargs)
        if _unavailable(product):
            result["_carousel_unavailable"] = True
        if has_source:
            entries = result.get("entries") if isinstance(result, Mapping) else None
            if not (
                isinstance(result, Mapping)
                and result.get("_type") == "playlist"
                and isinstance(entries, list)
                and len(entries) == len(source)
                and all(
                    isinstance(entry, Mapping)
                    and isinstance(evidence := entry.get("_carousel_item_evidence"), ItemEvidence)
                    and evidence.item_id == _identity(original.get("pk"))
                    and entry.get("id") == evidence.mapped_id
                    for original, entry in zip(source, entries, strict=True)
                )
            ):
                return invalid
            result["_carousel_source_count"] = len(source)
        return result
