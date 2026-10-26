"""Shared technical limits; independent of provider selection and HTTP policy."""

import shutil
from dataclasses import dataclass
from pathlib import Path

from social_video_downloader.domain.errors import MediaProcessingError

MIB = 1024**2
LOCAL_API_FILE_BYTES = 2_000_000_000
CLOUD_API_FILE_BYTES = 50_000_000


@dataclass(frozen=True, slots=True)
class DownloadLimits:
    max_file_bytes: int = 512 * MIB
    max_request_bytes: int = 1024 * MIB
    max_workspace_bytes: int = 3072 * MIB
    min_free_bytes: int = 512 * MIB

    def __post_init__(self):
        for value in (
            self.max_file_bytes,
            self.max_request_bytes,
            self.max_workspace_bytes,
            self.min_free_bytes,
        ):
            if type(value) is not int or not 0 < value <= 16 * 1024**3:
                raise ValueError("Download limits must be positive bounded integers.")
        if self.max_file_bytes > LOCAL_API_FILE_BYTES:
            raise ValueError("A file cannot exceed the Local Bot API ceiling.")
        if self.max_request_bytes < self.max_file_bytes:
            raise ValueError("Request budget must cover one file.")
        if self.max_workspace_bytes < self.max_request_bytes + self.max_file_bytes:
            raise ValueError("Workspace must cover acquired files and one prepared output.")

    def check_workspace(self, workspace: Path):
        if shutil.disk_usage(workspace).free < self.min_free_bytes:
            raise MediaProcessingError("Insufficient free disk reserve.")
        size = 0
        for entries, path in enumerate(workspace.rglob("*"), start=1):
            if entries > 256 or path.is_symlink():
                raise MediaProcessingError("Unsafe or excessive workspace entries.")
            if path.is_file():
                size += path.stat().st_size
            if size > self.max_workspace_bytes:
                raise MediaProcessingError("Workspace budget exceeded.")
        return size

    def check_file(self, path: Path):
        if (
            path.is_symlink()
            or not path.is_file()
            or not 0 < path.stat().st_size <= self.max_file_bytes
        ):
            raise MediaProcessingError("File exceeds the technical delivery limit.")
