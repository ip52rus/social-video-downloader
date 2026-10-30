"""Request-owned SDK file iterators; transport return is not file-close evidence."""

import asyncio
from contextlib import suppress

from aiogram.types import FSInputFile

from social_video_downloader.domain.errors import DownloadCleanupError


class _Reader:
    def __init__(self, owner, source):
        self.owner = owner
        self.source = source
        self.pending = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.owner.closing:
            raise StopAsyncIteration
        if self.pending is not None and not self.pending.done():
            raise RuntimeError("Concurrent upload reads are not supported.")
        # Keep source I/O owned even if aiohttp cancels its consuming writer.
        self.pending = asyncio.create_task(anext(self.source))
        chunk = await asyncio.shield(self.pending)
        if self.owner.closing:
            raise StopAsyncIteration
        return chunk

    async def close(self):
        if self.pending is not None:
            # A read error still leaves the source responsible for its finally;
            # explicit aclose below must independently confirm source closure.
            with suppress(Exception):
                await self.pending
        await self.source.aclose()


class OwnedUploadFile(FSInputFile):
    """Stream SDK chunks, then confirm every source generator closed before exit."""

    def __init__(self, path):
        super().__init__(path)
        self.closing = False
        self._readers = []
        self._close_task = None

    def read(self, bot):
        if self.closing or self._readers:
            raise DownloadCleanupError("Upload file cannot be reused.")
        reader = _Reader(self, super().read(bot))
        self._readers.append(reader)
        return reader

    async def __aenter__(self):
        return self

    async def _finish(self):
        for reader in self._readers:
            await reader.close()

    async def __aexit__(self, *_):
        self.closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._finish())
        interrupted = False
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError:
                if self._close_task.cancelled():
                    break
                interrupted = True
            except Exception:
                break
        try:
            self._close_task.result()
        except (Exception, asyncio.CancelledError):
            raise DownloadCleanupError("Upload reader closure was not confirmed.") from None
        if interrupted:
            raise asyncio.CancelledError
