"""Private offline, killable preparation boundary; never acquires or uploads media."""

import contextlib
import json
import math
import os
import resource
import shutil
import signal
import stat
import subprocess
import sys
from pathlib import Path
from time import monotonic

from social_video_downloader.domain.errors import MediaProcessingError
from social_video_downloader.infrastructure.telegram_carousel import (
    CarouselDeliveryLimits,
    _fingerprint,
)
from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)


class _PreparationStopped(BaseException):
    """Terminal budget/deadline stop; the helper must not retry via transcode."""


def _usage(workspace, limits):
    """Logical regular-file bytes by unique inode, including caller-owned originals."""
    entries = 0
    inodes = {}
    for directory, dirs, files in os.walk(workspace, followlinks=False):
        entries += len(dirs) + len(files)
        if entries > limits.max_workspace_entries:
            raise MediaProcessingError("Carousel workspace entry limit exceeded.")
        for name in files:
            info = (Path(directory) / name).lstat()
            if stat.S_ISREG(info.st_mode):
                inodes[(info.st_dev, info.st_ino)] = info.st_size
        if sum(inodes.values()) > limits.max_workspace_bytes:
            raise MediaProcessingError("Carousel workspace byte limit exceeded.")
    return sum(inodes.values())


def _input_paths(inputs, workspace, private, total_bytes, limits):
    if (
        workspace.is_symlink()
        or not workspace.is_dir()
        or workspace.resolve() != workspace
        or private.is_symlink()
        or not private.is_dir()
        or private.resolve().parent != workspace
        or list(private.iterdir())
        or not isinstance(inputs, list)
        or not 1 <= len(inputs) <= limits.max_videos
    ):
        raise MediaProcessingError("Invalid carousel preparation workspace.")
    paths = []
    fingerprints = []
    for value in inputs:
        path = Path(value)
        relative = path.relative_to(workspace)
        if not path.is_absolute() or ".." in relative.parts or path == private:
            raise MediaProcessingError("Carousel source is outside the approved workspace.")
        parent = workspace
        for part in relative.parts:
            parent = parent / part
            if parent.is_symlink():
                raise MediaProcessingError("Carousel source traverses a symlink.")
        if path.is_relative_to(private):
            raise MediaProcessingError("Carousel source cannot be a prepared derivative.")
        fingerprint = _fingerprint(path)
        paths.append(path)
        fingerprints.append(fingerprint)
    if (
        len({x[:2] for x in fingerprints}) != len(fingerprints)
        or sum(x[2] for x in fingerprints) != total_bytes
    ):
        raise MediaProcessingError("Carousel source files are duplicated or changed.")
    return paths, fingerprints


def _validate_probe(data):
    streams = data.get("streams")
    container = data.get("format")
    if (
        not isinstance(streams, list)
        or any(not isinstance(s, dict) for s in streams)
        or not isinstance(container, dict)
        or not isinstance(container.get("format_name"), str)
        or "mp4" not in container["format_name"].split(",")
    ):
        raise MediaProcessingError("Prepared carousel container/streams are invalid.")
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if (
        len(videos) != 1
        or videos[0].get("codec_name") != "h264"
        or any(s.get("codec_name") != "aac" for s in audio)
        or any(type(videos[0].get(k)) is not int or videos[0][k] <= 0 for k in ("width", "height"))
    ):
        raise MediaProcessingError("Prepared carousel codecs/dimensions are incompatible.")
    return telegram_video_upload_parameters(data)


