"""Path: an immutable path value with no I/O on it.

A Path is pure data: it joins with /, compares, hashes, sorts and exposes
its pieces (parent, parents, name, suffix, stem, parts), and nothing else.
Every read of or write to the file system goes through the FileSystem
service, so a Path can never reach the disk on its own. It wraps the
standard library's PurePath, so joining and normalization follow the
platform's rules exactly: an absolute right-hand side replaces the left,
and redundant separators and single dots collapse.
"""

import pathlib
from dataclasses import dataclass
from typing import final


@final
@dataclass(frozen=True, init=False, repr=False)
class Path:
    _pure: pathlib.PurePath

    def __init__(self, *segments: str) -> None:
        object.__setattr__(self, "_pure", pathlib.PurePath(*segments))

    def __truediv__(self, other: str | Path) -> Path:
        tail = other._pure if isinstance(other, Path) else other
        return _wrap(self._pure / tail)

    def __lt__(self, other: Path) -> bool:
        return self._pure < other._pure

    def __str__(self) -> str:
        return str(self._pure)

    def __repr__(self) -> str:
        return f"Path({str(self._pure)!r})"

    @property
    def parent(self) -> Path:
        """The directory holding this path; the root is its own parent."""
        return _wrap(self._pure.parent)

    @property
    def parents(self) -> tuple[Path, ...]:
        """Every ancestor, nearest first; empty for the root."""
        return tuple(_wrap(parent) for parent in self._pure.parents)

    @property
    def name(self) -> str:
        return self._pure.name

    @property
    def suffix(self) -> str:
        return self._pure.suffix

    @property
    def stem(self) -> str:
        return self._pure.stem

    @property
    def parts(self) -> tuple[str, ...]:
        return self._pure.parts


def _wrap(pure: pathlib.PurePath) -> Path:
    path = object.__new__(Path)
    object.__setattr__(path, "_pure", pure)
    return path
