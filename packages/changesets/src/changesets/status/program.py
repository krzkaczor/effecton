"""The status flow: report pending changesets and the releases they produce."""

from pathlib import Path

import effecton as E
from changesets.shared import changeset, config, pyproject_version, repo, semver
from changesets.shared import file_system as FileSystem
from changesets.shared.release_plan import plan_releases

type StatusError = (
    repo.NotAChangesetRepo
    | config.ConfigError
    | changeset.ChangesetError
    | semver.InvalidVersion
    | pyproject_version.VersionLineError
    | FileSystem.FileSystemError
)


@E.gen
def status(start: Path) -> E.EffectGen[str, StatusError, FileSystem.Protocol]:
    root = yield from repo.find_root(start)
    cfg = yield from repo.load_config(root)
    changesets = yield from repo.load_changesets(root, cfg)

    if not changesets:
        return "No unreleased changesets found."
    releases = yield from plan_releases(root, cfg, changesets)
    lines = ["Planned releases:", ""]
    lines.extend(f"- {r.package}: {r.old} -> {r.new}" for r in releases)
    lines.extend(["", "Changesets:", ""])
    for c in changesets:
        bumps = ", ".join(f"{package} ({level})" for package, level in c.bumps.items())
        lines.append(f"- {c.path.name}: {bumps}")
    return "\n".join(lines)
