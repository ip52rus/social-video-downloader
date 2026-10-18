"""Metadata-only carousel fixtures through the installed Instagram extractor."""

from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest
import yt_dlp
from yt_dlp.extractor.instagram import InstagramIE

from social_video_downloader.domain.carousel import (
    CarouselIssue,
    CarouselItemKind,
    CarouselPlanState,
    CarouselScope,
)
from social_video_downloader.domain.errors import InvalidMediaURLError, MetadataExtractionError
from social_video_downloader.domain.models import MediaMetadata
from social_video_downloader.infrastructure.instagram_metadata import CarouselInstagramIE, _classify
from social_video_downloader.providers.instagram import InstagramProvider
from social_video_downloader.services.instagram_carousel import InstagramCarouselService

URL = "https://www.instagram.com/p/Fixture_Carousel/"
VIDEO = {
    "pk": 101,
    "media_type": 2,
    "video_versions": [{"url": "https://media.invalid/video.mp4", "width": 720, "height": 1280}],
}
PHOTO = {
    "pk": 102,
    "media_type": 1,
    "is_video": False,
    "image_versions2": {"candidates": [{"url": "https://media.invalid/photo.jpg"}]},
}
# Sanitized shape observed in the separate live metadata diagnostic. No source IDs,
# accounts, media URLs or raw response payloads are retained.
CORROBORATED_PHOTO = {
    "pk": 102,
    "media_type": 1,
    "__typename": "UnrecognizedFixtureType",
    "image_versions2": {"candidates": [{"url": "https://media.invalid/photo.jpg"}]},
}

INVALID_CAROUSEL_SOURCES = [
    pytest.param([None], id="null-entry"),
    pytest.param("invalid", id="string"),
    pytest.param({}, id="empty-object"),
    pytest.param({"invalid": "shape"}, id="object"),
    pytest.param([], id="empty-list"),
    pytest.param([VIDEO, None], id="invalid-last-entry"),
    pytest.param([None, VIDEO], id="invalid-first-entry"),
    pytest.param(None, id="present-null"),
    pytest.param([False], id="boolean-entry"),
    pytest.param(True, id="boolean"),
    pytest.param(1, id="number"),
    pytest.param([{**VIDEO, "carousel_media": [None]}], id="nested-collection"),
]

SOURCE_MUTATIONS = [
    "drop_unknown",
    "reverse",
    "identity",
    "promote_unknown",
    "photo_to_video",
    "video_signal",
    "image_signal",
    "is_private",
    "needs_auth",
    "has_drm",
    "availability",
]


def mutate_upstream_source(monkeypatch, change):
    """Fault injection before the installed mapper, not its observed behavior."""
    original = InstagramIE._extract_product
    items = [deepcopy(VIDEO), {**deepcopy(VIDEO), "pk": 103}]
    if change in {"drop_unknown", "promote_unknown"}:
        items[1] = {"pk": 103}
    elif change == "photo_to_video":
        items[1] = deepcopy(PHOTO)
    elif change in {"is_private", "needs_auth", "has_drm", "availability"}:
        items[1][change] = "needs_auth" if change == "availability" else True

    def changed(self, product, *args, **kwargs):
        source = product["carousel_media"]
        if change == "drop_unknown":
            source.pop()
        elif change == "reverse":
            source.reverse()
        elif change == "identity":
            source[1]["pk"] = 104
        elif change in {"promote_unknown", "photo_to_video"}:
            identity = source[1]["pk"]
            source[1].clear()
            source[1].update(deepcopy(VIDEO), pk=identity)
        elif change == "video_signal":
            source[1]["is_video"] = True
        elif change == "image_signal":
            source[1]["image_versions2"] = deepcopy(PHOTO["image_versions2"])
        else:
            source[1].pop(change)
        return original(self, product, *args, **kwargs)

    monkeypatch.setattr(InstagramIE, "_extract_product", changed)
    return items


def corrupt_upstream_collection(monkeypatch, change):
    original = InstagramIE._extract_product

    def changed(self, product, *args, **kwargs):
        result = original(self, product, *args, **kwargs)
        if change == "single":
            return self._extract_product_media(product)
        if change == "missing_entries":
            result.pop("entries")
        elif change == "dropped_entry":
            result["entries"].pop()
        else:
            assert change == "reordered"
            result["entries"].reverse()
        return result

    monkeypatch.setattr(InstagramIE, "_extract_product", changed)


