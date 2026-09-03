"""The version flow: apply pending changesets to versions and changelogs."""

from pathlib import Path

import effecton as E
from changesets.shared import (
    changelog,
    changeset,
    config,
    github,
    pyproject_version,
    repo,
    semver,
)
from changesets.shared import file_system as FileSystem
from changesets.shared import git as Git
from changesets.shared.release_plan import Release, plan_releases

type ApplyError = (
    repo.NotAChangesetRepo
    | config.ConfigError
    | changeset.ChangesetError
    | semver.InvalidVersion
    | pyproject_version.VersionLineError
    | FileSystem.FileSystemError
    | Git.GitError
    | github.NotAGitHubRemote
)


@E.gen
def apply_versions(
    start: Path,
) -> E.EffectGen[tuple[Release, ...], ApplyError, FileSystem.Protocol | Git.Protocol]:
    fs = yield from E.require(FileSystem.Protocol)
    git = yield from E.require(Git.Protocol)

    root = yield from repo.find_root(start)
    cfg = yield from repo.load_config(root)
    changesets = yield from repo.load_changesets(root, cfg)
    if not changesets:
        return ()

    def missing_as_absent(
        error: FileSystem.FileSystemError,
    ) -> E.Effect[
        str | None, FileSystem.PermissionDenied | FileSystem.PathIsADirectory
    ]:
        if isinstance(error, FileSystem.FileNotFound):
            return E.success(None)
        return E.fail(error)

    # Resolve PR links before any write, and before the changeset files are
    # deleted, since git history is queried by path.
    remote = yield from git.remote_url("origin")
    repository = yield from github.parse_repository(remote)
    pull_requests: dict[Path, github.PullRequest] = {}
    for c in changesets:
        subject = yield from git.added_in(c.path)
        number = github.pull_request_number(subject) if subject else None
        if number is not None:
            pull_requests[c.path] = github.PullRequest(repository, number)

    releases = yield from plan_releases(root, cfg, changesets)
    for release in releases:
        package_dir = root / cfg.packages[release.package]
        pyproject_path = package_dir / "pyproject.toml"
        text = yield from fs.read_text(pyproject_path)
        updated = yield from pyproject_version.replace_version(
            pyproject_path, text, str(release.new)
        )
        yield from fs.write_text(pyproject_path, updated)

        section = changelog.render_section(
            release.package, release.new, changesets, pull_requests
        )
        changelog_path = package_dir / "CHANGELOG.md"
        existing = yield from fs.read_text(changelog_path).catch_all(missing_as_absent)
        yield from fs.write_text(
            changelog_path, changelog.prepend(release.package, existing, section)
        )
        yield from E.log_info("Bumped:", release.package, str(release.new))

    for c in changesets:
        yield from fs.delete(c.path)
    return releases
