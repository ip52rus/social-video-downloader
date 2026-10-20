"""Synthetic page state and real HTTP parser only; external sockets forbidden."""

import json
import traceback
from time import monotonic

import pytest

from scripts import tiktok_native as cli
from social_video_downloader.infrastructure import tiktok_native as native
from social_video_downloader.infrastructure import tiktok_public_page as page
from social_video_downloader.providers.tiktok import TikTokProvider
from tests.test_tiktok_native import MEDIA, A, key, network, response
from tests.test_tiktok_native import offline as offline


def html(identity="11111111", video=None, **fields):
    item = {"id": identity, "video": video if video is not None else {"playAddr": MEDIA}, **fields}
    state = {
        "__DEFAULT_SCOPE__": {
            "webapp.video-detail": {"statusCode": 0, "itemInfo": {"itemStruct": item}}
        }
    }
    return (
        f'<script id="{page.STATE_ID}" type="application/json">' + json.dumps(state) + "</script>"
    ).encode()


@pytest.mark.parametrize(
    "query", ["", "?is_from_webapp=1", "?is_from_webapp=1&sender_device=pc#share"]
)
def test_embed_transport_uses_the_same_canonical_url_as_provider(monkeypatch, query):
    # Provider now selects public-page metadata; this checks shared canonicalization.
    assert cli is native and TikTokProvider.download_prepared.__globals__["native"] is native
    embed = "https://www.tiktok.com/embed/v2/11111111"
    wire = network(monkeypatch, {key(embed): response(b"<html>synthetic</html>")})
    for supplied in (A + query, TikTokProvider.canonical_url(A + query)):
        identity, canonical = native.publication(supplied)
        session = native.Session(identity, canonical, monotonic() + 10, native._budget())
        session.metadata()
    requests = [
        (host, method, target, dict(headers)) for host, method, target, headers in wire.requests
    ]
    assert requests[0] == requests[1]
    assert requests[0][2] == "/embed/v2/11111111"
    assert wire.requests[0][3]["Referer"] == A
    assert wire.requests[0][3]["User-Agent"] == native.UA
    assert wire.requests[0][3]["Accept-Encoding"] == "identity"


@pytest.mark.parametrize("address", [MEDIA, [{"src": MEDIA}, {"src": MEDIA}]])
def test_public_state_identity_and_signed_play_addr(address, capsys):
    result = page.resolve_public_page(html(video={"playAddr": address}), A)
    assert result.url == MEDIA and result.source == "playAddr" and result.candidates == 1
    assert not result.separate_audio
    assert MEDIA not in repr(result) and not capsys.readouterr().out


def test_installed_ytdlp_recognizes_the_same_schema_but_does_not_prove_source_id():
    from yt_dlp import YoutubeDL
    from yt_dlp.extractor.tiktok import TikTokIE

    with YoutubeDL({"quiet": True, "no_warnings": True, "cachedir": False}) as ydl:
        extractor = TikTokIE(ydl)
        scope = extractor._get_universal_data(html().decode(), "offline")
        item = scope["webapp.video-detail"]["itemInfo"]["itemStruct"]
        mapped = extractor._parse_aweme_video_web(item, A, "11111111")
        assert page.resolve_public_page(html(), A).url in [f["url"] for f in mapped["formats"]]
        item["id"] = "22222222"
        assert extractor._parse_aweme_video_web(item, A, "11111111")["id"] == "11111111"
    with pytest.raises(native.Refusal, match="^source_identity_mismatch$"):
        page.resolve_public_page(html("22222222"), A)


@pytest.mark.parametrize("identity", [None, True, "22222222", {}, "11111111 "])
def test_source_id_not_replaced_or_inferred(identity):
    with pytest.raises(native.Refusal, match="^source_identity_mismatch$"):
        page.resolve_public_page(html(identity), A)


@pytest.mark.parametrize(
    "body",
    [
        b"<html>" + b"x" * 524 + b"</html>",
        b"<html>PRIVATE_HTML</html>",
        b"<!--" + html() + b"-->",
        b"<textarea>" + html() + b"</textarea>",
        b"<template>" + html() + b"</template>",
        b"<title>" + html() + b"</title>",
        b"<plaintext></plaintext>" + html(),
        html() + html(),
        html().replace(
            b'type="application/json"', b'type="application/json" TYPE="text/javascript"'
        ),
        html().replace(b'"id":', b'"id":"11111111", "id":'),
        html().removesuffix(b"</script>"),
        html().replace(b'"statusCode": 0', b'"statusCode": 10216'),
        b"\xffPRIVATE_HTML",
    ],
)
def test_ambiguous_missing_or_damaged_state_has_safe_failure(body, capsys):
    with pytest.raises(native.Refusal) as caught:
        page.resolve_public_page(body, A)
    rendered = "".join(traceback.format_exception(caught.value))
    assert not any(secret in rendered for secret in ("PRIVATE_HTML", "PRIVATE_SIGNED", MEDIA))
    assert not capsys.readouterr().out


@pytest.mark.parametrize(
    "fields",
    [
        {"privateItem": True},
        {"isContentClassified": True},
        {"imagePost": {"images": [{"imageURL": {"urlList": ["PRIVATE_IMAGE"]}}]}},
        {"imagePostInfo": {"unknown": "PRIVATE_DATA"}},
    ],
)
def test_private_or_photo_content_is_not_video(fields):
    with pytest.raises(native.Refusal):
        page.resolve_public_page(html(**fields), A)