class Runtime:
    def __init__(self, items):
        self.product = {"pk": 100, "carousel_media": deepcopy(items)}
        self.extractions = []
        self.options = []
        self.raw_override = None
        self.mutate = lambda raw: raw
        self.fail = False

    def factory(self, options):
        owner = self
        owner.options.append(options)

        class LocalYDL(yt_dlp.YoutubeDL):
            def __init__(self):
                super().__init__(options, auto_init=False)

            def add_info_extractor(self, ie):
                assert type(ie) is CarouselInstagramIE

                class FixtureIE(type(ie)):
                    def _real_initialize(self):
                        pass

                    @property
                    def _can_impersonate(self):
                        # Only selects the fixture JSON branch; never changes transport.
                        return True

                    def _download_json(self, url, *args, **kwargs):
                        if "/web/get_ruling_for_content/" in url:
                            return {"status": "ok"}
                        assert url == "https://www.instagram.com/api/graphql"
                        return {
                            "data": {
                                "xig_polaris_media": {
                                    "if_not_gated_logged_out": deepcopy(owner.product)
                                }
                            }
                        }

                    def _download_webpage_handle(self, *args, **kwargs):
                        raise AssertionError("No metadata network request allowed")

                super().add_info_extractor(FixtureIE(self))

            def extract_info(self, url, **kwargs):
                assert kwargs == {"download": False, "process": False, "ie_key": "Instagram"}
                owner.extractions.append(url)
                if owner.fail:
                    raise RuntimeError("synthetic upstream failure")
                if owner.raw_override is not None:
                    return deepcopy(owner.raw_override)
                return owner.mutate(super().extract_info(url, **kwargs))

            def process_ie_result(self, *args, **kwargs):
                raise AssertionError("No playlist processing allowed")

            def process_info(self, *args, **kwargs):
                raise AssertionError("No media acquisition allowed")

            def urlopen(self, *args, **kwargs):
                raise AssertionError("No network or image access allowed")

        return LocalYDL()

    def service(self):
        self.provider = InstagramProvider(self.factory)
        return InstagramCarouselService(self.provider)


def assert_blocked(plan, reason):
    assert plan.state is CarouselPlanState.BLOCKED
    assert plan.issue is reason
    assert plan.selected_videos == ()


@pytest.mark.parametrize("count", [1, 2, 5, 10, 11, 21])
def test_all_video_carousel_preserves_every_position_and_id(count):
    runtime = Runtime([{**VIDEO, "pk": 101 + i} for i in range(count)])
    plan = runtime.service().create_selection_plan(URL)
    assert plan.state is CarouselPlanState.READY
    assert plan.issue is None
    assert plan.scope is CarouselScope.PUBLICATION
    assert plan.total_entries == count
    assert plan.selected_videos == plan.items
    assert [x.position for x in plan.items] == list(range(1, count + 1))
    assert [x.item_id for x in plan.items] == [str(101 + i) for i in range(count)]
    assert all(
        x.kind is CarouselItemKind.VIDEO and x.admissible_format_count == 1 for x in plan.items
    )
    assert runtime.extractions == [URL]
    assert runtime.options[0]["skip_download"] is True
    assert runtime.options[0]["getcomments"] is False
    assert runtime.options[0]["noplaylist"] is True
    assert all(
        runtime.options[0][k] == 0 for k in ("retries", "extractor_retries", "fragment_retries")
    )
    with pytest.raises(FrozenInstanceError):
        plan.state = CarouselPlanState.BLOCKED
    with pytest.raises(FrozenInstanceError):
        plan.items[0].position = 99
    assert isinstance(plan.items, tuple) and isinstance(plan.items[0].evidence, tuple)
    assert "url" not in vars(type(plan.items[0]))


def test_mixed_carousel_omits_only_confirmed_photos_and_retains_gaps():
    runtime = Runtime([PHOTO, VIDEO, {**PHOTO, "pk": 103}, {**VIDEO, "pk": 104}])
    plan = runtime.service().create_selection_plan(URL)
    assert plan.state is CarouselPlanState.READY
    assert [x.kind for x in plan.items] == [CarouselItemKind.PHOTO, CarouselItemKind.VIDEO] * 2
    assert [x.position for x in plan.selected_videos] == [2, 4]
    assert [x.item_id for x in plan.selected_videos] == ["101", "104"]


