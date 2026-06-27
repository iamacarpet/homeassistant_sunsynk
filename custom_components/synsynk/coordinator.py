"""File watcher coordinator using Linux inotify (no external dependencies)."""
from __future__ import annotations

import asyncio
import ctypes
import ctypes.util
import json
import logging
import os
import struct
from collections.abc import Callable
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# inotify event mask bits
_IN_CLOSE_WRITE = 0x00000008
_IN_MOVED_TO = 0x00000080
_IN_CREATE = 0x00000100

# inotify_event header: int wd, uint32 mask, uint32 cookie, uint32 len
_EVENT_FMT = "iIII"
_EVENT_HEADER_SIZE = struct.calcsize(_EVENT_FMT)

_WATCH_MASK = _IN_CLOSE_WRITE | _IN_MOVED_TO | _IN_CREATE

_RETRY_INTERVAL = 30  # seconds between retries when directory is unavailable

_libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


def _inotify_init1() -> int:
    fd = _libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    if fd < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    return fd


def _inotify_add_watch(fd: int, path: str, mask: int) -> int:
    wd = _libc.inotify_add_watch(fd, path.encode(), mask)
    if wd < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    return wd


def _inotify_rm_watch(fd: int, wd: int) -> None:
    _libc.inotify_rm_watch(fd, wd)


def _read_events(fd: int) -> list[tuple[int, int, int, str]]:
    """Drain inotify fd and return list of (wd, mask, cookie, name) tuples."""
    try:
        data = os.read(fd, 65536)
    except BlockingIOError:
        return []

    events: list[tuple[int, int, int, str]] = []
    offset = 0
    while offset + _EVENT_HEADER_SIZE <= len(data):
        wd, mask, cookie, name_len = struct.unpack_from(_EVENT_FMT, data, offset)
        offset += _EVENT_HEADER_SIZE
        name = ""
        if name_len:
            raw = data[offset : offset + name_len]
            name = raw.rstrip(b"\x00").decode(errors="replace")
            offset += name_len
        events.append((wd, mask, cookie, name))
    return events


class SynsynkCoordinator:
    """Reads solar.status via inotify and notifies subscribed entities."""

    def __init__(self, hass, file_path: str) -> None:
        self.hass = hass
        self.file_path = file_path
        self.data: dict = {}
        self._listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task | None = None

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to data updates. Returns an unsubscribe callable."""
        self._listeners.append(listener)

        def _remove() -> None:
            self._listeners.remove(listener)

        return _remove

    def _notify_listeners(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Error notifying listener")

    async def async_setup(self) -> None:
        self._task = asyncio.create_task(self._watch_forever())

    async def async_shutdown(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _load_file(self) -> None:
        """Read and parse the status file, notifying listeners on success."""
        loop = asyncio.get_running_loop()
        try:
            content = await loop.run_in_executor(None, Path(self.file_path).read_text)
            self.data = json.loads(content)
            self._notify_listeners()
        except FileNotFoundError:
            pass
        except Exception as exc:
            _LOGGER.error("Error reading %s: %s", self.file_path, exc)

    async def _watch_forever(self) -> None:
        """Outer loop: restart the watcher on unexpected errors."""
        while True:
            try:
                await self._watch_loop()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _LOGGER.error(
                    "Inotify watcher crashed (%s), restarting in %ds",
                    exc,
                    _RETRY_INTERVAL,
                )
                await asyncio.sleep(_RETRY_INTERVAL)

    async def _watch_loop(self) -> None:
        """
        Watch the parent directory for writes/renames/creates of the target
        filename.  This handles both direct writes (IN_CLOSE_WRITE) and atomic
        rename-into-place (IN_MOVED_TO), and waits for the file to appear if
        it doesn't exist yet (IN_CREATE).
        """
        file_path = Path(self.file_path)
        parent = str(file_path.parent)
        filename = file_path.name

        # Attempt an initial load in case the file already exists.
        await self._load_file()

        fd = _inotify_init1()
        loop = asyncio.get_running_loop()
        try:
            try:
                wd = _inotify_add_watch(fd, parent, _WATCH_MASK)
            except OSError as exc:
                _LOGGER.warning(
                    "Cannot watch %s: %s — retrying in %ds", parent, exc, _RETRY_INTERVAL
                )
                await asyncio.sleep(_RETRY_INTERVAL)
                return

            _LOGGER.debug("Watching %s for changes to %s", parent, filename)

            ev = asyncio.Event()
            loop.add_reader(fd, ev.set)
            try:
                while True:
                    await ev.wait()
                    ev.clear()
                    for _wd, mask, _cookie, name in _read_events(fd):
                        if name == filename and (mask & _WATCH_MASK):
                            await self._load_file()
            finally:
                loop.remove_reader(fd)
                _inotify_rm_watch(fd, wd)
        finally:
            os.close(fd)
