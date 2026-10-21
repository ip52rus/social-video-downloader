"""Observed parent identity, private IPC and pre-media fail-closed regression."""

import json
import logging
import socket
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest
from yt_dlp.extractor.instagram import InstagramIE

from social_video_downloader.domain.carousel import (
    CarouselIssue,
    CarouselParentIdentity,
    CarouselPlanState,
)
from social_video_downloader.domain.errors import DownloadFailedError
from social_video_downloader.infrastructure.instagram_acquisition import _same_selection
from social_video_downloader.operation_logging import LOGGER_NAME, Operation
from social_video_downloader.services.instagram_acquisition import (
    CarouselAcquisitionLimits,
    InstagramCarouselAcquisition,
    plan_from_payload,
    plan_payload,
    validate_plan,
)
from tests import test_instagram_acquisition as acquisition_fixtures
from tests.test_instagram_acquisition import (
    Runtime as AcquisitionRuntime,
)
from tests.test_instagram_acquisition import (
    acquire,
    install_child,
    product,
    subprocess_script,
)
from tests.test_instagram_carousel import PHOTO, URL, VIDEO, Runtime

media_files = acquisition_fixtures.media_files

PK = 6862381134413977756083341221


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("External network forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


@pytest.mark.parametrize("branch", ["graphql", "webpage"])
@pytest.mark.parametrize("pk", [PK, str(PK)])
@pytest.mark.parametrize("code", [None, "Fixture_Carousel"])
def test_received_parent_survives_installed_extractor_and_contract(branch, pk, code):
    runtime = Runtime([VIDEO, PHOTO, {**VIDEO, "pk": 103}], branch=branch)
    runtime.product["pk"] = pk
    if code is not None:
        runtime.product["code"] = code
    plan = runtime.service().create_selection_plan(URL + "?utm_source=fixture&psln=x&rpxt=x")
    assert plan.state is CarouselPlanState.READY
    assert plan.parent_identity == CarouselParentIdentity(str(PK), "Fixture_Carousel")
    assert [x.position for x in plan.selected_videos] == [1, 3]
    assert plan_from_payload(json.loads(json.dumps(plan_payload(plan)))) == plan
    assert runtime.extractions == [URL]
    with pytest.raises(FrozenInstanceError):
        plan.parent_identity.pk = "changed"


@pytest.mark.parametrize("branch", ["graphql", "webpage"])
@pytest.mark.parametrize(
    "bad",
    [
        None,
        0,
        -1,
        True,
        False,
        1.5,
        [],
        {},
        "",
        "invalid",
        "01",
        " 1",
        "+1",
        "1_2",
        "١",
        "1" * 65,
        "1" * 64,
        PK + 1,
    ],
)
def test_bad_received_parent_never_reaches_upstream_mapping(monkeypatch, branch, bad):
    runtime = Runtime([VIDEO, {**VIDEO, "pk": 103}], branch=branch)
    runtime.product["pk"] = bad
    calls = []
    original = InstagramIE._extract_product

    def mapped(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(InstagramIE, "_extract_product", mapped)
    plan = runtime.service().create_selection_plan(URL)
    assert plan.state is CarouselPlanState.BLOCKED and not plan.selected_videos
    assert plan.issue is CarouselIssue.UNSTABLE_IDENTITIES and not calls


@pytest.mark.parametrize("code", [None, "", "different", 123, True])
def test_missing_pk_or_conflicting_code_cannot_use_url_fallback(code):
    runtime = Runtime([VIDEO])
    runtime.product["code"] = code
    assert runtime.service().create_selection_plan(URL).state is CarouselPlanState.BLOCKED
    runtime.product.pop("pk")
    runtime.product["code"] = "Fixture_Carousel"
    assert runtime.service().create_selection_plan(URL).state is CarouselPlanState.BLOCKED


def test_upstream_url_derived_result_id_cannot_replace_parent(monkeypatch):
    runtime = Runtime([VIDEO])
    runtime.product.pop("pk")
    # Demonstrate the actual installed upstream fallback, outside the guarded adapter.
    with runtime.factory({"quiet": True}) as ydl:
        raw = InstagramIE(ydl)._extract_product(runtime.product, video_id="Fixture_Carousel")
    assert raw["id"] == "Fixture_Carousel"
    raw["_carousel_source_count"] = 1
    runtime.raw_override = raw
    assert runtime.service().create_selection_plan(URL).state is CarouselPlanState.BLOCKED


@pytest.mark.parametrize(
    "mutation", ["missing", "pk", "code", "shape", "url", "bool_position", "unknown_kind", "count"]
)
def test_forged_ipc_refused_without_identity_reconstruction(mutation):
    plan = Runtime([VIDEO, {**VIDEO, "pk": 103}]).service().create_selection_plan(URL)
    data = json.loads(json.dumps(plan_payload(plan)))
    if mutation == "missing":
        data.pop("parent_identity")
    elif mutation == "pk":
        data["parent_identity"]["pk"] = str(PK + 1)
    elif mutation == "code":
        data["parent_identity"]["shortcode"] = "different"
    elif mutation == "shape":
        data["parent_identity"] = ["private-parent-sentinel"]
    elif mutation == "url":
        data["publication_url"] = "https://www.instagram.com/p/different/"
    elif mutation == "bool_position":
        data["items"][0]["position"] = True
    elif mutation == "unknown_kind":
        data["items"][0]["kind"] = "private-parent-sentinel"
    else:
        data["total_entries"] = 3
    with pytest.raises(DownloadFailedError, match="Invalid private carousel plan") as error:
        plan_from_payload(data)
    assert "private-parent-sentinel" not in str(error.value)


def test_missing_identity_blocks_service_validator_and_repr(caplog):
    runtime = Runtime([VIDEO])
    plan = runtime.service().create_selection_plan(URL)
    facts = runtime.provider.inspect_carousel(URL)
    assert (
        runtime.service()._selection_plan(replace(facts, parent_identity=None)).state
        is CarouselPlanState.BLOCKED
    )
    with pytest.raises(DownloadFailedError):
        validate_plan(replace(plan, parent_identity=None), CarouselAcquisitionLimits())
    assert str(PK) not in repr(plan) + repr(facts) + repr(plan.parent_identity) + caplog.text
    assert (
        "Fixture_Carousel"
        not in repr(plan) + repr(facts) + repr(plan.parent_identity) + caplog.text
    )


def test_parent_refusal_events_do_not_expose_response_or_ipc(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    runtime = Runtime([VIDEO])
    good = runtime.service().create_selection_plan(URL)
    runtime.product["code"] = "private-parent-sentinel"
    with Operation("instagram", "metadata") as operation:
        blocked = runtime.service().inspect_publication(URL)
        assert blocked.state is CarouselPlanState.BLOCKED
        operation.fail(category="refused")
    bad = plan_payload(good)
    bad["parent_identity"]["pk"] = "private-parent-sentinel"
    with pytest.raises(DownloadFailedError), Operation("instagram", "download"):
        plan_from_payload(bad)
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 4 and all(r.exc_info is None for r in records)
    assert [json.loads(r.getMessage())["event"] for r in records] == [
        "operation_started",
        "operation_failed",
        "operation_started",
        "operation_failed",
    ]
    for value in (str(PK), "Fixture_Carousel", "private-parent-sentinel", URL):
        assert value not in caplog.text


@pytest.mark.parametrize("mutation", ["parent", "child", "order", "type", "count", "unknown"])
def test_fresh_parent_and_full_manifest_gate_before_any_media(tmp_path, media_files, mutation):
    runtime = AcquisitionRuntime(product(3, photos=(2,)), media_files["video"])
    plan = runtime.plan()
    if mutation == "parent":
        runtime.data["pk"] += 1
    elif mutation == "child":
        runtime.data["carousel_media"][0]["pk"] += 10
    elif mutation == "order":
        runtime.data["carousel_media"].reverse()
    elif mutation == "type":
        runtime.data["carousel_media"][1] = {**deepcopy(VIDEO), "pk": 1002}
    elif mutation == "count":
        runtime.data["carousel_media"].pop()
    else:
        runtime.data["carousel_media"][1] = {"pk": 1002}
    facts, _ = runtime.provider.fresh_carousel_entries(URL)
    assert not _same_selection(plan, facts)
    with pytest.raises(DownloadFailedError):
        acquire(runtime, plan, tmp_path)
    assert not runtime.processed and runtime.requests == 0
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_parent_only_change_refused_in_real_child_and_reaped(
    tmp_path, media_files, monkeypatch, caplog
):
    runtime = AcquisitionRuntime(product(2), media_files["video"])
    script = subprocess_script(runtime.media).replace(
        "boundary.InstagramProvider=lambda:",
        "runtime.data['pk'] += 1\nboundary.InstagramProvider=lambda:",
    )
    processes = install_child(monkeypatch, script)
    with pytest.raises(DownloadFailedError):
        await InstagramCarouselAcquisition().acquire(runtime.plan(), tmp_path)
    assert len(processes) == 1 and processes[0].returncode is not None
    assert list(tmp_path.iterdir()) == []
    assert str(PK) not in caplog.text and "Fixture_Carousel" not in caplog.text
