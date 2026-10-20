"""Independent, offline-verified public-page prototype; no Telegram integration.

Only JSON schema facts are taken from source inspection; no upstream implementation
is copied. See docs/PHASE6E_TIKTOK_PUBLIC_PAGE.md. Live use requires separate approval
and an owned process supervisor, as with the native embed engine.
"""

import json
from html.parser import HTMLParser
from time import monotonic

from social_video_downloader.infrastructure import tiktok_native as native

STATE_ID = "__UNIVERSAL_DATA_FOR_REHYDRATION__"


def _publication(url):
    try:
        return native.publication(url)
    except (ValueError, TypeError):
        raise native.Refusal("invalid_input") from None


class _PageState(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = self.done = False
        self.parts = []
        self.inert = []

    def handle_starttag(self, tag, attrs):
        if tag in {"textarea", "template", "noscript", "title", "xmp", "iframe", "plaintext"}:
            self.inert.append(tag)
        if self.inert:
            return
        if any(key == "id" and value == STATE_ID for key, value in attrs):
            if (
                tag != "script"
                or self.active
                or self.done
                or len(dict(attrs)) != len(attrs)
                or dict(attrs).get("type") != "application/json"
            ):
                raise native.Refusal("ambiguous_metadata")
            self.active = True

    def handle_endtag(self, tag):
        if self.inert:
            if self.inert[-1] == "plaintext":
                return
            if tag == self.inert[-1]:
                self.inert.pop()
            return
        if tag == "script" and self.active:
            self.active, self.done = False, True

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def resolve_public_page(body: bytes, url: str) -> native.Resolved:
    """Resolve one already-received page; never executes JS or performs I/O."""
    post_id, _ = _publication(url)
    try:
        if not isinstance(body, bytes) or not 0 < len(body) <= native.HTML_BYTES:
            raise native.Refusal("metadata_body_limit")
        parser = _PageState()
        parser.feed(body.decode("utf-8"))
        parser.close()
        if not parser.done or parser.active:
            raise native.Refusal("missing_public_state")
        state = json.loads("".join(parser.parts), object_pairs_hook=native._unique)
        detail = state["__DEFAULT_SCOPE__"]["webapp.video-detail"]
        if (
            type(detail.get("statusCode", 0)) is not int
            or detail.get("statusCode", 0) != 0
            or detail.get("statusMsg") not in (None, "")
        ):
            raise native.Refusal("non_public_or_unavailable")
        item = detail["itemInfo"]["itemStruct"]
        identity = item.get("id")
        if type(identity) not in (str, int) or str(identity) != post_id:
            raise native.Refusal("source_identity_mismatch")
        if any(
            item.get(key) for key in ("privateItem", "isPrivate", "isDRM", "isContentClassified")
        ):
            raise native.Refusal("non_public_or_unavailable")
        video = item["video"]
        for obj in (item, video):
            for key in ("imagePost", "imagePostInfo"):
                photo = obj.get(key)
                if photo is None or (isinstance(photo, (dict, list)) and not photo):
                    continue
                images = photo.get("images") if isinstance(photo, dict) else None
                if (
                    isinstance(images, list)
                    and images
                    and all(isinstance(i, dict) and i for i in images)
                ):
                    raise native.Refusal("unsupported_photo")
                raise native.Refusal("metadata_schema")
        address = video["playAddr"]
        if isinstance(address, str):
            candidates = [address]
        elif isinstance(address, list) and 0 < len(address) <= 32:
            candidates = [entry["src"] for entry in address]
        else:
            raise native.Refusal("unsupported_page_video")
        if any(not isinstance(candidate, str) or not candidate for candidate in candidates):
            raise native.Refusal("metadata_schema")
        separate = any(
            obj.get(key) for obj in (item, video) for key in ("audio", "audioInfo", "audioAddr")
        )
        for candidate in dict.fromkeys(candidates):
            try:
                admitted = native.media_url(candidate)
            except native.Refusal:
                continue  # Offline admission only, not a request/fallback.
            return native.Resolved(admitted, len(set(candidates)), bool(separate), "playAddr")
        raise native.Refusal("forbidden_media_destination")
    except native.Refusal:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise native.Refusal("metadata_schema") from None


class _PublicPageSession(native.Session):
    def __init__(self, post_id, canonical, deadline, budget):
        super().__init__(post_id, canonical, min(deadline, monotonic() + native.SECONDS), budget)
        self.path = native._url(canonical).path

    def _admit(self, url, phase):
        if phase != "metadata":
            raise native.Refusal("metadata_only_prototype")
        super()._admit(url, phase)


def inspect_public_page(url: str, *, deadline: float, budget: dict) -> native.Resolved:
    """One bounded metadata resolution, no media GET or embed fallback.

    Caller owns the shared counters and must supervise the process for live use.
    Cookies and response objects remain local to this single operation.
    """
    post_id, canonical = _publication(url)
    session = _PublicPageSession(post_id, canonical, deadline, budget)
    try:
        return resolve_public_page(session.metadata(), canonical)
    finally:
        session.jar.clear()
