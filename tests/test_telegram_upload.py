"""Failure injection at the file-owner boundary, separate from SDK transport tests."""

import asyncio

import pytest
from aiogram.types import FSInputFile

from social_video_downloader.domain.errors import DownloadCleanupError
from social_video_downloader.infrastructure.telegram_upload import OwnedUploadFile


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [OSError, asyncio.CancelledError])
async def test_unconfirmed_source_close_is_typed_and_private(monkeypatch, tmp_path, failure):
    class Source:
        async def __anext__(self):
            return b"synthetic chunk"

        async def aclose(self):
            raise failure("synthetic private close detail")

    monkeypatch.setattr(FSInputFile, "read", lambda self, bot: Source())
    upload = OwnedUploadFile(tmp_path / "synthetic.mp4")
    reader = upload.read(None)
    assert await anext(reader) == b"synthetic chunk"
    with pytest.raises(DownloadCleanupError, match="closure was not confirmed") as caught:
        await upload.__aexit__(None, None, None)
    assert "private" not in str(caught.value)
    # A closed/uncertain owner must never reopen the source for an automatic replay.
    with pytest.raises(DownloadCleanupError):
        upload.read(None)
    assert upload._close_task.done()
