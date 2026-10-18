"""Selection policy for Instagram carousels; no acquisition or Telegram calls."""

from urllib.parse import parse_qsl, urlsplit

from social_video_downloader.domain.carousel import (
    CarouselIssue,
    CarouselItemKind,
    CarouselPlanState,
    CarouselScope,
    CarouselSelectionPlan,
)
from social_video_downloader.domain.errors import InvalidMediaURLError
from social_video_downloader.domain.urls import normalize_media_url
from social_video_downloader.providers.instagram import InstagramProvider


class InstagramCarouselService:
    def __init__(self, provider: InstagramProvider) -> None:
        self._provider = provider

    def create_selection_plan(self, url: str) -> CarouselSelectionPlan:
        normalized = normalize_media_url(url)
        parts = urlsplit(normalized)
        if not parts.path.startswith("/p/"):
            raise InvalidMediaURLError("Carousel inspection requires an Instagram post URL.")
        canonical = self._provider._media_url(normalized)
        # Inspect intent before using a stripped canonical cache key. Unknown query
        # parameters/fragments are ambiguous, not permission to select all entries.
        try:
            query = parse_qsl(
                parts.query, keep_blank_values=True, strict_parsing=True, max_num_fields=32
            )
        except ValueError:
            query = [("ambiguous", "")]
        reference_keys = {"img_index", "media_id", "item_id", "carousel_index", "index", "slide"}
        issue = None
        if any(key.lower() in reference_keys for key, _ in query):
            issue = CarouselIssue.ITEM_REFERENCE_UNSUPPORTED
        elif urlsplit(url.strip()).fragment or any(
            key not in {"igsh", "igshid", "fbclid", "psln"} and not key.startswith("utm_")
            for key, _ in query
        ):
            issue = CarouselIssue.AMBIGUOUS_REFERENCE
        if issue is not None:
            return CarouselSelectionPlan(
                canonical,
                None,
                (),
                (),
                CarouselScope.ITEM_REFERENCE,
                CarouselPlanState.BLOCKED,
                issue,
            )
        inspection = self._provider.inspect_carousel(canonical)
        items = inspection.items
        issue = inspection.issue
        if issue is None:
            if any(item.kind is CarouselItemKind.UNKNOWN for item in items):
                issue = CarouselIssue.UNKNOWN_ITEM
            elif any(
                item.kind is CarouselItemKind.VIDEO and not item.admissible_format_count
                for item in items
            ):
                issue = CarouselIssue.UNSUPPORTED_VIDEO
            elif not any(item.kind is CarouselItemKind.VIDEO for item in items):
                issue = CarouselIssue.NO_VIDEOS
        selected = (
            tuple(item for item in items if item.kind is CarouselItemKind.VIDEO)
            if issue is None
            else ()
        )
        return CarouselSelectionPlan(
            canonical,
            inspection.total_entries,
            items,
            selected,
            CarouselScope.PUBLICATION,
            CarouselPlanState.READY if issue is None else CarouselPlanState.BLOCKED,
            issue,
        )
