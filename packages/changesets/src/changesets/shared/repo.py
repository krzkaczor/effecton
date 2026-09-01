"""Locate the changeset repo and load its config and pending changesets."""

from dataclasses import dataclass
from pathlib import Path

import effecton as E
from changesets.shared import changeset, config
from changesets.shared import file_system as FileSystem
from changesets.shared.changeset import Changeset
from changesets.shared.config import Config

CHANGESET_DIR = ".changeset"
CONFIG_FILE = "config.toml"


@dataclass(frozen=True)
class NotAChangesetRepo(E.EffectonError):
    start: Path

    def __str__(self) -> str:
        return f"No .changeset directory found in {self.start} or any parent"


@E.gen
def find_root(
    start: Path,
) -> E.EffectGen[
    Path, NotAChangesetRepo | FileSystem.PermissionDenied, FileSystem.Protocol
]:
    fs = yield from E.require(FileSystem.Protocol)

    for candidate in (start, *start.parents):
        found = yield from fs.exists(candidate / CHANGESET_DIR)
        if found:
            return candidate
    return (yield from E.fail(NotAChangesetRepo(start=start)))


@E.gen
def load_config(
    root: Path,
) -> E.EffectGen[
    Config, config.ConfigError | FileSystem.FileSystemError, FileSystem.Protocol
]:
    fs = yield from E.require(FileSystem.Protocol)

    path = root / CHANGESET_DIR / CONFIG_FILE
    found = yield from fs.exists(path)
    if not found:
        return (yield from E.fail(config.MissingConfig(path=path)))
    text = yield from fs.read_text(path)
    return (yield from config.parse(path, text))


@E.gen
def load_changesets(
    root: Path, cfg: Config
) -> E.EffectGen[
    tuple[Changeset, ...],
    changeset.ChangesetError | FileSystem.FileSystemError,
    FileSystem.Protocol,
]:
    fs = yield from E.require(FileSystem.Protocol)

    paths = yield from fs.list_markdown(root / CHANGESET_DIR)
    changesets: list[Changeset] = []
    for path in paths:
        text = yield from fs.read_text(path)
        parsed = yield from changeset.parse(path, text, cfg.packages.keys())
        changesets.append(parsed)
    return tuple(changesets)
