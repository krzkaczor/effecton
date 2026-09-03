"""File-system service: Protocol plus Live (pathlib) and Test (in-memory).

Failures a user can act on (permissions, a file squatting where a
directory or symlink should go) are typed; everything else, such as disk
full or I/O errors, stays a defect. ``exists`` does not follow symlinks,
so a dangling symlink counts as existing; the symlink-skipping check in
the program relies on this.
"""

import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import runtime_checkable

import effecton as E


@dataclass(frozen=True)
class PermissionDenied(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"Permission denied: {self.path}"


@dataclass(frozen=True)
class PathIsNotADirectory(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"{self.path} exists but is not a directory"


@dataclass(frozen=True)
class PathIsADirectory(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"Can't write {self.path}: it is a directory"


@dataclass(frozen=True)
class PathAlreadyExists(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f"Can't create symlink {self.path}: it already exists"


type FileSystemError = (
    PermissionDenied | PathIsNotADirectory | PathIsADirectory | PathAlreadyExists
)


@runtime_checkable
class Protocol(typing.Protocol):
    def exists(self, path: Path) -> E.Effect[bool, PermissionDenied]: ...

    def mkdir(
        self, path: Path
    ) -> E.Effect[None, PermissionDenied | PathIsNotADirectory]: ...

    def write_text(
        self, path: Path, content: str
    ) -> E.Effect[None, PermissionDenied | PathIsADirectory]: ...

    def symlink(
        self, link: Path, target: Path
    ) -> E.Effect[None, PermissionDenied | PathAlreadyExists]: ...


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

    def mkdir(
        self, path: Path
    ) -> E.Effect[None, PermissionDenied | PathIsNotADirectory]:
        def go() -> None:
            path.mkdir(parents=True, exist_ok=True)

        def to_error(e: Exception) -> PermissionDenied | PathIsNotADirectory:
            if isinstance(e, PermissionError):
                return PermissionDenied(path=path)
            # exist_ok only suppresses FileExistsError when the existing
            # path is a directory; NotADirectoryError means a parent is a
            # file.
            if isinstance(e, FileExistsError | NotADirectoryError):
                return PathIsNotADirectory(path=path)
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

    def symlink(
        self, link: Path, target: Path
    ) -> E.Effect[None, PermissionDenied | PathAlreadyExists]:
        def go() -> None:
            link.symlink_to(target, target_is_directory=True)

        def to_error(e: Exception) -> PermissionDenied | PathAlreadyExists:
            if isinstance(e, PermissionError):
                return PermissionDenied(path=link)
            if isinstance(e, FileExistsError):
                return PathAlreadyExists(path=link)
            raise e

        return E.attempt(go, to_error)


@dataclass
class Test(Protocol):
    __test__ = False

    files: dict[Path, str] = field(default_factory=dict)
    dirs: set[Path] = field(default_factory=set)
    links: dict[Path, Path] = field(default_factory=dict)

    def exists(self, path: Path) -> E.Effect[bool]:
        return E.sync(
            lambda: path in self.files or path in self.dirs or path in self.links
        )

    def mkdir(self, path: Path) -> E.Effect[None]:
        def go() -> None:
            self.dirs.add(path)

        return E.sync(go)

    def write_text(self, path: Path, content: str) -> E.Effect[None]:
        def go() -> None:
            self.files[path] = content

        return E.sync(go)

    def symlink(self, link: Path, target: Path) -> E.Effect[None]:
        def go() -> None:
            self.links[link] = target

        return E.sync(go)
