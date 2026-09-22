"""The `changeset version` command."""

import effecton as E
from changesets.shared import git as Git
from changesets.shared import repo
from changesets.version.program import ApplyError, apply_versions

Cli = E.Cli


@E.gen
def run_version() -> E.EffectGen[
    None, ApplyError, E.FileSystem.Protocol | E.Process.Protocol
]:
    releases = yield from repo.from_cwd(
        lambda cwd: apply_versions(cwd).provide(Git.Protocol)(Git.Live(cwd=cwd))
    )
    if not releases:
        yield from E.sync(lambda: print("No unreleased changesets found."))
        return
    for release in releases:
        yield from E.sync(
            lambda release=release: print(
                f"{release.package}: {release.old} -> {release.new}"
            )
        )


version = Cli.command(
    "version",
    handler=run_version,
    help="Apply pending changesets: bump versions and update changelogs.",
)
