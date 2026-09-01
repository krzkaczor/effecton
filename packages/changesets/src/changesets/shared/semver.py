"""Strict X.Y.Z semver: parse, bump, and pick the strongest bump level."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import effecton as E

type Bump = Literal["major", "minor", "patch"]

BUMPS: tuple[Bump, ...] = ("major", "minor", "patch")

_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class InvalidVersion(E.EffectonError):
    package: str
    value: str

    def __str__(self) -> str:
        return f"Package {self.package} has version {self.value!r}, expected X.Y.Z"


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def parse(package: str, value: str) -> E.Effect[Version, InvalidVersion]:
    matched = _VERSION.fullmatch(value)
    if matched is None:
        return E.fail(InvalidVersion(package=package, value=value))
    major, minor, patch = matched.groups()

    return E.success(Version(major=int(major), minor=int(minor), patch=int(patch)))


def bump(version: Version, level: Bump) -> Version:
    match level:
        case "major":
            return Version(major=version.major + 1, minor=0, patch=0)
        case "minor":
            return Version(major=version.major, minor=version.minor + 1, patch=0)
        case "patch":
            return Version(
                major=version.major, minor=version.minor, patch=version.patch + 1
            )


def max_bump(levels: Iterable[Bump]) -> Bump:
    # BUMPS is ordered strongest-first, so the smallest index wins.
    return min(levels, key=BUMPS.index)
