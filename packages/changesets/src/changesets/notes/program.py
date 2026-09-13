"""The notes flow: extract the latest released changelog section."""

from dataclasses import dataclass
from typing import final

import effecton as E
from changesets.shared import changelog, config, repo


@final
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
    | E.FileSystem.FileNotFound
    | E.FileSystem.PermissionDenied
    | E.FileSystem.PathIsADirectory
)


@E.gen
def latest_notes(
    start: E.Path, package: str
) -> E.EffectGen[str, NotesError, E.FileSystem.Protocol]:
    fs = yield from E.require(E.FileSystem.Protocol)

    root = yield from repo.find_root(start)
    cfg = yield from repo.load_config(root)
    if package not in cfg.packages:
        config_path = root / repo.CHANGESET_DIR / repo.CONFIG_FILE
        error = config.UnknownPackage(path=config_path, package=package)
        return (yield from E.fail(error))

    changelog_path = root / cfg.packages[package] / "CHANGELOG.md"
    text = yield from fs.read_file_string(changelog_path).catch(
        E.FileSystem.FileNotFound
    )(lambda _: E.fail(NoReleasedVersion(package=package)))
    section = changelog.latest_section(text)
    match section:
        case None:
            return (yield from E.fail(NoReleasedVersion(package=package)))
        case _:
            return section
