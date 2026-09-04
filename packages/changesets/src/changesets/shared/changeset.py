"""Parse and serialize a single .changeset/*.md file.

A changeset is markdown with YAML frontmatter mapping package names to
bump levels, and a body describing the change:

    ---
    effecton: minor
    ---

    Add `E.retry` combinator.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import final

import frontmatter
import yaml

import effecton as E
from changesets.shared.config import UnknownPackage
from changesets.shared.semver import Bump


@final
@dataclass(frozen=True)
class MalformedChangeset(E.EffectonError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"Invalid changeset {self.path}: {self.reason}"


@final
@dataclass(frozen=True)
class InvalidBumpLevel(E.EffectonError):
    path: Path
    value: str

    def __str__(self) -> str:
        return (
            f"Invalid bump level {self.value!r} in {self.path}: "
            "expected major, minor, or patch"
        )


type ChangesetError = MalformedChangeset | UnknownPackage | InvalidBumpLevel


@dataclass(frozen=True)
class Changeset:
    path: Path
    bumps: Mapping[str, Bump]
    summary: str


def parse(
    path: Path, text: str, known_packages: Collection[str]
) -> E.Effect[Changeset, ChangesetError]:
    def load() -> frontmatter.Post:
        return frontmatter.loads(text)

    def to_error(e: Exception) -> MalformedChangeset:
        if isinstance(e, yaml.YAMLError):
            return MalformedChangeset(path=path, reason=str(e))
        raise e

    def validate(post: frontmatter.Post) -> E.Effect[Changeset, ChangesetError]:
        if not post.metadata:
            reason = "frontmatter lists no packages"
            return E.fail(MalformedChangeset(path=path, reason=reason))
        bumps: dict[str, Bump] = {}
        for package, level in post.metadata.items():
            if package not in known_packages:
                return E.fail(UnknownPackage(path=path, package=str(package)))
            match level:
                case "major":
                    bumps[str(package)] = "major"
                case "minor":
                    bumps[str(package)] = "minor"
                case "patch":
                    bumps[str(package)] = "patch"
                case _:
                    return E.fail(InvalidBumpLevel(path=path, value=str(level)))
        return E.success(
            Changeset(path=path, bumps=bumps, summary=post.content.strip())
        )

    return E.attempt(load, to_error).flat_map(validate)


def serialize(bumps: Mapping[str, Bump], summary: str) -> str:
    lines = "\n".join(f"{package}: {level}" for package, level in sorted(bumps.items()))

    return f"---\n{lines}\n---\n\n{summary}\n"
