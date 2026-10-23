"""Strict synthetic snapshot codec/admission; no external extraction."""

import json
from dataclasses import replace
from time import monotonic

import pytest
from yt_dlp.utils import LazyList
from yt_dlp.utils.networking import HTTPHeaderDict

from social_video_downloader.domain.errors import MetadataExtractionError
from social_video_downloader.infrastructure import youtube_snapshot as wire
from social_video_downloader.providers.youtube import YouTubeProvider
from tests.youtube_metadata_fixtures import info

URL = "https://www.youtube.com/watch?v=abcdefghijk"


def envelope():
    req = wire.request(URL, "synthetic-request-nonce")
    return req, wire.response(req, info(), monotonic())


def test_real_types_roundtrip_private_repr_and_binding():
    req, payload = envelope()
    payload["info"]["http_headers"] = HTTPHeaderDict({"x-Synthetic": "private"})
    restored = wire.decode(wire.encode(payload))
    snapshot = wire.validate_response(restored, req)
    assert snapshot.info == payload["info"]
    assert type(snapshot.info["_format_sort_fields"]) is tuple
    assert type(snapshot.info["http_headers"]) is HTTPHeaderDict
    assert snapshot.info["http_headers"]["X-SYNTHETIC"] == "private"
    assert URL not in repr(snapshot) and "private" not in repr(snapshot)
    assert snapshot.created_at == payload["created_at"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 2),
        ("yt_dlp", "wrong"),
        ("url", URL + "&other=1"),
        ("video_id", "lmnopqrstuv"),
        ("nonce", "another-operation-nonce"),
        ("created_at", monotonic() + 1000),
        ("created_at", monotonic() - 181),
        ("created_at", True),
        ("created_at", float("nan")),
    ],
)
def test_forged_response_refused(field, value):
    req, payload = envelope()
    payload[field] = value
    with pytest.raises(MetadataExtractionError):
        wire.validate_response(payload, req)


@pytest.mark.parametrize(
    "change",
    [
        {"id": "lmnopqrstuv"},
        {"id": True},
        {"_type": "url"},
        {"_type": "url_transparent"},
        {"_type": "playlist"},
        {"entries": []},
        {"__post_extractor": lambda: None},
    ],
)
def test_unconfirmed_or_deferred_video_refused(change):
    req, payload = envelope()
    payload["info"].update(change)
    with pytest.raises(MetadataExtractionError):
        wire.validate_response(payload, req)


@pytest.mark.parametrize(
    "kind", ["callable", "lazy", "bytes", "set", "object", "cycle", "huge_int", "nan"]
)
def test_unsupported_objects_do_not_run_or_materialize(kind):
    def forbidden():
        raise AssertionError("must not evaluate")
        yield None

    values = {
        "callable": forbidden,
        "lazy": LazyList(forbidden()),
        "bytes": b"private",
        "set": {1},
        "object": object(),
        "cycle": [],
        "huge_int": 10**100,
        "nan": float("nan"),
    }
    values["cycle"].append(values["cycle"])
    with pytest.raises(MetadataExtractionError):
        wire.encode({"synthetic": values[kind]})


@pytest.mark.parametrize(
    "data",
    [
        b"{",
        b'["class",[]]',
        b'["dict",[["key",1],["key",2]]]',
        b'["headers",[["key",1]]]',
        b'["headers",[["X-Key","a"],["x-key","b"]]]',
        b"1e999",
        b"NaN",
        b"[" * 1500,
        b'["list",' + b"[null," * 2,
        b"9" * 65,
    ],
)
def test_malformed_wire_refused(data):
    with pytest.raises(MetadataExtractionError):
        wire.decode(data)


@pytest.mark.parametrize("cap", [wire.REQUEST_BYTES, wire.RESPONSE_BYTES])
def test_exact_wire_budget_and_one_byte_over(cap):
    empty = {"padding": ""}
    count = cap - len(wire.encode(empty, cap))
    value = {"padding": "x" * count}
    encoded = wire.encode(value, cap)
    assert len(encoded) == cap and wire.decode(encoded, cap) == value
    with pytest.raises(MetadataExtractionError):
        wire.encode({"padding": value["padding"] + "x"}, cap)
    with pytest.raises(MetadataExtractionError):
        wire.decode(encoded + b" ", cap)


def test_depth_nodes_and_decoded_ram_limits(monkeypatch):
    nested = None
    for _ in range(34):
        nested = [nested]
    with pytest.raises(MetadataExtractionError):
        wire.encode(nested)
    with pytest.raises(MetadataExtractionError):
        wire.decode(json.dumps(["list", [None] * 100001]).encode())
    monkeypatch.setattr(wire, "SNAPSHOT_BYTES", 128)
    with pytest.raises(MetadataExtractionError):
        wire.memory_size(info())


def test_ram_refusal_does_not_evict_live_cache(monkeypatch):
    provider = YouTubeProvider()
    req, payload = envelope()
    snapshot = wire.validate_response(payload, req)
    provider._publish_snapshot(snapshot)
    before = dict(provider._inspection_cache)
    monkeypatch.setattr(wire, "CACHE_BYTES", 1)
    other_req = wire.request("https://youtu.be/lmnopqrstuv", "synthetic-request-nonce")
    other = wire.validate_response(
        wire.response(other_req, info("lmnopqrstuv"), monotonic()), other_req
    )
    with pytest.raises(MetadataExtractionError):
        provider._publish_snapshot(other)
    assert provider._inspection_cache == before
    assert provider._take_cached_info(URL) is snapshot.info


def test_import_keeps_original_timestamp_ttl_capacity_and_eviction(monkeypatch):
    from social_video_downloader.providers import youtube

    now = [monotonic()]
    monkeypatch.setattr(youtube, "monotonic", lambda: now[0])
    provider = YouTubeProvider()
    req, payload = envelope()
    snapshot = wire.validate_response(payload, req)
    provider._publish_snapshot(snapshot)
    stamp = snapshot.created_at
    assert provider._inspection_cache[URL][0] == stamp
    now[0] = stamp + 179.999
    assert provider._cached_info(URL) is not None
    now[0] = stamp + 180
    assert provider._cached_info(URL) is None
    for i in range(33):
        now[0] += 1
        provider._remember_info(str(i), info())
    assert len(provider._inspection_cache) == 32 and "0" not in provider._inspection_cache
    with pytest.raises(MetadataExtractionError):
        provider._publish_snapshot(replace(snapshot, video_id="other", info={"id": "other"}))
