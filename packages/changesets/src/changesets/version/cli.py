"""The `changeset version` command."""

from pathlib import Path

import typer

from changesets.shared import file_system as FileSystem
from changesets.shared.runner import execute
from changesets.version.program import apply_versions


def version() -> None:
    """Apply pending changesets: bump versions and update changelogs."""
    releases = execute(
        apply_versions(Path.cwd()).provide(FileSystem.Protocol)(FileSystem.Live())
    )
    if not releases:
        typer.echo("No unreleased changesets found.")
        return
    for release in releases:
        typer.echo(f"{release.package}: {release.old} -> {release.new}")