def test_no_download_fallback_and_separate_audio_not_assumed_silent():
    with pytest.raises(native.Refusal):
        page.resolve_public_page(html(video={"downloadAddr": MEDIA}), A)
    result = page.resolve_public_page(
        html(video={"playAddr": MEDIA, "audioAddr": "PRIVATE_AUDIO"}, imagePost=None), A
    )
    assert result.separate_audio


def test_malformed_url_has_no_raw_parser_exception_or_network():
    untrusted = "https://[PRIVATE_URL_TOKEN]/video/11111111"
    with pytest.raises(native.Refusal, match="^invalid_input$") as caught:
        page.inspect_public_page(
            untrusted,
            deadline=monotonic() + 10,
            budget=native._budget(),
        )
    assert "PRIVATE_URL_TOKEN" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize(
    "media",
    ["https://evil.invalid/file", "https://127.0.0.1/file", "http://v77.tiktokcdn.com/file"],
)
def test_media_admission_uses_existing_policy(media):
    with pytest.raises(native.Refusal, match="^forbidden_media_destination$"):
        page.resolve_public_page(html(video={"playAddr": media}), A)


def test_one_page_request_with_original_headers_and_destroyed_cookie_state(monkeypatch):
    sessions = []
    original = page._PublicPageSession

    class Observed(original):
        def __init__(self, *args):
            super().__init__(*args)
            sessions.append(self)

    monkeypatch.setattr(page, "_PublicPageSession", Observed)
    wire = network(
        monkeypatch,
        {
            key(A): response(
                html(), fields=[("Set-Cookie", "temporary=PRIVATE_COOKIE; Secure; Path=/")]
            )
        },
    )
    budget = native._budget()
    resolved = page.inspect_public_page(
        A + "?is_from_webapp=1&sender_device=pc", deadline=monotonic() + 10, budget=budget
    )
    assert resolved.url == MEDIA and len(wire.requests) == 1
    request = wire.requests[0]
    assert request[2] == "/@fixture/video/11111111"
    assert request[3]["Referer"] == A and request[3]["User-Agent"] == native.UA
    assert request[3]["Accept-Encoding"] == "identity" and "Cookie" not in request[3]
    assert budget == {**native._budget(), "metadata_requests": 1, "metadata_bytes": len(html())}
    assert len(sessions[0].jar) == 0
    with (
        pytest.raises(native.Refusal, match="^metadata_only_prototype$"),
        sessions[0].open(MEDIA, "media"),
    ):
        pytest.fail("No media operation is allowed")
    assert len(wire.requests) == 1 and budget["media_requests"] == 0


@pytest.mark.parametrize("status", [403, 429])
def test_http_refusal_stops_without_retry_or_embed_request(monkeypatch, status):
    wire = network(monkeypatch, {key(A): (status, b"PRIVATE_HTML", {"Retry-After": "300"})})
    budget = native._budget()
    with pytest.raises(native.Refusal, match=f"^http_{status}$"):
        page.inspect_public_page(A, deadline=monotonic() + 10, budget=budget)
    assert len(wire.requests) == budget["metadata_requests"] == 1
    assert budget["metadata_bytes"] == budget["media_requests"] == budget["acquisitions"] == 0


def test_allowed_canonical_slash_redirect_keeps_original_context(monkeypatch):
    wire = network(
        monkeypatch,
        {
            key(A): (302, b"", {"Location": A + "/"}),
            key(A + "/"): response(html()),
        },
    )
    budget = native._budget()
    assert page.inspect_public_page(A, deadline=monotonic() + 10, budget=budget).url == MEDIA
    assert len(wire.requests) == budget["metadata_requests"] == 2
    assert all(request[3]["Referer"] == A for request in wire.requests)
    assert budget["media_requests"] == budget["acquisitions"] == 0


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.invalid/login",
        "https://127.0.0.1/",
        A.replace("11111111", "22222222"),
        "https://www.tiktok.com/embed/v2/11111111",
    ],
)
def test_redirect_is_rejected_before_another_connection(monkeypatch, target):
    wire = network(monkeypatch, {key(A): (302, b"", {"Location": target})})
    with pytest.raises(native.Refusal, match="^forbidden_metadata_destination$"):
        page.inspect_public_page(A, deadline=monotonic() + 10, budget=native._budget())
    assert len(wire.requests) == 1


@pytest.mark.parametrize("fault", ["oversize", "incomplete", "budget", "deadline"])
def test_existing_body_request_and_deadline_limits(monkeypatch, fault):
    budget = native._budget()
    if fault == "budget":
        budget["metadata_requests"] = 6
    fields = {
        "Content-Type": "text/html",
        "Content-Length": str(native.HTML_BYTES + 1 if fault == "oversize" else len(html()) + 1),
    }
    wire = network(monkeypatch, {key(A): (200, html(), fields)})
    with pytest.raises(native.Refusal):
        page.inspect_public_page(
            A, deadline=monotonic() + (-1 if fault == "deadline" else 10), budget=budget
        )
    assert len(wire.requests) == (0 if fault in {"budget", "deadline"} else 1)
    assert budget["media_requests"] == budget["acquisitions"] == 0
    if fault == "incomplete":
        assert budget["metadata_bytes"] == len(html())
