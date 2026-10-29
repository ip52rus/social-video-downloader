"""Bounded, explicit YouTube snapshot wire types; never a general object loader."""

import json
import math
import sys
from dataclasses import dataclass, field
from time import monotonic, monotonic_ns

from yt_dlp.extractor.youtube import YoutubeIE
from yt_dlp.utils.networking import HTTPHeaderDict
from yt_dlp.version import __version__

from social_video_downloader.domain.errors import MetadataExtractionError

REQUEST_BYTES = 8 * 1024
RESPONSE_BYTES = 2 * 1024**2
SNAPSHOT_BYTES = 8 * 1024**2
CACHE_BYTES = 64 * 1024**2
MAX_DEPTH = 32
MAX_NODES = 100_000
VERSION = 1
TTL = 180


def refuse():
    raise MetadataExtractionError("YouTube metadata snapshot was refused.") from None


def target(url):
    # Local parser only; no extraction. Keep the provider's existing normalization.
    from social_video_downloader.providers.youtube import YouTubeProvider

    if type(url) is not str:
        refuse()
    canonical = YouTubeProvider._normalize_youtube_url(url)
    try:
        video_id = YoutubeIE.extract_id(canonical)
    except Exception:
        refuse()
    return canonical, video_id


def encode(value, limit=RESPONSE_BYTES):
    active = set()
    nodes = units = 0

    def walk(obj, depth):
        nonlocal nodes, units
        nodes += 1
        kind = type(obj)
        units += len(obj) if kind is str else 1
        if depth > MAX_DEPTH or nodes > MAX_NODES or units > limit:
            refuse()
        if obj is None or kind in (str, bool):
            return obj
        if kind is int and obj.bit_length() <= 210:
            return obj
        if kind is float and math.isfinite(obj):
            return obj
        if kind not in (dict, list, tuple, HTTPHeaderDict) or id(obj) in active:
            refuse()
        active.add(id(obj))
        try:
            if kind in (dict, HTTPHeaderDict):
                pairs = []
                source = obj.sensitive() if kind is HTTPHeaderDict else obj
                for key, item in source.items():
                    if type(key) is not str:
                        refuse()
                    units += len(key)
                    if units > limit:
                        refuse()
                    pairs.append([key, walk(item, depth + 1)])
                return ["headers" if kind is HTTPHeaderDict else "dict", pairs]
            return ["tuple" if kind is tuple else "list", [walk(v, depth + 1) for v in obj]]
        finally:
            active.remove(id(obj))

    tree = walk(value, 0)
    output = bytearray()
    try:
        for chunk in json.JSONEncoder(
            separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).iterencode(tree):
            block = chunk.encode("utf-8")
            if len(output) + len(block) > limit:
                refuse()
            output.extend(block)
    except (ValueError, UnicodeError, RecursionError):
        refuse()
    return bytes(output)


def decode(data, limit=RESPONSE_BYTES):
    if type(data) is not bytes or len(data) > limit:
        refuse()

    def integer(value):
        if len(value) > 64:
            refuse()
        number = int(value)
        if number.bit_length() > 210:
            refuse()
        return number

    try:
        tree = json.loads(data, parse_int=integer, parse_constant=lambda _: refuse())
    except (ValueError, UnicodeError, RecursionError):
        refuse()
    nodes = 0

    def walk(obj, depth):
        nonlocal nodes
        nodes += 1
        if depth > MAX_DEPTH or nodes > MAX_NODES:
            refuse()
        kind = type(obj)
        if obj is None or kind in (str, bool, int):
            return obj
        if kind is float and math.isfinite(obj):
            return obj
        if kind is not list or len(obj) != 2 or type(obj[0]) is not str or type(obj[1]) is not list:
            refuse()
        tag, items = obj
        if tag in ("list", "tuple"):
            values = [walk(v, depth + 1) for v in items]
            return tuple(values) if tag == "tuple" else values
        if tag not in ("dict", "headers"):
            refuse()
        values = {}
        for pair in items:
            if (
                type(pair) is not list
                or len(pair) != 2
                or type(pair[0]) is not str
                or pair[0] in values
            ):
                refuse()
            values[pair[0]] = walk(pair[1], depth + 1)
        if tag == "headers":
            if any(type(v) is not str for v in values.values()) or len(
                {key.lower() for key in values}
            ) != len(values):
                refuse()
            return HTTPHeaderDict(values)
        return values

    return walk(tree, 0)


def memory_size(value):
    """Measure the admitted object graph, not process RSS or transient JSON memory."""
    seen, active = set(), set()
    count = total = 0

    def visit(obj, depth):
        nonlocal count, total
        count += 1
        if depth > MAX_DEPTH or count > MAX_NODES or id(obj) in active:
            refuse()
        kind = type(obj)
        if obj is not None and kind not in (
            str,
            bool,
            int,
            float,
            list,
            tuple,
            dict,
            HTTPHeaderDict,
        ):
            refuse()
        if (kind is int and obj.bit_length() > 210) or (kind is float and not math.isfinite(obj)):
            refuse()
        if id(obj) in seen:
            return
        seen.add(id(obj))
        total += sys.getsizeof(obj)
        if total > SNAPSHOT_BYTES:
            refuse()
        active.add(id(obj))
        try:
            if kind in (dict, HTTPHeaderDict):
                for key, item in obj.items():
                    if type(key) is not str:
                        refuse()
                    visit(key, depth + 1)
                    visit(item, depth + 1)
                if kind is HTTPHeaderDict:
                    visit(vars(obj), depth + 1)
            elif kind in (list, tuple):
                for item in obj:
                    visit(item, depth + 1)
        finally:
            active.remove(id(obj))

    visit(value, 0)
    return total


