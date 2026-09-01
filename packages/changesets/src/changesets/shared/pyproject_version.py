"""Find and rewrite the `version = "..."` line of a pyproject.toml.

Targeted string replacement instead of a TOML round-trip so every other
byte of the file is preserved. Exactly one match is required: zero means
the package has no static version, more than one means we cannot tell
which one is the project version.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import effecton as E

_VERSION_LINE = re.compile(r'^version = "(?P<version>[^"]*)"$', re.MULTILINE)


@dataclass(frozen=True)
class MissingVersionLine(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f'No version = "..." line found in {self.path}'


@dataclass(frozen=True)
class AmbiguousVersionLine(E.EffectonError):
    path: Path

    def __str__(self) -> str:
        return f'More than one version = "..." line found in {self.path}'


type VersionLineError = MissingVersionLine | AmbiguousVersionLine


def _match_version_line(
    path: Path, text: str
) -> E.Effect[re.Match[str], VersionLineError]:
    matches = list(_VERSION_LINE.finditer(text))
    if not matches:
        return E.fail(MissingVersionLine(path=path))
    if len(matches) > 1:
        return E.fail(AmbiguousVersionLine(path=path))

    return E.success(matches[0])


def read_version(path: Path, text: str) -> E.Effect[str, VersionLineError]:
    return _match_version_line(path, text).map(lambda m: m.group("version"))


def replace_version(
    path: Path, text: str, new_version: str
) -> E.Effect[str, VersionLineError]:
    def splice(matched: re.Match[str]) -> str:
        line = f'version = "{new_version}"'
        return text[: matched.start()] + line + text[matched.end() :]

    return _match_version_line(path, text).map(splice)
