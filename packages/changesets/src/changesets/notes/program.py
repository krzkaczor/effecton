"""The notes flow: extract the latest released changelog section."""

from dataclasses import dataclass
from pathlib import Path

import effecton as E
from changesets.shared import changelog, config, repo
from changesets.shared import file_system as FileSystem


@dataclass(frozen=True)
class NoReleasedVersion(E.EffectonError):
    package: str

    def __str__(self) -> str:
        return f"Package {self.package} has no released changelog section yet"


type NotesError = (
    repo.NotAChangesetRepo
    | config.ConfigError
    | config.UnknownPackage
    | NoReleasedVersion
    | FileSystem.FileSystemError
)


@E.gen
def latest_notes(
    start: Path, package: str
) -> E.EffectGen[str, NotesError, FileSystem.Protocol]:
    fs = yield from E.require(FileSystem.Protocol)

    root = yield from repo.find_root(start)
    cfg = yield from repo.load_config(root)
    if package not in cfg.packages:
        config_path = root / repo.CHANGESET_DIR / repo.CONFIG_FILE
        error = config.UnknownPackage(path=config_path, package=package)
        return (yield from E.fail(error))

    def missing_as_unreleased(
        error: FileSystem.FileSystemError,
    ) -> E.Effect[
        str,
        NoReleasedVersion | FileSystem.PermissionDenied | FileSystem.PathIsADirectory,
    ]:
        if isinstance(error, FileSystem.FileNotFound):
            return E.fail(NoReleasedVersion(package=package))
        return E.fail(error)

    changelog_path = root / cfg.packages[package] / "CHANGELOG.md"
    text = yield from fs.read_text(changelog_path).catch_all(missing_as_unreleased)
    section = changelog.latest_section(text)
    match section:
        case None:
            return (yield from E.fail(NoReleasedVersion(package=package)))
        case _:
            return section