@pytest.mark.parametrize("items", [[], [PHOTO], [PHOTO, {**PHOTO, "pk": 103}]])
def test_no_videos_has_clear_non_downloadable_result(items):
    plan = Runtime(items).service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.NO_VIDEOS)
    assert plan.total_entries == len(items)
    assert len(plan.items) == len(items)


@pytest.mark.parametrize(
    "item",
    [
        {"pk": 102},
        {"pk": 102, "media_type": 1},
        {"pk": 102, "media_type": 2},
        {"pk": 102, "formats": []},
        {"pk": 102, "thumbnails": [{"url": "https://media.invalid/photo.jpg"}]},
        {k: v for k, v in PHOTO.items() if k not in {"is_video", "media_type"}},
        {**PHOTO, "image_versions2": {}},
        {**PHOTO, "video_versions": VIDEO["video_versions"]},
        {**PHOTO, "video_codec": "h264"},
        {**VIDEO, "media_type": 1},
        {**VIDEO, "media_type": 999},
        {**VIDEO, "is_video": "true"},
        {**VIDEO, "video_versions": {"url": "https://media.invalid/video.mp4"}},
    ],
)
def test_unknown_or_conflicting_item_blocks_whole_plan(item):
    item = {**item, "pk": 102}
    plan = Runtime([VIDEO, item]).service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.UNKNOWN_ITEM)
    assert len(plan.items) == 2
    assert plan.items[1].kind is CarouselItemKind.UNKNOWN


@pytest.mark.parametrize(
    "item",
    [
        {"pk": 102, "is_video": True, "media_type": 2},
        {"pk": 102, "is_video": True, "video_versions": [{"width": 720}]},
        {
            **VIDEO,
            "has_audio": False,
            "video_versions": [{"url": "https://media.invalid/video.m3u8"}],
        },
        {**VIDEO, "video_codec": "none"},
        {**VIDEO, "video_versions": [{"url": "https://media.invalid/video.webm"}]},
        {**VIDEO, "video_versions": [{"url": "https://media.invalid/video.m3u8"}]},
        {**VIDEO, "video_versions": [{"url": "https://media.invalid/video.mpd"}]},
    ],
)
def test_unsupported_video_is_not_reclassified_or_omitted(item):
    plan = Runtime([VIDEO, {**item, "pk": 102}]).service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.UNSUPPORTED_VIDEO)
    assert plan.items[1].kind is CarouselItemKind.VIDEO


@pytest.mark.parametrize(
    "pk", [None, "", "non-numeric", True, -1, "101_ambiguous", "0101", "9" * 65]
)
def test_missing_or_unstable_identity_is_not_synthesized(pk):
    item = {**VIDEO, "pk": pk}
    plan = Runtime([item]).service().create_selection_plan(URL)
    assert plan.state is CarouselPlanState.BLOCKED
    assert plan.selected_videos == ()
    assert plan.items[0].item_id is None


def test_duplicate_ids_remain_visible_but_block_selection():
    plan = Runtime([VIDEO, VIDEO]).service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.UNSTABLE_IDENTITIES)
    assert len(plan.items) == 2
    assert [x.position for x in plan.items] == [1, 2]


@pytest.mark.parametrize("bad", [None, "invalid", 3, []])
def test_malformed_original_entries_cannot_be_silently_filtered(bad):
    plan = Runtime([VIDEO, bad]).service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.INVALID_METADATA)


@pytest.mark.parametrize("source", INVALID_CAROUSEL_SOURCES)
def test_present_source_collection_cannot_become_a_single_video(source):
    runtime = Runtime([])
    # Parent video locators deliberately make upstream's single fallback admissible.
    runtime.product = {**VIDEO, "carousel_media": deepcopy(source)}
    service = runtime.service()
    result = service.inspect_publication(URL)
    assert not isinstance(result, MediaMetadata)
    issue = CarouselIssue.NO_VIDEOS if source == [] else CarouselIssue.INVALID_METADATA
    assert_blocked(result, issue)
    assert result.total_entries == (len(source) if isinstance(source, list) else None)
    assert runtime.extractions == [URL]
    assert runtime.provider._inspection_cache == {}


