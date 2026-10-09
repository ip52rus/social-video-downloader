"""Tests for temporary workspace lifecycle."""

from pathlib import Path

import pytest

from social_video_downloader.infrastructure.workspace import temporary_workspace


def test_workspace_exists_during_context_and_is_removed_afterward() -> None:
    workspace_path: Path

    with temporary_workspace() as workspace:
        workspace_path = workspace
        assert workspace.is_dir()

        media_file = workspace / "video.mp4"
        media_file.write_bytes(b"test media")
        assert media_file.is_file()

    assert not workspace_path.exists()


def test_workspace_is_removed_when_an_exception_occurs() -> None:
    workspace_path: Path

    with pytest.raises(RuntimeError, match="processing failed"), temporary_workspace() as workspace:
        workspace_path = workspace
        (workspace / "partial.mp4").write_bytes(b"partial")
        raise RuntimeError("processing failed")

    assert not workspace_path.exists()


def test_workspace_is_created_inside_base_directory(tmp_path: Path) -> None:
    with temporary_workspace(base_dir=tmp_path) as workspace:
        assert workspace.is_dir()
        assert workspace.parent == tmp_path
        assert workspace.name.startswith("social-video-downloader-")

    assert tmp_path.is_dir()
    assert list(tmp_path.iterdir()) == []


def test_each_workspace_has_a_separate_directory() -> None:
    with temporary_workspace() as first, temporary_workspace() as second:
        assert first != second
        assert first.is_dir()
        assert second.is_dir()
