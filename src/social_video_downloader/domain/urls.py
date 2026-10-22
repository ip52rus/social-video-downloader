"""URL normalization and platform detection."""

from re import findall, fullmatch, search
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

from social_video_downloader.domain.errors import (
    InvalidMediaURLError,
    UnsupportedPlatformError,
)
from social_video_downloader.domain.models import Platform

_PLATFORM_DOMAINS: dict[Platform, tuple[str, ...]] = {
    Platform.YOUTUBE: (
        "youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
    ),
    Platform.INSTAGRAM: ("instagram.com",),
    Platform.TIKTOK: ("tiktok.com",),
}


def normalize_media_url(url: str) -> str:
    """Normalize a media URL without changing its meaningful query parameters."""
    if not isinstance(url, str) or not url.strip():
        raise InvalidMediaURLError("Media URL must not be empty.")

    candidate = url.strip()

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    try:
        parts = urlsplit(candidate)
        port = parts.port
    except ValueError as exc:
        raise InvalidMediaURLError("Media URL is malformed.") from exc

    scheme = parts.scheme.lower()

    if scheme not in {"http", "https"}:
        raise InvalidMediaURLError("Only HTTP and HTTPS URLs are allowed.")

    if parts.username is not None or parts.password is not None:
        raise InvalidMediaURLError("Media URLs must not contain user credentials.")

    if not parts.hostname:
        raise InvalidMediaURLError("Media URL must contain a hostname.")

    try:
        hostname = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise InvalidMediaURLError("Media URL contains an invalid hostname.") from exc

    if not hostname:
        raise InvalidMediaURLError("Media URL must contain a hostname.")

    netloc = f"[{hostname}]" if ":" in hostname else hostname

    is_default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    if port is not None and not is_default_port:
        netloc = f"{netloc}:{port}"

    return urlunsplit(
        (
            scheme,
            netloc,
            parts.path,
            parts.query,
            "",
        )
    )


def has_instagram_item_reference(raw: str) -> bool:
    """Inspect intent on a raw URL already validated by InstagramProvider.

    Share parameters are discarded by the provider's canonicalization. Only known
    selectors change publication scope; malformed or overlarge references fail closed.
    """
    parts = urlsplit(raw.strip())
    try:
        query = parse_qsl(parts.query, keep_blank_values=True, max_num_fields=32)
    except ValueError:
        raise InvalidMediaURLError("Ambiguous reference.") from None
    if (
        any(not key for key, _ in query)
        or search(r"%(?![0-9A-Fa-f]{2})", parts.query)
        or search(r"%(?![0-9A-Fa-f]{2})", parts.fragment)
    ):
        raise InvalidMediaURLError("Malformed reference.")

    def decoded(value):
        # Escaped selectors must not masquerade as unknown tracking keys. Each
        # changing decode shortens the string; a literal percent sign converges.
        while (normalized := unquote(value)) != value:
            value = normalized
        return value

    reference_keys = {"img_index", "media_id", "item_id", "carousel_index", "index", "slide"}
    fragment_keys = findall(r"(?:^|[?&/])([^=:/?&]+)", decoded(parts.fragment))
    return any(decoded(key).casefold() in reference_keys for key, _ in query) or any(
        key.casefold() in reference_keys for key in fragment_keys
    )


def detect_platform(url: str) -> Platform:
    """Detect a supported platform from a URL's hostname."""
    normalized_url = normalize_media_url(url)
    hostname = urlsplit(normalized_url).hostname

    if hostname is None:
        raise InvalidMediaURLError("Media URL must contain a hostname.")

    for platform, domains in _PLATFORM_DOMAINS.items():
        if any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains):
            return platform

    raise UnsupportedPlatformError(f"No supported provider matches hostname '{hostname}'.")


def instagram_item_position(raw: str) -> int | None:
    """One unambiguous img_index; never silently discard malformed reference intent."""
    normalize_media_url(raw)
    if len(raw) > 4096:
        raise InvalidMediaURLError("Instagram reference is too large.")
    # Retain the legacy fragment/malformed/query-field guards used by Reel admission.
    has_reference = has_instagram_item_reference(raw)
    parts = urlsplit(raw.strip())
    try:
        unquote(parts.fragment, errors="strict")
        query = parse_qsl(parts.query, keep_blank_values=True, max_num_fields=32, errors="strict")
    except (ValueError, UnicodeError):
        raise InvalidMediaURLError("Malformed Instagram reference.") from None
    keys = {"img_index", "media_id", "item_id", "carousel_index", "index", "slide"}
    selected = []
    for key, value in query:
        decoded = key
        while (next_key := unquote(decoded)) != decoded:
            decoded = next_key
        if decoded.casefold() not in keys and search(
            r"^(?:img_index|media_id|item_id|carousel_index|index|slide)[^a-zA-Z0-9_]",
            decoded.casefold(),
        ):
            raise InvalidMediaURLError("Malformed Instagram selector.")
        if decoded.casefold() not in keys:
            continue
        if key.casefold() != "img_index" or decoded != key:
            raise InvalidMediaURLError("Unsupported or ambiguous Instagram selector.")
        if not fullmatch(r"[1-9][0-9]{0,8}", value):
            raise InvalidMediaURLError("Instagram position must be a positive integer.")
        selected.append(int(value))
    # Check fragments independently: a query selector cannot legitimise a fragment selector.
    fragment_url = parts._replace(query="").geturl()
    if has_instagram_item_reference(fragment_url) or len(selected) > 1:
        raise InvalidMediaURLError("Ambiguous Instagram selector.")
    if has_reference and not selected:
        raise InvalidMediaURLError("Unsupported Instagram selector.")
    return selected[0] if selected else None
