"""Private YouTube write boundary. Global file hooks exist only in an owned child."""

import builtins
import errno
import io
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import RLock

from social_video_downloader.resource_limits import DownloadLimits

_ACTIVE = ContextVar("youtube_write_budget", default=None)
_OPEN = builtins.open
_IO_OPEN = io.open
_OS_OPEN = os.open
_OS_WRITE = os.write
_FTRUNCATE = os.ftruncate
_TRUNCATE = os.truncate


class BudgetExceeded(BaseException):
    """A sticky resource stop must bypass yt-dlp retries and preparation fallback."""


class _Writer:
    def __init__(self, stream, budget, path, append=False):
        self._stream, self._budget, self._path, self._append = stream, budget, path, append

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self._stream.__exit__(*args)

    def write(self, data):
        raw = data.encode(self._stream.encoding or "utf-8") if isinstance(data, str) else data
        with self._budget.lock:
            size = os.fstat(self._stream.fileno()).st_size
            offset = size if self._append else self._stream.tell()
            self._budget.before_growth(self._path, max(size, offset + len(raw)))
            try:
                result = self._stream.write(data)
                self._stream.flush()  # Make accounting exact before another writer is admitted.
                return result
            except OSError as error:
                if error.errno in {errno.ENOSPC, errno.EFBIG, errno.EDQUOT}:
                    self._budget.stop()
                raise

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def truncate(self, size=None):
        size = self._stream.tell() if size is None else size
        with self._budget.lock:
            self._budget.before_growth(self._path, size)
            return self._budget.resource_io(self._stream.truncate, size)


class YouTubeWriteBudget:
    def __init__(self, workspace, limits):
        self.workspace = Path(workspace).resolve(strict=True)
        self.limits = limits
        self.lock = RLock()
        self.network_bytes = 0
        self._fds = {}
        self.control = self.workspace / ".youtube-resource-control"
        self.control.mkdir(mode=0o700, exist_ok=True)
        self.marker = self.control / "stopped"
        if not self.marker.exists():
            with _OPEN(self.marker, "wb") as stream:
                stream.write(b"0")
        self.config = self.control / "limits.json"
        from dataclasses import asdict

        self.config.write_text(
            json.dumps({"workspace": str(self.workspace), "limits": asdict(limits)})
        )
        self.executables = self.control / "bin"
        self.executables.mkdir(mode=0o700, exist_ok=True)
        for name in ("ffmpeg", "ffprobe"):
            binary = shutil.which(name)
            if binary is None:
                continue  # Preserve the existing missing-binary refusal.
            wrapper = self.executables / name
            wrapper.write_text(
                f"#!{sys.executable}\n"
                "from social_video_downloader.infrastructure.youtube_write_budget "
                "import exec_tool\n"
                f"exec_tool({str(self.config)!r}, {binary!r})\n"
            )
            wrapper.chmod(0o700)

    def check(self):
        with _OPEN(self.marker, "rb") as stream:
            if stream.read(1) != b"0":
                raise BudgetExceeded

    def stop(self):
        with _OPEN(self.marker, "r+b", buffering=0) as stream:
            stream.write(b"1")
        raise BudgetExceeded

    def owned(self, value):
        if isinstance(value, int):
            saved = self._fds.get(value)
            if saved is None:
                return None
            path, identity, _ = saved
            try:
                info = os.fstat(value)
            except OSError:
                return None
            return path if (info.st_dev, info.st_ino) == identity else None
        try:
            path = Path(os.fsdecode(value))
        except TypeError:
            return None
        if not path.is_absolute():
            path = Path.cwd() / path
        # Refuse lexical escapes and symlinks without following an unbounded parent loop.
        lexical_owner = path.is_relative_to(self.workspace)
        path = Path(os.path.abspath(path))
        if not path.is_relative_to(self.workspace):
            if lexical_owner:
                self.stop()
            return None
        parent = path
        while parent != self.workspace:
            if parent.is_symlink():
                self.stop()
            parent = parent.parent
        if not path.resolve().is_relative_to(self.workspace):
            self.stop()
        return path

    def usage(self):
        total, inodes, entries = 0, set(), 0
        for directory, dirs, files in os.walk(self.workspace, followlinks=False):
            entries += len(dirs) + len(files)
            if entries > 256:
                self.stop()
            for name in dirs + files:
                path = Path(directory) / name
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    self.stop()
                if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) not in inodes:
                    inodes.add((info.st_dev, info.st_ino))
                    total += info.st_size
        return total

    def before_growth(self, path, end):
        self.check()
        size = path.stat().st_size if path.exists() else 0
        growth = max(0, end - size)
        if (
            end > self.limits.max_file_bytes
            or self.usage() + growth > self.limits.max_workspace_bytes
            or shutil.disk_usage(self.workspace).free - growth < self.limits.min_free_bytes
        ):
            self.stop()

    def open(self, original, value, mode="r", *args, **kwargs):
        path = self.owned(value)
        writing = any(c in mode for c in "wax+")
        with self.lock:
            if path is not None and writing:
                self.check()
                self.before_growth(path, 0)
            stream = original(value, mode, *args, **kwargs)
            if path is not None and writing:
                return _Writer(stream, self, path, append="a" in mode)
            return stream

    def os_open(self, value, flags, mode=0o777, *, dir_fd=None):
        # yt-dlp/tempfile use absolute paths; no relative-dir-fd write bypass.
        if dir_fd is not None and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            self.stop()
        path = self.owned(value)
        if path is not None and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            self.before_growth(path, 0)
        fd = _OS_OPEN(value, flags, mode, dir_fd=dir_fd)
        if path is not None:
            info = os.fstat(fd)
            self._fds[fd] = (path, (info.st_dev, info.st_ino), bool(flags & os.O_APPEND))
        return fd

    def resource_io(self, function, *args):
        try:
            return function(*args)
        except OSError as error:
            if error.errno in {errno.ENOSPC, errno.EFBIG, errno.EDQUOT}:
                self.stop()
            raise

    def os_write(self, fd, data):
        path = self.owned(fd)
        with self.lock:
            if path is not None:
                size = os.fstat(fd).st_size
                offset = size if self._fds[fd][2] else os.lseek(fd, 0, os.SEEK_CUR)
                self.before_growth(path, max(size, offset + len(data)))
            return self.resource_io(_OS_WRITE, fd, data)

    def ftruncate(self, fd, size):
        path = self.owned(fd)
        with self.lock:
            if path is not None:
                self.before_growth(path, size)
            return self.resource_io(_FTRUNCATE, fd, size)

    def truncate(self, value, size):
        path = self.owned(value)
        with self.lock:
            if path is not None:
                self.before_growth(path, size)
            return self.resource_io(_TRUNCATE, value, size)

    def wrap_response(self, response):
        original = response.read

        def read(amt=None):
            size = -1 if amt is None else amt
            chunks = []
            while True:
                with self.lock:
                    self.check()
                    remaining = self.limits.max_request_bytes - self.network_bytes
                    amount = min(64 * 1024, max(1, remaining + 1), size if size >= 0 else 64 * 1024)
                    chunk = original(amount)
                    if (
                        len(chunk) > amount
                        or self.network_bytes + len(chunk) > self.limits.max_request_bytes
                    ):
                        response.close()
                        self.stop()
                    self.network_bytes += len(chunk)
                chunks.append(chunk)
                if size >= 0 or not chunk:
                    return b"".join(chunks)

        response.read = read
        return response

    @contextmanager
    def install_in_child(self):
        """Never called in the polling process or its executor threads."""
        token = _ACTIVE.set(self)
        builtins.open = lambda *a, **kw: self.open(_OPEN, *a, **kw)
        io.open = lambda *a, **kw: self.open(_IO_OPEN, *a, **kw)
        os.open, os.write = self.os_open, self.os_write
        os.ftruncate, os.truncate = self.ftruncate, self.truncate
        try:
            yield
            self.check()
        finally:
            builtins.open, io.open = _OPEN, _IO_OPEN
            os.open, os.write = _OS_OPEN, _OS_WRITE
            os.ftruncate, os.truncate = _FTRUNCATE, _TRUNCATE
            _ACTIVE.reset(token)

    def run(self, command, **kwargs):
        """Same preparation commands, with a bounded/reaped FFmpeg writer."""
        self.check()
        argv = command
        if Path(command[0]).name in {"ffmpeg", "ffprobe"}:
            wrapper = self.executables / Path(command[0]).name
            if wrapper.exists():
                argv = [str(wrapper), *command[1:]]
        try:
            result = subprocess.run(argv, **kwargs)
        except subprocess.SubprocessError:
            self.check()  # Resource failures bypass helper conversion fallback.
            raise
        self.check()
        return result


