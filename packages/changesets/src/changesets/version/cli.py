"""The `changeset version` command."""

import typer

import effecton as E
from changesets.shared import git as Git
from changesets.shared import repo
from changesets.version.program import apply_versions


def version() -> None:
    """Apply pending changesets: bump versions and update changelogs."""
    releases = E.run_main(
        repo.from_cwd(
            lambda cwd: apply_versions(cwd).provide(Git.Protocol)(Git.Live(cwd=cwd))
        )
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
    )
    if not releases:
        typer.echo("No unreleased changesets found.")
        return
    for release in releases:
        typer.echo(f"{release.package}: {release.old} -> {release.new}")
