"""Selection policy for Instagram carousels; no acquisition or Telegram calls."""

from dataclasses import replace
from urllib.parse import urlsplit

from social_video_downloader.domain.carousel import (
    CarouselInspection,
    CarouselIssue,
    CarouselItemKind,
    CarouselPlanState,
    CarouselScope,
    CarouselSelectionPlan,
)
from social_video_downloader.domain.errors import InvalidMediaURLError
from social_video_downloader.domain.models import MediaMetadata
from social_video_downloader.domain.urls import (
    has_instagram_item_reference,
    instagram_item_position,
    normalize_media_url,
)
from social_video_downloader.infrastructure.instagram_metadata import parent_identity_matches
from social_video_downloader.providers.instagram import InstagramProvider


class InstagramCarouselService:
    def __init__(self, provider: InstagramProvider) -> None:
        self._provider = provider

    def create_selection_plan(self, url: str) -> CarouselSelectionPlan:
        canonical, blocked = self._publication_url(url)
        return blocked or self._selection_plan(self._provider.inspect_carousel(canonical))

    def inspect_item_reference(self, url: str) -> CarouselSelectionPlan:
        if instagram_item_position(url) is None:
            raise InvalidMediaURLError("An explicit Instagram position is required.")
        canonical = self._provider._media_url(url)
        return self._selection_plan(self._provider.inspect_carousel(canonical))

    @staticmethod
    def select_video(plan: CarouselSelectionPlan, position: int) -> CarouselSelectionPlan:
        from social_video_downloader.services.instagram_acquisition import (
            CarouselAcquisitionLimits,
            validate_plan,
        )

        validate_plan(plan, CarouselAcquisitionLimits())
        if type(position) is not int or not 1 <= position <= len(plan.items):
            raise InvalidMediaURLError("Instagram position is out of range.")
        item = plan.items[position - 1]
        if item.kind is not CarouselItemKind.VIDEO or item.admissible_format_count <= 0:
            raise InvalidMediaURLError("The selected position is not an available video.")
        selected = replace(
            plan,
            scope=CarouselScope.SINGLE_VIDEO,
            requested_position=position,
            selected_videos=(item,),
        )
        validate_plan(selected, CarouselAcquisitionLimits())
        return selected

    def inspect_publication(self, url: str) -> MediaMetadata | CarouselSelectionPlan:
        """Share the URL/type policy; only positive single-video evidence returns metadata."""
        canonical, blocked = self._publication_url(url)
        if blocked is not None:
            return blocked
        inspection = self._provider.inspect_post(canonical)
        if isinstance(inspection, MediaMetadata):
            return inspection
        return self._selection_plan(inspection)

    def _publication_url(self, url: str) -> tuple[str, CarouselSelectionPlan | None]:
        normalized = normalize_media_url(url)
        parts = urlsplit(normalized)
        if not parts.path.startswith("/p/"):
            raise InvalidMediaURLError("Carousel inspection requires an Instagram post URL.")
        canonical = self._provider._media_url(normalized)
        # Share the Reel reference policy before using a stripped canonical cache key.
        try:
            issue = (
                CarouselIssue.ITEM_REFERENCE_UNSUPPORTED
                if has_instagram_item_reference(url)
                else None
            )
        except InvalidMediaURLError:
            issue = CarouselIssue.AMBIGUOUS_REFERENCE
        if issue is not None:
            return canonical, CarouselSelectionPlan(
                canonical,
                None,
                (),
                (),
                CarouselScope.ITEM_REFERENCE,
                CarouselPlanState.BLOCKED,
                issue,
            )
        return canonical, None

    @staticmethod
    def _selection_plan(inspection: CarouselInspection) -> CarouselSelectionPlan:
        items = inspection.items
        issue = inspection.issue
        if issue is None and not parent_identity_matches(
            inspection.parent_identity, inspection.publication_url
        ):
            issue = CarouselIssue.UNSTABLE_IDENTITIES
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
            inspection.publication_url,
            inspection.total_entries,
            items,
            selected,
            CarouselScope.PUBLICATION,
            CarouselPlanState.READY if issue is None else CarouselPlanState.BLOCKED,
            issue,
            parent_identity=inspection.parent_identity,
        )