@pytest.mark.parametrize("source", [[None], "invalid", {}, [VIDEO, None]])
def test_installed_upstream_mapping_loses_invalid_source_shape(source):
    # Exercise the installed mapper directly, without our adapter or network access.
    with yt_dlp.YoutubeDL({"quiet": True}, auto_init=False) as ydl:
        result = InstagramIE(ydl)._extract_product(
            {**VIDEO, "carousel_media": deepcopy(source)}, get_comments=False
        )
    assert "carousel_media" not in result
    if source == [VIDEO, None]:
        assert result["_type"] == "playlist" and len(result["entries"]) == 1
    else:
        assert result.get("_type", "video") == "video"
        assert any(InstagramProvider._usable_format(f) for f in result["formats"])


@pytest.mark.parametrize("change", ["single", "missing_entries", "dropped_entry", "reordered"])
@pytest.mark.parametrize("entry_point", ["create_selection_plan", "inspect_publication"])
def test_source_collection_must_survive_mapping_completely(monkeypatch, change, entry_point):
    corrupt_upstream_collection(monkeypatch, change)
    runtime = Runtime([VIDEO, {**VIDEO, "pk": 103}])
    runtime.product.update(VIDEO)
    service = runtime.service()
    result = getattr(service, entry_point)(URL)
    assert not isinstance(result, MediaMetadata)
    assert_blocked(result, CarouselIssue.INVALID_METADATA)
    assert result.total_entries == 2
    assert runtime.extractions == [URL] and runtime.provider._inspection_cache == {}


@pytest.mark.parametrize("change", SOURCE_MUTATIONS)
@pytest.mark.parametrize("entry_point", ["create_selection_plan", "inspect_publication"])
def test_mapping_compares_against_initial_immutable_source_facts(monkeypatch, change, entry_point):
    runtime = Runtime(mutate_upstream_source(monkeypatch, change))
    service = runtime.service()
    result = getattr(service, entry_point)(URL)
    assert not isinstance(result, MediaMetadata)
    assert_blocked(result, CarouselIssue.INVALID_METADATA)
    # In particular, dropping UNKNOWN must not rewrite the original count to one.
    assert result.total_entries == 2
    assert runtime.extractions == [URL] and runtime.provider._inspection_cache == {}


@pytest.mark.parametrize(
    "items,selected", [([VIDEO, {**VIDEO, "pk": 103}], [1, 2]), ([VIDEO, PHOTO], [1])]
)
def test_unmodified_real_mapper_preserves_initial_facts(monkeypatch, items, selected):
    original = InstagramIE._extract_product
    calls = []

    def unchanged(self, product, *args, **kwargs):
        before = deepcopy(product)
        result = original(self, product, *args, **kwargs)
        assert product == before
        calls.append(True)
        return result

    monkeypatch.setattr(InstagramIE, "_extract_product", unchanged)
    runtime = Runtime(items)
    plan = runtime.service().inspect_publication(URL)
    assert plan.state is CarouselPlanState.READY and plan.issue is None
    assert [item.item_id for item in plan.items] == [str(item["pk"]) for item in items]
    assert [item.position for item in plan.items] == [1, 2]
    assert [item.position for item in plan.selected_videos] == selected
    assert calls == [True] and runtime.extractions == [URL]


@pytest.mark.parametrize(
    "query",
    [
        "?img_index=3",
        "?img_index=0",
        "?img_index=-1",
        "?img_index=bad",
        "?img_index=",
        "?img_index=1&img_index=2",
        "?%69mg_index=3",
        "?media_id=3",
        "?item_id=3",
        "?index=3",
        "?carousel_index=3",
        "?slide=3",
    ],
)
def test_item_reference_intent_is_rejected_before_extraction_and_cache(query):
    runtime = Runtime([VIDEO])
    service = runtime.service()
    service.create_selection_plan(URL)
    plan = service.create_selection_plan(URL + query)
    assert_blocked(plan, CarouselIssue.ITEM_REFERENCE_UNSUPPORTED)
    assert plan.scope is CarouselScope.ITEM_REFERENCE
    assert plan.total_entries is None
    assert runtime.extractions == [URL]


