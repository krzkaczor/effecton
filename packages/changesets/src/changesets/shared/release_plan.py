"""Compute the releases a set of pending changesets produces."""

from dataclasses import dataclass

import effecton as E
from changesets.shared import pyproject_version, semver
from changesets.shared.changeset import Changeset
from changesets.shared.config import Config
from changesets.shared.semver import Version


@dataclass(frozen=True)
class Release:
    package: str
    old: Version
    new: Version


@E.gen
def plan_releases(
    root: E.Path, cfg: Config, changesets: tuple[Changeset, ...]
) -> E.EffectGen[
    tuple[Release, ...],
    semver.InvalidVersion
    | pyproject_version.VersionLineError
    | E.FileSystem.FileNotFound
    | E.FileSystem.PermissionDenied
    | E.FileSystem.PathIsADirectory,
    E.FileSystem.Protocol,
]:
    fs = yield from E.require(E.FileSystem.Protocol)

    releases: list[Release] = []
    for package in sorted(cfg.packages):
        levels = [c.bumps[package] for c in changesets if package in c.bumps]
        if not levels:
            continue
        pyproject_path = root / cfg.packages[package] / "pyproject.toml"
        text = yield from fs.read_file_string(pyproject_path)
        current_text = yield from pyproject_version.read_version(pyproject_path, text)
        current = yield from semver.parse(package, current_text)
        new = semver.bump(current, semver.max_bump(levels))
        releases.append(Release(package=package, old=current, new=new))
    return tuple(releases)
