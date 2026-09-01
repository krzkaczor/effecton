"""File-system service: Protocol plus Live (pathlib) and Test (in-memory).

Failures the program reacts to (a missing file, permissions, a directory
squatting where a file should be) are typed; everything else, such as
disk full or I/O errors, stays a defect.
"""

import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import runtime_checkable

import effecton as E


@dataclass(frozen=True)
class FileNotFound(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"File not found: {self.path}"


@dataclass(frozen=True)
class PermissionDenied(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"Permission denied: {self.path}"


@dataclass(frozen=True)
class PathIsADirectory(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"Can't read or write {self.path}: it is a directory"


type FileSystemError = FileNotFound | PermissionDenied | PathIsADirectory


@runtime_checkable
class Protocol(typing.Protocol):
    def exists(self, path: Path) -> E.Effect[bool, PermissionDenied]: ...

    def read_text(
        self, path: Path
    ) -> E.Effect[str, FileNotFound | PermissionDenied | PathIsADirectory]: ...

    def write_text(
        self, path: Path, content: str
    ) -> E.Effect[None, PermissionDenied | PathIsADirectory]: ...

    def list_markdown(
        self, directory: Path
    ) -> E.Effect[tuple[Path, ...], FileNotFound | PermissionDenied]: ...

    def delete(self, path: Path) -> E.Effect[None, FileNotFound | PermissionDenied]: ...


class Live(Protocol):
    def exists(self, path: Path) -> E.Effect[bool, PermissionDenied]:
        # lstat instead of Path.exists: exists() swallows every OSError as
        # False, which would report an unreadable path as absent.
        def go() -> bool:
            try:
                path.lstat()
            except FileNotFoundError, NotADirectoryError:
                return False
            return True

        def to_error(e: Exception) -> PermissionDenied:
            if isinstance(e, PermissionError):
                return PermissionDenied(path=path)
            raise e

        return E.attempt(go, to_error)

    def read_text(
        self, path: Path
    ) -> E.Effect[str, FileNotFound | PermissionDenied | PathIsADirectory]:
        def go() -> str:
            return path.read_text()

        def to_error(
            e: Exception,
        ) -> FileNotFound | PermissionDenied | PathIsADirectory:
            if isinstance(e, FileNotFoundError | NotADirectoryError):
                return FileNotFound(path=path)
            if isinstance(e, PermissionError):
                return PermissionDenied(path=path)
            if isinstance(e, IsADirectoryError):
                return PathIsADirectory(path=path)
            raise e

        return E.attempt(go, to_error)

    def write_text(
        self, path: Path, content: str
    ) -> E.Effect[None, PermissionDenied | PathIsADirectory]:
        def go() -> None:
            path.write_text(content)

        def to_error(e: Exception) -> PermissionDenied | PathIsADirectory:
            if isinstance(e, PermissionError):
                return PermissionDenied(path=path)
            if isinstance(e, IsADirectoryError):
                return PathIsADirectory(path=path)
            raise e

        return E.attempt(go, to_error)

    def list_markdown(
        self, directory: Path
    ) -> E.Effect[tuple[Path, ...], FileNotFound | PermissionDenied]:
        # iterdir instead of glob: glob suppresses OSError, which would
        # report a missing or unreadable directory as simply empty.
        def go() -> tuple[Path, ...]:
            return tuple(sorted(p for p in directory.iterdir() if p.suffix == ".md"))

        def to_error(e: Exception) -> FileNotFound | PermissionDenied:
            if isinstance(e, FileNotFoundError | NotADirectoryError):
                return FileNotFound(path=directory)
            if isinstance(e, PermissionError):
                return PermissionDenied(path=directory)
            raise e

        return E.attempt(go, to_error)

    def delete(self, path: Path) -> E.Effect[None, FileNotFound | PermissionDenied]:
        def go() -> None:
            path.unlink()

        def to_error(e: Exception) -> FileNotFound | PermissionDenied:
            if isinstance(e, FileNotFoundError | NotADirectoryError):
                return FileNotFound(path=path)
            if isinstance(e, PermissionError):
                return PermissionDenied(path=path)
            raise e

        return E.attempt(go, to_error)


@dataclass
class Test(Protocol):
    __test__ = False

    files: dict[Path, str] = field(default_factory=dict)
    dirs: set[Path] = field(default_factory=set)

    def exists(self, path: Path) -> E.Effect[bool]:
        return E.sync(lambda: path in self.files or path in self.dirs)

    @E.suspend
    def read_text(self, path: Path) -> E.Effect[str, FileNotFound]:
        if path not in self.files:
            return E.fail(FileNotFound(path=path))
        return E.success(self.files[path])

    def write_text(self, path: Path, content: str) -> E.Effect[None]:
        def go() -> None:
            self.files[path] = content

        return E.sync(go)

    def list_markdown(self, directory: Path) -> E.Effect[tuple[Path, ...]]:
        def go() -> tuple[Path, ...]:
            return tuple(
                sorted(
                    path
                    for path in self.files
                    if path.parent == directory and path.suffix == ".md"
                )
            )

        return E.sync(go)

    @E.suspend
    def delete(self, path: Path) -> E.Effect[None, FileNotFound]:
        if path not in self.files:
            return E.fail(FileNotFound(path=path))
        del self.files[path]
        return E.success(None)
