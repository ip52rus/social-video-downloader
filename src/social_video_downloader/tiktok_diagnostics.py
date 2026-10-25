"""One bounded native-refusal event; no external text or request identity."""

import json
import logging

LOGGER_NAME = "social_video_downloader.tiktok_diagnostics"
STAGES = frozenset(
    {
        "admission",
        "short_link",
        "metadata_fetch",
        "metadata_parse",
        "media_acquire",
        "media_verify",
        "cleanup",
        "unknown",
    }
)
REASONS = frozenset(
    [
        "ambiguous_metadata",
        "audio_required",
        "byte_limit",
        "cancelled",
        "case_cleanup_failed",
        "cleanup_failed",
        "content_length_required",
        "cookie_limit",
        "deadline",
        "duplicate_publication",
        "encoded_response",
        "export_failed",
        "file_size",
        "forbidden_media_destination",
        "forbidden_metadata_destination",
        "full_video_url_required",
        "header_limit",
        "incomplete_response",
        "invalid_benchmark_cases",
        "invalid_content_length",
        "invalid_input",
        "invalid_native_output",
        "invalid_session_header",
        "invalid_short_url",
        "invalid_url",
        "invalid_workspace",
        "media_content_type",
        "metadata_body_limit",
        "metadata_content_type",
        "metadata_only_prototype",
        "metadata_schema",
        "missing_embed_state",
        "missing_public_state",
        "no_bounded_candidates",
        "non_public_or_drm",
        "non_public_or_unavailable",
        "not_mp4",
        "one_or_two_full_urls_required",
        "one_public_page_url_required",
        "operation_failed",
        "posix_ffmpeg_required",
        "preparation_not_passthrough",
        "preparation_requires_conversion",
        "redirect_limit",
        "request_limit",
        "separate_streams_unsupported",
        "short_link_required",
        "short_metadata_only",
        "short_redirect_cycle",
        "short_redirect_forbidden",
        "short_redirect_required",
        "source_identity_mismatch",
        "subprocess_deadline",
        "unsupported_http_framing",
        "unsupported_page_video",
        "unsupported_photo",
        "unsupported_selector",
        "unsupported_streams",
        "unsafe_dns",
        "worker_failed",
        "worker_output_limit",
        "workspace_cleanup_failed",
        "workspace_limit",
        "interrupted",
        "http_error",
        "unknown",
    ]
)
HTTP_REASONS = frozenset(f"http_{status}" for status in range(100, 600))


def _choice(value, choices):
    return value if type(value) is str and value in choices else "unknown"


def _integer(value, lower, upper):
    return value if type(value) is int and lower <= value <= upper else None


def safe_payload(payload):
    """Rebuild the exact schema, including when the logging sink formats a record."""
    if (
        type(payload) is not dict
        or payload.get("platform") != "tiktok"
        or payload.get("event") != "native_refusal"
    ):
        return None
    exact = payload.get("counts_exact") is True
    return dict(
        platform="tiktok",
        event="native_refusal",
        reason=_choice(payload.get("reason"), REASONS),
        stage=_choice(payload.get("stage"), STAGES),
        metadata_http_status=_integer(payload.get("metadata_http_status"), 100, 599),
        counts_exact=exact,
        metadata_bytes=_integer(payload.get("metadata_bytes"), 0, 4194304) if exact else None,
        metadata_requests=_integer(payload.get("metadata_requests"), 0, 6) if exact else None,
        media_requests=_integer(payload.get("media_requests"), 0, 6) if exact else None,
    )


def emit_refusal(result):
    """Best effort after the worker lifecycle; never change the native outcome."""
    try:
        code = result.get("error")
        reason = "http_error" if type(code) is str and code in HTTP_REASONS else code
        reports = result.get("results")
        report = reports[0] if type(reports) is list and len(reports) == 1 else None
        # Supervisor/cleanup overrides must not inherit an unrelated worker stage/status.
        report = report if type(report) is dict and report.get("error") == code else {}
        payload = safe_payload(
            dict(
                platform="tiktok",
                event="native_refusal",
                reason=reason,
                stage=report.get("failure_stage"),
                metadata_http_status=report.get("metadata_http_status"),
                counts_exact=result.get("counts_exact"),
                metadata_bytes=result.get("metadata_bytes"),
                metadata_requests=result.get("metadata_requests"),
                media_requests=result.get("media_requests"),
            )
        )
        logging.getLogger(LOGGER_NAME).warning(
            json.dumps(payload, sort_keys=True), extra={"safe_tiktok_event": payload}
        )
    except Exception:
        # Logging failure never retries acquisition or interferes with cleanup/cancellation.
        pass
