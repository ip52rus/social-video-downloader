"""Bounded short redirects on the existing pinned transport, inside its worker."""

import re
from time import monotonic

from social_video_downloader.infrastructure import tiktok_native as native

SHORT_HOSTS = frozenset({"vm.tiktok.com", "vt.tiktok.com"})
SHORT_SECONDS = 20


def reference(value: str) -> str:
    """Pure admission/canonicalization; never resolve a short link during intake."""
    parsed = native._url(value)
    if parsed.hostname not in SHORT_HOSTS:
        return native.publication(value)[1]
    if not re.fullmatch(r"/[A-Za-z0-9]{1,64}/?", parsed.path) or "?" in value or "#" in value:
        raise native.Refusal("invalid_short_url")
    return f"https://{parsed.hostname}{parsed.path}"


def is_short(value: str) -> bool:
    return native._url(value).hostname in SHORT_HOSTS


class _DestinationFound(Exception):
    """Internal control flow only: no locator is included in exception text."""


class ShortLinkSession(native.Session):
    def __init__(self, deadline, budget):
        super().__init__(
            "", "https://www.tiktok.com/", min(deadline, monotonic() + SHORT_SECONDS), budget
        )
        self.canonical = None
        self._seen = {}

    def _admit(self, url, phase):
        self.remaining()
        if phase != "metadata":
            raise native.Refusal("short_metadata_only")
        if is_short(url):
            admitted = reference(url)
            count = self.budget["metadata_requests"]
            # open() admits a redirect target and then admits it again before
            # connecting, without incrementing the counter in between.
            if admitted in self._seen and self._seen[admitted] != count:
                raise native.Refusal("short_redirect_cycle")
            self._seen[admitted] = count
            return
        try:
            _, canonical = native.publication(url)
        except (native.Refusal, ValueError, TypeError):
            raise native.Refusal("short_redirect_forbidden") from None
        self.canonical = canonical
        # The parent transport closes the redirect response/connection in its
        # finally blocks. Do not GET the final page until normal metadata parsing.
        raise _DestinationFound

    def resolve(self, url):
        admitted = reference(url)
        if not is_short(admitted):
            raise native.Refusal("short_link_required")
        try:
            with self.open(admitted, "metadata"):
                # A 200 body, JS redirect or challenge is not a publication URL.
                raise native.Refusal("short_redirect_required")
        except _DestinationFound:
            return self.canonical
