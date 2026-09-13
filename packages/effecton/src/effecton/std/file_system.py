"""FileSystem service: Protocol plus SyncLive, AsyncLive and an in-memory Test.

Paths are E.Path values, and this module is the only place where they
touch the disk. SyncLive calls the os-level standard library (os.*, open)
and blocks the thread, so it suits run_sync; AsyncLive makes the same
calls through aiofiles, so the loop keeps turning under run_async and
run_main. Both share one error mapping: the failures a program reacts to
(a missing file, permissions, a directory where a file should be and the
reverse, a path already taken, a directory that is not empty) are typed,
and everything else, such as disk full or an I/O error, stays a defect.
Test keeps the tree in dicts and enforces the same rules, so a program
sees the same Exit whichever implementation it runs against.

Naming follows Effect-TS's FileSystem with these deliberate differences:
read_directory returns full paths rather than names, exists does not
follow symlinks (a dangling link exists), symlink takes (target, link)
like os.symlink; the working and home directories are read through the
Process service, since a Path has no way to reach the environment.
"""

import errno
import os
import shutil
import typing
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from stat import S_ISDIR, S_ISLNK, S_ISREG
from typing import Literal, final, runtime_checkable

import aiofiles
import aiofiles.os

from effecton.attempt import attempt, attempt_async
from effecton.effect import Effect, EffectonError, die, fail, success, sync
from effecton.std.path import Path
from effecton.suspend import suspend


