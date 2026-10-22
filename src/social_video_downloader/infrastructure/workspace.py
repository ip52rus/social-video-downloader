"""Temporary workspace management for media processing."""

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp

from social_video_downloader.domain.errors import DownloadCleanupError


@contextmanager
def temporary_workspace(
    *,
    base_dir: Path | None = None,
) -> Iterator[Path]:
    """Yield an isolated temporary directory and remove it on exit.

    If ``base_dir`` is provided, the workspace is created inside that
    existing directory. The base directory itself is never removed.
    """
    with TemporaryDirectory(
        prefix="social-video-downloader-",
        dir=base_dir,
    ) as temporary_directory:
        yield Path(temporary_directory)


@contextmanager
def quarantinable_workspace(*, base_dir: Path | None = None) -> Iterator[Path]:
    """Opt-in owned workspace: uncertain worker ownership must never delete its files."""
    workspace = Path(mkdtemp(prefix="social-video-downloader-", dir=base_dir))
    try:
        yield workspace
    except DownloadCleanupError:
        raise  # No finalizer: preserve this directory and every potentially owned file.
    except BaseException:
        try:
            shutil.rmtree(workspace)
        except OSError:
            raise DownloadCleanupError("Owned workspace cleanup failed.") from None
        raise
    else:
        try:
            shutil.rmtree(workspace)
        except OSError:
            raise DownloadCleanupError("Owned workspace cleanup failed.") from None
