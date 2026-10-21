"""Immutable carousel facts, selections and acquired video collections."""

from dataclasses import dataclass, field
from enum import StrEnum

from social_video_downloader.domain.models import DownloadedMedia


class CarouselItemKind(StrEnum):
    VIDEO = "video"
    PHOTO = "photo"
    UNKNOWN = "unknown"


class CarouselScope(StrEnum):
    PUBLICATION = "publication"
    ITEM_REFERENCE = "item_reference"


class CarouselPlanState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class CarouselIssue(StrEnum):
    ITEM_REFERENCE_UNSUPPORTED = "item_reference_unsupported"
    AMBIGUOUS_REFERENCE = "ambiguous_reference"
    INVALID_METADATA = "invalid_metadata"
    UNSUPPORTED_CONTENT = "unsupported_content"
    UNSTABLE_IDENTITIES = "unstable_identities"
    UNKNOWN_ITEM = "unknown_item"
    UNSUPPORTED_VIDEO = "unsupported_video"
    NO_VIDEOS = "no_videos"


@dataclass(frozen=True, slots=True)
class CarouselItem:
    position: int
    item_id: str | None = field(repr=False)
    kind: CarouselItemKind
    evidence: tuple[str, ...]
    admissible_format_count: int


@dataclass(frozen=True, slots=True)
class CarouselParentIdentity:
    """Observed product PK and its verified shortcode; never a URL-derived identity."""

    pk: str = field(repr=False)
    shortcode: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CarouselInspection:
    publication_url: str = field(repr=False)
    total_entries: int | None
    items: tuple[CarouselItem, ...] = ()
    issue: CarouselIssue | None = None
    parent_identity: CarouselParentIdentity | None = field(default=None, repr=False, kw_only=True)


@dataclass(frozen=True, slots=True)
class CarouselSelectionPlan:
    """READY validates a selection, not acquisition, streams or Telegram delivery."""

    publication_url: str = field(repr=False)
    total_entries: int | None
    items: tuple[CarouselItem, ...]
    selected_videos: tuple[CarouselItem, ...]
    scope: CarouselScope
    state: CarouselPlanState
    issue: CarouselIssue | None = None
    parent_identity: CarouselParentIdentity | None = field(default=None, repr=False, kw_only=True)


@dataclass(frozen=True, slots=True)
class DownloadedCarouselVideo:
    position: int
    item_id: str = field(repr=False)
    media: DownloadedMedia = field(repr=False)


@dataclass(frozen=True, slots=True)
class DownloadedCarousel:
    """Caller owns all returned files until explicitly removed; no signed locators."""

    publication_url: str = field(repr=False)
    videos: tuple[DownloadedCarouselVideo, ...]
    total_bytes: int

    @property
    def file_count(self) -> int:
        return len(self.videos)