@final
@dataclass(frozen=True)
class FileNotFound(EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"File not found: {self.path}"


@final
@dataclass(frozen=True)
class PermissionDenied(EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"Permission denied: {self.path}"


@final
@dataclass(frozen=True)
class PathIsADirectory(EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"{self.path} is a directory"


@final
@dataclass(frozen=True)
class PathIsNotADirectory(EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"{self.path} is not a directory"


@final
@dataclass(frozen=True)
class PathAlreadyExists(EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"{self.path} already exists"


@final
@dataclass(frozen=True)
class DirectoryNotEmpty(EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"Directory not empty: {self.path}"


type FileSystemError = (
    FileNotFound
    | PermissionDenied
    | PathIsADirectory
    | PathIsNotADirectory
    | PathAlreadyExists
    | DirectoryNotEmpty
)

type StatError = FileNotFound | PermissionDenied
type ReadError = FileNotFound | PermissionDenied | PathIsADirectory
type WriteError = (
    FileNotFound | PermissionDenied | PathIsADirectory | PathIsNotADirectory
)
type MakeDirectoryError = (
    FileNotFound | PermissionDenied | PathAlreadyExists | PathIsNotADirectory
)
type ReadDirectoryError = FileNotFound | PermissionDenied | PathIsNotADirectory
type RemoveError = FileNotFound | PermissionDenied | DirectoryNotEmpty
type RenameError = (
    FileNotFound
    | PermissionDenied
    | PathIsADirectory
    | PathIsNotADirectory
    | DirectoryNotEmpty
)
type CopyFileError = FileNotFound | PermissionDenied | PathIsADirectory
type SymlinkError = (
    FileNotFound | PermissionDenied | PathAlreadyExists | PathIsNotADirectory
)

type FileType = Literal["file", "directory", "symlink", "other"]


@final
@dataclass(frozen=True)
class FileInfo:
    """What lstat reports about a path: the entry itself, not a link's target."""

    type: FileType
    size: int
    modified_at: datetime


@runtime_checkable
class Protocol(typing.Protocol):
    def exists(self, path: Path) -> Effect[bool, PermissionDenied]:
        """Whether the entry exists; a dangling symlink counts."""
        ...

    def stat(self, path: Path) -> Effect[FileInfo, StatError]: ...

    def read_file(self, path: Path) -> Effect[bytes, ReadError]: ...

    def read_file_string(
        self, path: Path, encoding: str = "utf-8"
    ) -> Effect[str, ReadError]:
        """The file decoded; undecodable bytes are a defect."""
        ...

    def write_file(self, path: Path, content: bytes) -> Effect[None, WriteError]:
        """Create or overwrite the file; the parent directory must exist."""
        ...

    def write_file_string(
        self, path: Path, content: str, encoding: str = "utf-8"
    ) -> Effect[None, WriteError]: ...

    def make_directory(
        self, path: Path, *, recursive: bool = False
    ) -> Effect[None, MakeDirectoryError]:
        """Create the directory; recursive also creates parents and accepts
        an existing directory, while a file at the path is PathAlreadyExists
        either way."""
        ...

    def read_directory(
        self, path: Path
    ) -> Effect[tuple[Path, ...], ReadDirectoryError]:
        """The entries as full paths, sorted."""
        ...

    def remove(
        self, path: Path, *, recursive: bool = False
    ) -> Effect[None, RemoveError]:
        """Remove a file, a symlink (never its target) or a directory, which
        must be empty unless recursive."""
        ...

    def rename(self, old: Path, new: Path) -> Effect[None, RenameError]:
        """Move an entry, replacing a file or an empty directory at new."""
        ...

    def copy_file(self, src: Path, dst: Path) -> Effect[None, CopyFileError]: ...

    def symlink(self, target: Path, link: Path) -> Effect[None, SymlinkError]:
        """Create link pointing at target, which need not exist."""
        ...

    def read_link(self, link: Path) -> Effect[Path, StatError]:
        """The target a symlink points at; a non-link is a defect."""
        ...


@final
@dataclass(frozen=True)
class SyncLive(Protocol):
    """The real file system through blocking os calls; suits run_sync."""

    def exists(self, path: Path) -> Effect[bool, PermissionDenied]:
        # lstat instead of os.path.exists: exists() swallows every OSError
        # as False, which would report an unreadable path as absent.
        def go() -> bool:
            try:
                os.lstat(str(path))
            except FileNotFoundError, NotADirectoryError:
                return False
            return True

        return attempt(go, _exists_error(path))

    def stat(self, path: Path) -> Effect[FileInfo, StatError]:
        return attempt(lambda: _file_info(os.lstat(str(path))), _stat_error(path))

    def read_file(self, path: Path) -> Effect[bytes, ReadError]:
        def go() -> bytes:
            with open(str(path), "rb") as f:
                return f.read()

        return attempt(go, _read_error(path))

    def read_file_string(
        self, path: Path, encoding: str = "utf-8"
    ) -> Effect[str, ReadError]:
        def go() -> str:
            with open(str(path), encoding=encoding) as f:
                return f.read()

        return attempt(go, _read_error(path))

    def write_file(self, path: Path, content: bytes) -> Effect[None, WriteError]:
        def go() -> None:
            with open(str(path), "wb") as f:
                f.write(content)

        return attempt(go, _write_error(path))

    def write_file_string(
        self, path: Path, content: str, encoding: str = "utf-8"
    ) -> Effect[None, WriteError]:
        def go() -> None:
            with open(str(path), "w", encoding=encoding) as f:
                f.write(content)

        return attempt(go, _write_error(path))

    def make_directory(
        self, path: Path, *, recursive: bool = False
    ) -> Effect[None, MakeDirectoryError]:
        def go() -> None:
            if recursive:
                os.makedirs(str(path), exist_ok=True)
            else:
                os.mkdir(str(path))

        return attempt(go, _make_directory_error(path))

    def read_directory(
        self, path: Path
    ) -> Effect[tuple[Path, ...], ReadDirectoryError]:
        # listdir instead of glob: glob suppresses OSError, which would
        # report a missing or unreadable directory as simply empty.
        def go() -> tuple[Path, ...]:
            return tuple(sorted(path / name for name in os.listdir(str(path))))

        return attempt(go, _read_directory_error(path))

    def remove(
        self, path: Path, *, recursive: bool = False
    ) -> Effect[None, RemoveError]:
        # Dispatch on the entry kind rather than on exceptions: unlinking a
        # directory raises EPERM on macOS, which would read as a permission
        # problem, and rmtree follows nothing, so a link to a directory is
        # only ever unlinked.
        def go() -> None:
            if S_ISDIR(os.lstat(str(path)).st_mode):
                if recursive:
                    shutil.rmtree(str(path))
                else:
                    os.rmdir(str(path))
            else:
                os.unlink(str(path))

        return attempt(go, _remove_error(path))

    def rename(self, old: Path, new: Path) -> Effect[None, RenameError]:
        return attempt(lambda: os.replace(str(old), str(new)), _rename_error(old, new))

    def copy_file(self, src: Path, dst: Path) -> Effect[None, CopyFileError]:
        def go() -> None:
            shutil.copyfile(str(src), str(dst))

        return attempt(go, _copy_error(src))

    def symlink(self, target: Path, link: Path) -> Effect[None, SymlinkError]:
        return attempt(lambda: os.symlink(str(target), str(link)), _symlink_error(link))

    def read_link(self, link: Path) -> Effect[Path, StatError]:
        return attempt(lambda: Path(os.readlink(str(link))), _stat_error(link))


@final
@dataclass(frozen=True)
class AsyncLive(Protocol):
    """The real file system through aiofiles; suits run_async and run_main.

    Every call awaits aiofiles' twin of the os call SyncLive makes, so the
    loop keeps turning while a worker thread does the I/O. Under run_sync
    the effects die with AsyncEffectInSyncRun, like any coroutine effect;
    a cancellation abandons the blocking call in its thread rather than
    aborting it.
    """

    def exists(self, path: Path) -> Effect[bool, PermissionDenied]:
        async def go() -> bool:
            try:
                await aiofiles.os.stat(str(path), follow_symlinks=False)
            except FileNotFoundError, NotADirectoryError:
                return False
            return True

        return attempt_async(go, _exists_error(path))

    def stat(self, path: Path) -> Effect[FileInfo, StatError]:
        async def go() -> FileInfo:
            return _file_info(await aiofiles.os.stat(str(path), follow_symlinks=False))

        return attempt_async(go, _stat_error(path))

    def read_file(self, path: Path) -> Effect[bytes, ReadError]:
        async def go() -> bytes:
            async with aiofiles.open(str(path), "rb") as f:
                return await f.read()

        return attempt_async(go, _read_error(path))

    def read_file_string(
        self, path: Path, encoding: str = "utf-8"
    ) -> Effect[str, ReadError]:
        async def go() -> str:
            async with aiofiles.open(str(path), encoding=encoding) as f:
                return await f.read()

        return attempt_async(go, _read_error(path))

    def write_file(self, path: Path, content: bytes) -> Effect[None, WriteError]:
        async def go() -> None:
            async with aiofiles.open(str(path), "wb") as f:
                await f.write(content)

        return attempt_async(go, _write_error(path))

    def write_file_string(
        self, path: Path, content: str, encoding: str = "utf-8"
    ) -> Effect[None, WriteError]:
        async def go() -> None:
            async with aiofiles.open(str(path), "w", encoding=encoding) as f:
                await f.write(content)

        return attempt_async(go, _write_error(path))

    def make_directory(
        self, path: Path, *, recursive: bool = False
    ) -> Effect[None, MakeDirectoryError]:
        async def go() -> None:
            if recursive:
                await aiofiles.os.makedirs(str(path), exist_ok=True)
            else:
                await aiofiles.os.mkdir(str(path))

        return attempt_async(go, _make_directory_error(path))

    def read_directory(
        self, path: Path
    ) -> Effect[tuple[Path, ...], ReadDirectoryError]:
        async def go() -> tuple[Path, ...]:
            names = await aiofiles.os.listdir(str(path))
            return tuple(sorted(path / name for name in names))

        return attempt_async(go, _read_directory_error(path))

    def remove(
        self, path: Path, *, recursive: bool = False
    ) -> Effect[None, RemoveError]:
        async def go() -> None:
            info = await aiofiles.os.stat(str(path), follow_symlinks=False)
            if S_ISDIR(info.st_mode):
                if recursive:
                    await aiofiles.os.wrap(shutil.rmtree)(str(path))
                else:
                    await aiofiles.os.rmdir(str(path))
            else:
                await aiofiles.os.unlink(str(path))

        return attempt_async(go, _remove_error(path))

    def rename(self, old: Path, new: Path) -> Effect[None, RenameError]:
        async def go() -> None:
            await aiofiles.os.replace(str(old), str(new))

        return attempt_async(go, _rename_error(old, new))

    def copy_file(self, src: Path, dst: Path) -> Effect[None, CopyFileError]:
        async def go() -> None:
            await aiofiles.os.wrap(shutil.copyfile)(str(src), str(dst))

        return attempt_async(go, _copy_error(src))

    def symlink(self, target: Path, link: Path) -> Effect[None, SymlinkError]:
        async def go() -> None:
            await aiofiles.os.symlink(str(target), str(link))

        return attempt_async(go, _symlink_error(link))

    def read_link(self, link: Path) -> Effect[Path, StatError]:
        async def go() -> Path:
            return Path(await aiofiles.os.readlink(str(link)))

        return attempt_async(go, _stat_error(link))


_ROOT = Path("/")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MAX_LINK_HOPS = 40


@final
@dataclass
class Test(Protocol):
    """An in-memory tree that follows the real rules.

    Seed it with files (text or bytes), directories and links; every
    ancestor of a seeded path is created too, and the root always exists.
    Operations then enforce what the disk would: a parent must exist and be
    a directory, a directory must be empty to go, and so on, so a program
    gets the same Exit here as against a Live. Content operations follow a
    symlink at the final component (a dangling one is FileNotFound); exists,
    stat, remove, rename and read_link act on the link itself, and links in
    the middle of a path are not resolved. modified_at is always the epoch.
    """

    files: dict[Path, bytes | str] = field(default_factory=dict)
    directories: set[Path] = field(default_factory=set)
    links: dict[Path, Path] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.directories.add(_ROOT)
        for path in (*self.files, *self.directories, *self.links):
            self.directories.update(path.parents)

    def exists(self, path: Path) -> Effect[bool]:
        return sync(lambda: self._kind(path) is not None)

    @suspend
    def stat(self, path: Path) -> Effect[FileInfo, StatError]:
        kind = self._kind(path)
        if kind is None:
            return fail(FileNotFound(path=path))
        size = len(self._bytes(path)) if kind == "file" else 0
        return success(FileInfo(type=kind, size=size, modified_at=_EPOCH))

    @suspend
    def read_file(self, path: Path) -> Effect[bytes, ReadError]:
        target = self._resolve(path)
        match self._kind(target):
            case None:
                return fail(FileNotFound(path=path))
            case "directory":
                return fail(PathIsADirectory(path=path))
            case _:
                return success(self._bytes(target))

    @suspend
    def read_file_string(
        self, path: Path, encoding: str = "utf-8"
    ) -> Effect[str, ReadError]:
        def decode(content: bytes | str) -> str:
            return content if isinstance(content, str) else content.decode(encoding)

        target = self._resolve(path)
        return self.read_file(path).map(lambda _: decode(self.files[target]))

    @suspend
    def write_file(self, path: Path, content: bytes) -> Effect[None, WriteError]:
        return self._write(path, content)

    @suspend
    def write_file_string(
        self, path: Path, content: str, encoding: str = "utf-8"
    ) -> Effect[None, WriteError]:
        stored = content if encoding == "utf-8" else content.encode(encoding)
        return self._write(path, stored)

    @suspend
    def make_directory(
        self, path: Path, *, recursive: bool = False
    ) -> Effect[None, MakeDirectoryError]:
        if recursive:
            if self._kind(self._resolve(path)) == "directory":
                return success(None)
            if self._kind(path) is not None:
                return fail(PathAlreadyExists(path=path))
            if any(self._kind(p) not in (None, "directory") for p in path.parents):
                return fail(PathIsNotADirectory(path=path))
            self.directories.update((path, *path.parents))
            return success(None)
        if self._kind(path) is not None:
            return fail(PathAlreadyExists(path=path))
        if (error := self._parent_error(path)) is not None:
            return fail(error)
        self.directories.add(path)
        return success(None)

    @suspend
    def read_directory(
        self, path: Path
    ) -> Effect[tuple[Path, ...], ReadDirectoryError]:
        target = self._resolve(path)
        match self._kind(target):
            case None:
                return fail(FileNotFound(path=path))
            case "directory":
                children = (e.name for e in self._entries() if e.parent == target)
                return success(tuple(sorted(path / name for name in children)))
            case _:
                return fail(PathIsNotADirectory(path=path))

    @suspend
    def remove(
        self, path: Path, *, recursive: bool = False
    ) -> Effect[None, RemoveError]:
        match self._kind(path):
            case None:
                return fail(FileNotFound(path=path))
            case "directory":
                inside = [e for e in self._entries() if path in e.parents]
                if inside and not recursive:
                    return fail(DirectoryNotEmpty(path=path))
                for entry in inside:
                    self._discard(entry)
                self.directories.discard(path)
            case _:
                self._discard(path)
        return success(None)

    @suspend
    def rename(self, old: Path, new: Path) -> Effect[None, RenameError]:
        old_kind = self._kind(old)
        if old_kind is None:
            return fail(FileNotFound(path=old))
        if (error := self._parent_error(new)) is not None:
            return fail(error)
        new_kind = self._kind(new)
        if old_kind == "directory":
            if new_kind in ("file", "symlink"):
                return fail(PathIsNotADirectory(path=new))
            if new_kind == "directory":
                if any(new in e.parents for e in self._entries()):
                    return fail(DirectoryNotEmpty(path=new))
                self.directories.discard(new)
        elif new_kind == "directory":
            return fail(PathIsADirectory(path=new))
        elif new_kind is not None:
            self._discard(new)
        moved = [e for e in self._entries() if e == old or old in e.parents]
        for entry in moved:
            relocated = new / Path(*entry.parts[len(old.parts) :])
            if entry in self.files:
                self.files[relocated] = self.files.pop(entry)
            elif entry in self.links:
                self.links[relocated] = self.links.pop(entry)
            else:
                self.directories.discard(entry)
                self.directories.add(relocated)
        return success(None)

    @suspend
    def copy_file(self, src: Path, dst: Path) -> Effect[None, CopyFileError]:
        source = self._resolve(src)
        match self._kind(source):
            case None:
                return fail(FileNotFound(path=src))
            case "directory":
                return fail(PathIsADirectory(path=src))
            case _:
                return self._write(dst, self.files[source]).catch(PathIsNotADirectory)(
                    lambda e: die(e)
                )

    @suspend
    def symlink(self, target: Path, link: Path) -> Effect[None, SymlinkError]:
        if self._kind(link) is not None:
            return fail(PathAlreadyExists(path=link))
        if (error := self._parent_error(link)) is not None:
            return fail(error)
        self.links[link] = target
        return success(None)

    @suspend
    def read_link(self, link: Path) -> Effect[Path, StatError]:
        match self._kind(link):
            case None:
                return fail(FileNotFound(path=link))
            case "symlink":
                return success(self.links[link])
            case _:
                return die(OSError(errno.EINVAL, "Not a symbolic link", str(link)))

    def _write(self, path: Path, content: bytes | str) -> Effect[None, WriteError]:
        target = self._resolve(path)
        if self._kind(target) == "directory":
            return fail(PathIsADirectory(path=path))
        if (error := self._parent_error(target, reported=path)) is not None:
            return fail(error)
        self.files[target] = content
        return success(None)

    def _parent_error(
        self, path: Path, reported: Path | None = None
    ) -> FileNotFound | PathIsNotADirectory | None:
        match self._kind(path.parent):
            case "directory":
                return None
            case None:
                return FileNotFound(path=reported or path)
            case _:
                return PathIsNotADirectory(path=reported or path)

    def _kind(self, path: Path) -> FileType | None:
        if path in self.links:
            return "symlink"
        if path in self.directories:
            return "directory"
        if path in self.files:
            return "file"
        return None

    def _resolve(self, path: Path) -> Path:
        for _ in range(_MAX_LINK_HOPS):
            if path not in self.links:
                return path
            path = path.parent / self.links[path]
        raise OSError(errno.ELOOP, "Too many levels of symbolic links", str(path))

    def _bytes(self, path: Path) -> bytes:
        content = self.files[path]
        return content if isinstance(content, bytes) else content.encode()

    def _entries(self) -> list[Path]:
        return [*self.files, *self.directories, *self.links]

    def _discard(self, path: Path) -> None:
        self.files.pop(path, None)
        self.links.pop(path, None)
        self.directories.discard(path)


def _file_info(result: os.stat_result) -> FileInfo:
    mode = result.st_mode
    if S_ISLNK(mode):
        kind: FileType = "symlink"
    elif S_ISDIR(mode):
        kind = "directory"
    elif S_ISREG(mode):
        kind = "file"
    else:
        kind = "other"
    modified_at = datetime.fromtimestamp(result.st_mtime, UTC)
    return FileInfo(type=kind, size=result.st_size, modified_at=modified_at)


def _exists_error(path: Path) -> Callable[[Exception], PermissionDenied]:
    def to_error(e: Exception) -> PermissionDenied:
        if isinstance(e, PermissionError):
            return PermissionDenied(path=path)
        raise e

    return to_error


def _stat_error(path: Path) -> Callable[[Exception], StatError]:
    def to_error(e: Exception) -> StatError:
        if isinstance(e, FileNotFoundError | NotADirectoryError):
            return FileNotFound(path=path)
        if isinstance(e, PermissionError):
            return PermissionDenied(path=path)
        raise e

    return to_error


def _read_error(path: Path) -> Callable[[Exception], ReadError]:
    def to_error(e: Exception) -> ReadError:
        if isinstance(e, FileNotFoundError | NotADirectoryError):
            return FileNotFound(path=path)
        if isinstance(e, PermissionError):
            return PermissionDenied(path=path)
        if isinstance(e, IsADirectoryError):
            return PathIsADirectory(path=path)
        raise e

    return to_error


def _write_error(path: Path) -> Callable[[Exception], WriteError]:
    def to_error(e: Exception) -> WriteError:
        if isinstance(e, FileNotFoundError):
            return FileNotFound(path=path)
        if isinstance(e, NotADirectoryError):
            return PathIsNotADirectory(path=path)
        if isinstance(e, PermissionError):
            return PermissionDenied(path=path)
        if isinstance(e, IsADirectoryError):
            return PathIsADirectory(path=path)
        raise e

    return to_error


def _make_directory_error(path: Path) -> Callable[[Exception], MakeDirectoryError]:
    def to_error(e: Exception) -> MakeDirectoryError:
        if isinstance(e, FileExistsError):
            return PathAlreadyExists(path=path)
        if isinstance(e, FileNotFoundError):
            return FileNotFound(path=path)
        if isinstance(e, NotADirectoryError):
            return PathIsNotADirectory(path=path)
        if isinstance(e, PermissionError):
            return PermissionDenied(path=path)
        raise e

    return to_error


def _read_directory_error(path: Path) -> Callable[[Exception], ReadDirectoryError]:
    def to_error(e: Exception) -> ReadDirectoryError:
        if isinstance(e, FileNotFoundError):
            return FileNotFound(path=path)
        if isinstance(e, NotADirectoryError):
            return PathIsNotADirectory(path=path)
        if isinstance(e, PermissionError):
            return PermissionDenied(path=path)
        raise e

    return to_error


def _remove_error(path: Path) -> Callable[[Exception], RemoveError]:
    def to_error(e: Exception) -> RemoveError:
        if isinstance(e, FileNotFoundError | NotADirectoryError):
            return FileNotFound(path=path)
        if isinstance(e, PermissionError):
            return PermissionDenied(path=path)
        if _is_not_empty(e):
            return DirectoryNotEmpty(path=path)
        raise e

    return to_error


def _rename_error(old: Path, new: Path) -> Callable[[Exception], RenameError]:
    # os.replace reports both names on every failure, so a missing source
    # and a missing destination parent look alike; the source is checked to
    # tell them apart.
    def to_error(e: Exception) -> RenameError:
        if isinstance(e, FileNotFoundError):
            return FileNotFound(path=old if not os.path.lexists(str(old)) else new)
        if isinstance(e, IsADirectoryError):
            return PathIsADirectory(path=new)
        if isinstance(e, NotADirectoryError):
            return PathIsNotADirectory(path=new)
        if isinstance(e, PermissionError):
            return PermissionDenied(path=Path(e.filename) if e.filename else old)
        if _is_not_empty(e):
            return DirectoryNotEmpty(path=new)
        raise e

    return to_error


def _copy_error(src: Path) -> Callable[[Exception], CopyFileError]:
    # copyfile opens each side in turn, so the exception names the side
    # that failed.
    def to_error(e: Exception) -> CopyFileError:
        failed = Path(e.filename) if isinstance(e, OSError) and e.filename else src
        if isinstance(e, FileNotFoundError | NotADirectoryError):
            return FileNotFound(path=failed)
        if isinstance(e, PermissionError):
            return PermissionDenied(path=failed)
        if isinstance(e, IsADirectoryError):
            return PathIsADirectory(path=failed)
        raise e

    return to_error


def _symlink_error(link: Path) -> Callable[[Exception], SymlinkError]:
    def to_error(e: Exception) -> SymlinkError:
        if isinstance(e, FileExistsError):
            return PathAlreadyExists(path=link)
        if isinstance(e, FileNotFoundError):
            return FileNotFound(path=link)
        if isinstance(e, NotADirectoryError):
            return PathIsNotADirectory(path=link)
        if isinstance(e, PermissionError):
            return PermissionDenied(path=link)
        raise e

    return to_error


def _is_not_empty(e: Exception) -> bool:
    return isinstance(e, OSError) and e.errno in (errno.ENOTEMPTY, errno.EEXIST)