@pytest.mark.parametrize(
    "suffix",
    ["?unknown=3", "?video_id=3", "?img_index", "?=3", "?igsh=x&item=3", "#3", "?bad%XX=3"],
)
def test_ambiguous_reference_never_becomes_full_publication(suffix):
    runtime = Runtime([VIDEO])
    plan = runtime.service().create_selection_plan(URL + suffix)
    assert_blocked(plan, CarouselIssue.AMBIGUOUS_REFERENCE)
    assert runtime.extractions == []


def test_tracking_variants_share_cached_immutable_facts(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("social_video_downloader.providers.instagram.monotonic", lambda: clock[0])
    runtime = Runtime([VIDEO])
    service = runtime.service()
    first = service.create_selection_plan(URL + "?igsh=fixture&utm_source=fixture&psln=fixture")
    assert service.create_selection_plan("http://m.instagram.com/p/Fixture_Carousel") == first
    assert len(runtime.extractions) == 1
    clock[0] = 180.0
    assert service.create_selection_plan(URL) == first
    assert len(runtime.extractions) == 2


def test_cache_is_bounded_and_distinct_publications_do_not_collide(monkeypatch):
    monkeypatch.setattr(InstagramProvider, "_INSPECTION_CACHE_MAX_ENTRIES", 2)
    runtime = Runtime([VIDEO])
    service = runtime.service()
    for name in ("One", "Two", "Three", "One"):
        service.create_selection_plan(f"https://www.instagram.com/p/{name}/")
    assert len(runtime.extractions) == 4
    assert len(runtime.provider._carousel_cache) == 2


@pytest.mark.parametrize(
    "url",
    [
        "https://instagram.com.evil.invalid/p/F/",
        "https://evil.instagram.com/p/F/",
        "https://user:pass@instagram.com/p/F/",
        "https://instagram.com:81/p/F/",
        "https://instagram.com/p/F/extra/",
        "https://instagram.com/reel/F/",
        "https://instagram.com/p/%2e%2e/",
        "file:///p/F/",
    ],
)
def test_url_safety_precedes_metadata(url):
    runtime = Runtime([VIDEO])
    with pytest.raises(InvalidMediaURLError):
        runtime.service().create_selection_plan(url)
    assert runtime.extractions == []


@pytest.mark.parametrize(
    "raw",
    [
        {"_type": "url", "url": "https://media.invalid/video.mp4"},
        {"_type": "playlist", "entries": []},
        {"_type": "playlist", "entries": iter(())},
        {"_type": "playlist", "entries": [], "_carousel_source_count": 1},
        {
            "_type": "playlist",
            "entries": [{"id": "fake", "formats": []}],
            "_carousel_source_count": 1,
        },
        {
            "_type": "playlist",
            "entries": [],
            "_carousel_source_count": 0,
            "availability": "private",
        },
        {"_type": "playlist", "entries": [], "_carousel_source_count": 0, "has_drm": True},
    ],
)
def test_untrusted_mapping_redirects_and_private_results_block(raw):
    runtime = Runtime([VIDEO])
    runtime.raw_override = raw
    plan = runtime.service().create_selection_plan(URL)
    assert plan.state is CarouselPlanState.BLOCKED
    assert plan.selected_videos == ()


@pytest.mark.parametrize("mutation", ["id", "redirect", "entries", "private", "drm"])
def test_changed_or_unavailable_mapped_video_blocks(mutation):
    runtime = Runtime([VIDEO])

    def change(raw):
        raw["entries"][0].update(
            {
                "id": {"id": "changed"},
                "redirect": {"_type": "url"},
                "entries": {"entries": []},
                "private": {"availability": "private"},
                "drm": {"has_drm": True},
            }[mutation]
        )
        return raw

    runtime.mutate = change
    plan = runtime.service().create_selection_plan(URL)
    assert plan.state is CarouselPlanState.BLOCKED
    assert len(plan.items) == 1
    assert plan.selected_videos == ()


def test_upstream_failure_is_safe_and_not_cached_or_retried():
    runtime = Runtime([VIDEO])
    runtime.fail = True
    service = runtime.service()
    with pytest.raises(MetadataExtractionError, match="Unable to inspect the Instagram carousel"):
        service.create_selection_plan(URL)
    assert runtime.extractions == [URL]
    assert runtime.provider._carousel_cache == {}


def test_no_global_extractor_override_or_mutation_of_single_video_cache():
    original = InstagramIE._extract_product_media
    runtime = Runtime([VIDEO])
    runtime.service().create_selection_plan(URL)
    assert InstagramIE._extract_product_media is original
    assert runtime.provider._inspection_cache == {}
    with pytest.raises(InvalidMediaURLError):
        runtime.provider.inspect_carousel(URL + "?img_index=3")


@pytest.mark.parametrize(
    "flag",
    [{"is_private": True}, {"needs_auth": True}, {"has_drm": True}, {"availability": "private"}],
)
@pytest.mark.parametrize("location", ["root", "item"])
def test_source_unavailability_is_not_lost_in_upstream_mapping(flag, location):
    runtime = Runtime([VIDEO])
    if location == "root":
        runtime.product.update(flag)
    else:
        runtime.product["carousel_media"][0].update(flag)
    plan = runtime.service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.UNSUPPORTED_CONTENT)


