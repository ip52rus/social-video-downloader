"""One metadata-only YouTube operation; private bounded stdin/stdout, no delivery."""

import contextlib
import os
import signal
import sys
from time import monotonic

from social_video_downloader.infrastructure.youtube_snapshot import (
    REQUEST_BYTES,
    decode,
    encode,
    response,
    validate_request,
    validate_response,
)
from social_video_downloader.providers.youtube import YouTubeProvider


def _terminate(*_):
    raise SystemExit(1)


def main():
    signal.signal(signal.SIGTERM, _terminate)
    try:
        req = validate_request(decode(sys.stdin.buffer.read(REQUEST_BYTES + 1), REQUEST_BYTES))
        # No cookies, credentials, download(), process_ie_result(), or metadata files.
        provider = YouTubeProvider()
        options = provider._base_options()
        options["cachedir"] = False
        options.update(retries=0, fragment_retries=0, extractor_retries=0)
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
            with provider._new_ydl(options) as ydl:
                info = provider._read_raw_info(ydl, req["url"])
            payload = response(req, info, monotonic())
            validate_response(payload, req)
            wire = encode(payload)
        sys.stdout.buffer.write(wire)
        sys.stdout.buffer.flush()
        return 0
    except BaseException:
        # Neither exception text nor upstream diagnostics cross the boundary.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
