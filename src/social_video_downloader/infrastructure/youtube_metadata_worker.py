"""One metadata-only YouTube operation; private bounded stdin/stdout, no delivery."""

import contextlib
import os
import signal
import sys
from time import monotonic, monotonic_ns

from social_video_downloader.infrastructure.youtube_snapshot import (
    REQUEST_BYTES,
    ExtractionInterval,
    decode,
    encode_metadata_response,
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
                extraction = None
                if req.get("diagnostics") is True:
                    started = finished = None
                    with contextlib.suppress(Exception):
                        started = monotonic_ns()
                    info = provider._read_raw_info(ydl, req["url"])
                    with contextlib.suppress(Exception):
                        finished = monotonic_ns()
                    if started is not None and finished is not None:
                        extraction = ExtractionInterval(started, finished)
                else:
                    info = provider._read_raw_info(ydl, req["url"])
            payload = response(req, info, monotonic(), extraction=extraction)
            validate_response(payload, req)
            wire = encode_metadata_response(payload)
        sys.stdout.buffer.write(wire)
        sys.stdout.buffer.flush()
        return 0
    except BaseException:
        # Neither exception text nor upstream diagnostics cross the boundary.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