def test_upstream_reordering_fails_shape_guard(monkeypatch):
    original = InstagramIE._extract_product

    def reordered(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        result["entries"].reverse()
        return result

    monkeypatch.setattr(InstagramIE, "_extract_product", reordered)
    plan = Runtime([VIDEO, PHOTO]).service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.INVALID_METADATA)


@pytest.mark.parametrize(
    "item",
    [
        {**PHOTO, "is_video": None, "__typename": "GraphImage"},
        {**VIDEO, "media_type": None, "is_video": True, "video_versions": []},
        {**VIDEO, "media_type": None, "__typename": "GraphVideo", "video_versions": []},
        {**VIDEO, "video_codec": "h264", "has_audio": True},
        {**VIDEO, "video_versions": [{"url": "https://media.invalid/video.mp4?signature=fixture"}]},
    ],
)
def test_explicit_markers_and_incomplete_metadata_remain_distinct(item):
    plan = Runtime([item]).service().create_selection_plan(URL)
    if item.get("__typename") == "GraphImage":
        assert_blocked(plan, CarouselIssue.NO_VIDEOS)
        assert plan.items[0].kind is CarouselItemKind.PHOTO
    elif not item.get("video_versions"):
        assert_blocked(plan, CarouselIssue.UNSUPPORTED_VIDEO)
        assert plan.items[0].kind is CarouselItemKind.VIDEO
    else:
        assert plan.state is CarouselPlanState.READY


@pytest.mark.parametrize("root_id", [-1, None, "invalid"])
def test_invalid_root_id_cannot_enter_unsafe_upstream_conversion(root_id):
    runtime = Runtime([VIDEO])
    runtime.product["pk"] = root_id
    # The publication identity is the validated URL; child identities remain valid.
    assert runtime.service().create_selection_plan(URL).state is CarouselPlanState.READY


@pytest.mark.parametrize(
    "item",
    [CORROBORATED_PHOTO, {k: v for k, v in PHOTO.items() if k != "is_video"}],
)
def test_numeric_photo_marker_needs_image_corroboration_and_reports_evidence(item):
    plan = Runtime([item]).service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.NO_VIDEOS)
    assert plan.items[0].kind is CarouselItemKind.PHOTO
    assert "media_type_photo" in plan.items[0].evidence
    assert "image_versions" in plan.items[0].evidence


def test_observed_twenty_item_shape_selects_only_seventeen_videos():
    photo_positions = {8, 9, 18}
    items = []
    for position in range(1, 21):
        item = (
            CORROBORATED_PHOTO
            if position in photo_positions
            else {
                **VIDEO,
                "has_audio": True,
                "image_versions2": PHOTO["image_versions2"],
                "video_versions": [
                    {"url": f"https://media.invalid/video-{height}.mp4", "height": height}
                    for height in (640, 1280, 1920)
                ],
            }
        )
        items.append({**deepcopy(item), "pk": 100 + position})
    runtime = Runtime(items)
    plan = runtime.service().create_selection_plan(URL)
    expected_positions = [i for i in range(1, 21) if i not in photo_positions]
    assert plan.state is CarouselPlanState.READY and plan.issue is None
    assert plan.total_entries == len(plan.items) == 20
    assert [x.position for x in plan.items] == list(range(1, 21))
    assert [x.item_id for x in plan.items] == [str(100 + i) for i in range(1, 21)]
    assert [x.position for x in plan.items if x.kind is CarouselItemKind.PHOTO] == [8, 9, 18]
    assert not any(x.kind is CarouselItemKind.UNKNOWN for x in plan.items)
    assert len(plan.selected_videos) == 17
    assert [x.position for x in plan.selected_videos] == expected_positions
    assert [x.item_id for x in plan.selected_videos] == [str(100 + i) for i in expected_positions]
    assert all(
        x.kind is CarouselItemKind.VIDEO and x.admissible_format_count == 3
        for x in plan.selected_videos
    )
    # Runtime forbids network, result processing and acquisition for the entire flow.
    assert runtime.extractions == [URL]