def prepare_collection(payload, *, prepare=prepare_telegram_video):
    """Production implementation; callable injection is only for offline fixtures."""
    limits = CarouselDeliveryLimits(**payload["limits"])
    started = monotonic()
    workspace, private = Path(payload["workspace"]), Path(payload["private"])
    paths, fingerprints = _input_paths(
        payload["inputs"], workspace, private, payload["total_bytes"], limits
    )

    def check_free():
        if shutil.disk_usage(workspace).free < limits.min_free_bytes:
            raise _PreparationStopped

    check_free()
    used = _usage(workspace, limits)
    if shutil.disk_usage(workspace).free < min(
        limits.max_upload_total_bytes, limits.max_workspace_bytes - used
    ) + max(1024**2, limits.min_free_bytes):
        raise MediaProcessingError("Insufficient carousel preparation disk space.")
    result = []
    upload_bytes = 0

    def runner(command, **kwargs):
        check_free()
        remaining_time = limits.max_prepare_seconds - (monotonic() - started)
        if remaining_time <= 0:
            raise _PreparationStopped
        current = _usage(workspace, limits)
        command = [command[0], "-protocol_whitelist", "file,pipe", *command[1:]]
        if command[0] == "ffmpeg":
            remaining_bytes = min(
                limits.max_upload_file_bytes,
                limits.max_upload_total_bytes - upload_bytes,
                limits.max_workspace_bytes - current,
            )
            if remaining_bytes <= 0:
                raise _PreparationStopped
            # Unlike -fs, the OS backstop fails the write rather than accepting a
            # valid but shortened movie. An exhausted cap always stops this operation.
            resource.setrlimit(
                resource.RLIMIT_FSIZE, (remaining_bytes, limits.max_upload_file_bytes)
            )
        try:
            process = subprocess.run(command, timeout=remaining_time, **kwargs)
        except subprocess.TimeoutExpired:
            raise _PreparationStopped from None
        except subprocess.SubprocessError as error:
            if command[0] == "ffmpeg" and (
                getattr(error, "returncode", None) == -signal.SIGXFSZ
                or "file too large" in str(getattr(error, "stderr", "")).lower()
                or (
                    Path(command[-1]).is_file()
                    and Path(command[-1]).stat().st_size >= remaining_bytes
                )
            ):
                raise _PreparationStopped from None
            raise
        if command[0] == "ffmpeg" and Path(command[-1]).stat().st_size >= remaining_bytes:
            raise _PreparationStopped
        if process.stderr.strip():
            raise MediaProcessingError("Carousel preparation reported media errors.")
        check_free()
        _usage(workspace, limits)
        return process

    for index, source in enumerate(paths):
        extension = source.suffix.lower()
        if len(extension) > 16 or not extension[1:].isalnum():
            extension = ".bin"
        alias = private / f"input-{index:04d}{extension}"
        os.link(source, alias, follow_symlinks=False)
        prepared = prepare(alias, runner=runner, allow_silent=True)
        if prepared.parent != private:
            raise MediaProcessingError("Prepared carousel path escaped its workspace.")
        fingerprint = _fingerprint(prepared)
        data = inspect_telegram_video(prepared, runner=runner)
        parameters = _validate_probe(data)
        if fingerprint != _fingerprint(prepared):
            raise MediaProcessingError("Prepared carousel file changed while probing.")
        upload_bytes += fingerprint[2]
        if (
            fingerprint[2] > limits.max_upload_file_bytes
            or upload_bytes > limits.max_upload_total_bytes
        ):
            raise MediaProcessingError("Prepared carousel upload byte limit exceeded.")
        result.append({"name": prepared.name, "parameters": parameters, "fingerprint": fingerprint})
    if any(_fingerprint(path) != before for path, before in zip(paths, fingerprints, strict=True)):
        raise MediaProcessingError("Caller-owned carousel originals changed during preparation.")
    if (
        not math.isfinite(monotonic() - started)
        or monotonic() - started >= limits.max_prepare_seconds
    ):
        raise TimeoutError
    _usage(workspace, limits)
    return result


def main():
    try:
        payload = json.load(sys.stdin)
        limits = CarouselDeliveryLimits(**payload["limits"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.max_upload_file_bytes,) * 2)
        with (
            open(os.devnull, "w") as sink,
            contextlib.redirect_stdout(sink),
            contextlib.redirect_stderr(sink),
        ):
            result = prepare_collection(payload)
        print(json.dumps(result))
    except (Exception, _PreparationStopped):
        print(json.dumps({"error": "preparation_failed"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