@dataclass(frozen=True, repr=False)
class Snapshot:
    url: str = field(repr=False)
    video_id: str = field(repr=False)
    created_at: float
    info: dict = field(repr=False)


def request(url, nonce, *, diagnostics=False):
    canonical, video_id = target(url)
    result = dict(
        version=VERSION, yt_dlp=__version__, url=canonical, video_id=video_id, nonce=nonce
    )
    if diagnostics:
        result["diagnostics"] = True
    return result


def validate_request(payload):
    if type(payload) is not dict:
        refuse()
    fields = set(payload)
    if "diagnostics" in fields:
        if payload["diagnostics"] is not True:
            refuse()
        fields.remove("diagnostics")
    if fields != {
        "version",
        "yt_dlp",
        "url",
        "video_id",
        "nonce",
    }:
        refuse()
    if (
        type(payload["version"]) is not int
        or payload["version"] != VERSION
        or payload["yt_dlp"] != __version__
        or type(payload["nonce"]) is not str
        or not 20 <= len(payload["nonce"]) <= 64
    ):
        refuse()
    canonical, video_id = target(payload["url"])
    if payload["url"] != canonical or payload["video_id"] != video_id:
        refuse()
    return payload


@dataclass(frozen=True, slots=True)
class ExtractionInterval:
    extraction_started_ns: int
    extraction_finished_ns: int


def extraction_interval(data, req, *, earliest_ns=0, now_ns=None):
    """Reject untrusted diagnostic evidence as UNKNOWN, never repair/infer timestamps."""
    if req.get("diagnostics") is not True or type(data) is not dict:
        return None
    value = data.get("diagnostics")
    if type(value) is not dict or set(value) != {"extraction_started_ns", "extraction_finished_ns"}:
        return None
    start, end = value["extraction_started_ns"], value["extraction_finished_ns"]
    now = monotonic_ns() if now_ns is None else now_ns
    if any(type(n) is not int or not 0 <= n <= 2**63 - 1 for n in (start, end, now)):
        return None
    stamp = data.get("created_at")
    if type(stamp) not in (int, float) or not math.isfinite(stamp):
        return None
    # Same-host monotonic domain; the parent also supplies its request lower bound.
    if not earliest_ns <= start <= end <= now or now - start >= TTL * 10**9:
        return None
    # Allow only float conversion precision, not a new clock/skew tolerance.
    if end > int(stamp * 10**9) + 1000:
        return None
    return ExtractionInterval(start, end)


def response(req, info, created_at, *, extraction=None):
    result = {k: v for k, v in req.items() if k != "diagnostics"}
    result.update(created_at=created_at, info=info)
    if req.get("diagnostics") is True:
        result["diagnostics"] = (
            {
                "extraction_started_ns": extraction.extraction_started_ns,
                "extraction_finished_ns": extraction.extraction_finished_ns,
            }
            if extraction is not None
            else {"extraction_started_ns": None, "extraction_finished_ns": None}
        )
    return result


def validate_response(data, req):
    expected = {k: v for k, v in req.items() if k != "diagnostics"}
    allowed = set(expected) | {"created_at", "info"}
    fields = set(data) if type(data) is dict else set()
    if req.get("diagnostics") is True:
        fields = fields - {"diagnostics"}
    if type(data) is not dict or fields != allowed:
        refuse()
    if any(
        type(data[key]) is not type(value) or data[key] != value for key, value in expected.items()
    ):
        refuse()
    stamp, info = data["created_at"], data["info"]
    age = monotonic() - stamp if type(stamp) in (int, float) else -1
    if not math.isfinite(age) or not 0 <= age < TTL:
        refuse()
    if (
        type(info) is not dict
        or info.get("_type", "video") != "video"
        or "entries" in info
        or info.get("__post_extractor") is not None
        or type(info.get("id")) is not str
        or info["id"] != req["video_id"]
    ):
        refuse()
    memory_size(info)
    return Snapshot(req["url"], req["video_id"], stamp, info)


def encode_metadata_response(payload):
    """Optional timing evidence must not displace an otherwise valid media snapshot."""
    try:
        return encode(payload)
    except MetadataExtractionError:
        if "diagnostics" not in payload:
            raise
        # Drop only optional evidence; no extraction/network/worker retry.
        return encode({k: v for k, v in payload.items() if k != "diagnostics"})


def encode_metadata_request(req):
    """An opt-in flag must not shrink the legacy request URL byte budget."""
    try:
        return req, encode(req, REQUEST_BYTES)
    except MetadataExtractionError:
        if req.get("diagnostics") is not True:
            raise
        legacy = {k: v for k, v in req.items() if k != "diagnostics"}
        return legacy, encode(legacy, REQUEST_BYTES)