@pytest.mark.parametrize(
    "images",
    [
        None,
        {},
        [],
        {"candidates": None},
        {"candidates": []},
        {"candidates": {}},
        {"candidates": [None, {}, {"url": None}]},
        {"candidates": [{"url": "javascript:invalid"}]},
        {"candidates": [{"url": "https:///missing-host.jpg"}]},
        {"candidates": [{"url": "https://[malformed/image.jpg"}]},
        {"candidates": [{"url": "ftp://media.invalid/photo.jpg"}]},
    ],
)
def test_numeric_photo_with_invalid_image_structure_remains_unknown(images):
    item = {**CORROBORATED_PHOTO, "image_versions2": images}
    kind, signals = _classify(item)
    assert kind is CarouselItemKind.UNKNOWN
    assert "media_type_photo" not in signals
    plan = Runtime([item]).service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.UNKNOWN_ITEM)


@pytest.mark.parametrize("marker", [True, False, "1", 1.0, 0, 3, -1, [], {}])
def test_malformed_numeric_photo_marker_never_selects_photo(marker):
    kind, signals = _classify({**CORROBORATED_PHOTO, "media_type": marker})
    assert kind is CarouselItemKind.UNKNOWN
    assert "media_type_photo" not in signals


@pytest.mark.parametrize(
    "video_fields",
    [
        {"video_versions": [{"url": "https://media.invalid/video.mp4"}]},
        {"video_versions": [{"width": 720}]},
        {"video_codec": "h264"},
        {"video_codec": "none"},
        {"video_duration": 0},
        {"video_duration": 12},
        {"video_dash_manifest": "nonempty fixture manifest"},
        {"is_video": True},
        {"__typename": "GraphVideo"},
        {"video_versions": {}},
        {"is_video": "false"},
        {"__typename": []},
        {"video_codec": False},
        {"video_dash_manifest": {}},
    ],
)
def test_numeric_photo_with_video_or_malformed_type_evidence_remains_unknown(video_fields):
    # Direct classifier test keeps malformed manifests away from the XML parser;
    # the existing integration cases separately prove unsupported VIDEO blocks.
    kind, signals = _classify({**CORROBORATED_PHOTO, **video_fields})
    assert kind is CarouselItemKind.UNKNOWN
    assert "media_type_photo" not in signals


@pytest.mark.parametrize("photo_fields", [{"is_video": False}, {"__typename": "GraphImage"}])
def test_explicit_photo_markers_work_without_numeric_marker(photo_fields):
    item = {key: value for key, value in PHOTO.items() if key not in {"media_type", "is_video"}}
    plan = Runtime([{**item, **photo_fields}]).service().create_selection_plan(URL)
    assert_blocked(plan, CarouselIssue.NO_VIDEOS)
    assert plan.items[0].kind is CarouselItemKind.PHOTO
    assert "photo_marker" in plan.items[0].evidence
    assert "media_type_photo" not in plan.items[0].evidence


def test_explicitly_silent_videos_are_ready_without_acquisition():
    items = [
        {
            **VIDEO,
            "pk": 101 + i,
            "has_audio": False,
            "video_versions": [
                {"url": "https://media.invalid/silent.mp4?signature=fixture"} for _ in range(3)
            ],
        }
        for i in range(3)
    ]
    runtime = Runtime(items)
    plan = runtime.service().create_selection_plan(URL)
    assert plan.state is CarouselPlanState.READY and plan.issue is None
    assert plan.total_entries == 3
    assert [x.position for x in plan.selected_videos] == [1, 2, 3]
    assert all(
        x.kind is CarouselItemKind.VIDEO and x.admissible_format_count == 3 for x in plan.items
    )
    assert len(runtime.extractions) == 1
