"""Temporary workspace management for media processing."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory


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