def guarded_options(options):
    budget = _ACTIVE.get()
    return {**options, "ffmpeg_location": str(budget.executables)} if budget else options


def guard_ydl(ydl):
    budget = _ACTIVE.get()
    if budget is None:
        return ydl
    original = ydl.urlopen

    def urlopen(*args, **kwargs):
        budget.check()  # A resource failure cannot authorize another HTTP attempt.
        return budget.wrap_response(original(*args, **kwargs))

    ydl.urlopen = urlopen
    return ydl


def exec_tool(config, binary):
    """Fresh single-purpose supervisor; never detach FFmpeg from its owner's group."""
    import resource

    with _OPEN(config) as stream:
        data = json.load(stream)
    workspace = Path(data["workspace"])
    limits = DownloadLimits(**data["limits"])
    marker = Path(config).parent / "stopped"

    def stopped():
        with _OPEN(marker, "r+b", buffering=0) as stream:
            stream.write(b"1")
        raise SystemExit(86)

    with _OPEN(marker, "rb") as stream:
        if stream.read(1) != b"0":
            stopped()
    # Version/capability probes and ffprobe are read-only, but still inherit an OS cap.
    read_only = (
        Path(binary).name == "ffprobe" or "-version" in sys.argv[1:] or "-bsfs" in sys.argv[1:]
    )
    inodes, used = set(), 0
    for directory, _, files in os.walk(workspace):
        for name in files:
            info = (Path(directory) / name).lstat()
            if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) not in inodes:
                inodes.add((info.st_dev, info.st_ino))
                used += info.st_size
    allowance = min(
        limits.max_file_bytes,
        limits.max_workspace_bytes - used,
        shutil.disk_usage(workspace).free - limits.min_free_bytes,
    )
    if not read_only and allowance <= 0:
        stopped()
    allowance = max(1, allowance)
    resource.setrlimit(resource.RLIMIT_FSIZE, (allowance, allowance))
    # Inherit stdio verbatim; no headers/URLs or response text are emitted by this code.
    process = subprocess.Popen([binary, *sys.argv[1:]])
    try:
        result = process.wait()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    exhausted = (
        result == -signal.SIGXFSZ or shutil.disk_usage(workspace).free < limits.min_free_bytes
    )
    if not read_only:
        # All current selected-format merge/fixup and Telegram preparation commands
        # write one local output; never accept an OS-truncated but playable movie.
        output = sys.argv[-1].removeprefix("file:")
        target = Path(output)
        exhausted = exhausted or (target.is_file() and target.stat().st_size >= allowance)
    if exhausted:
        stopped()
    raise SystemExit(result if result >= 0 else 1)
