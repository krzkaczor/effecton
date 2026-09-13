"""Locate the changeset repo and load its config and pending changesets."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import final

import effecton as E
from changesets.shared import changeset, config
from changesets.shared.changeset import Changeset
from changesets.shared.config import Config

CHANGESET_DIR = ".changeset"
CONFIG_FILE = "config.toml"


@final
@dataclass(frozen=True)
class NotAChangesetRepo(E.EffectonError):
    start: E.Path

    def __str__(self) -> str:
        return f"No .changeset directory found in {self.start} or any parent"


def from_cwd[A, Err: E.EffectonError, R](
    program: Callable[[E.Path], E.Effect[A, Err, R]],
) -> E.Effect[A, Err, R | E.Process.Protocol]:
    """Start a program from the current directory, read through the Process."""
    return (
        E.require(E.Process.Protocol)
        .flat_map(lambda process: process.cwd())
        .flat_map(program)
    )


@E.gen
def find_root(
    start: E.Path,
) -> E.EffectGen[
    E.Path, NotAChangesetRepo | E.FileSystem.PermissionDenied, E.FileSystem.Protocol
]:
    fs = yield from E.require(E.FileSystem.Protocol)

    for candidate in (start, *start.parents):
        found = yield from fs.exists(candidate / CHANGESET_DIR)
        if found:
            return candidate
    return (yield from E.fail(NotAChangesetRepo(start=start)))


@E.gen
def load_config(
    root: E.Path,
) -> E.EffectGen[
    Config,
    config.ConfigError
    | E.FileSystem.FileNotFound
    | E.FileSystem.PermissionDenied
    | E.FileSystem.PathIsADirectory,
    E.FileSystem.Protocol,
]:
    fs = yield from E.require(E.FileSystem.Protocol)

    path = root / CHANGESET_DIR / CONFIG_FILE
    found = yield from fs.exists(path)
    if not found:
        return (yield from E.fail(config.MissingConfig(path=path)))
    text = yield from fs.read_file_string(path)
    return (yield from config.parse(path, text))


@E.gen
def load_changesets(
    root: E.Path, cfg: Config
) -> E.EffectGen[
    tuple[Changeset, ...],
    changeset.ChangesetError
    | E.FileSystem.FileNotFound
    | E.FileSystem.PermissionDenied
    | E.FileSystem.PathIsADirectory
    | E.FileSystem.PathIsNotADirectory,
    E.FileSystem.Protocol,
]:
    fs = yield from E.require(E.FileSystem.Protocol)

    entries = yield from fs.read_directory(root / CHANGESET_DIR)
    changesets: list[Changeset] = []
    for path in entries:
        if path.suffix != ".md":
            continue
        text = yield from fs.read_file_string(path)
        parsed = yield from changeset.parse(path, text, cfg.packages.keys())
        changesets.append(parsed)
    return tuple(changesets)
