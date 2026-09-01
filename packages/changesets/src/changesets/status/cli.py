"""The `changeset status` command."""

from pathlib import Path

import typer

from changesets.shared import file_system as FileSystem
from changesets.shared.runner import execute
from changesets.status.program import status as status_program


def status() -> None:
    """Show pending changesets and the releases they would produce."""
    report = execute(
        status_program(Path.cwd()).provide(FileSystem.Protocol)(FileSystem.Live())
    )
    typer.echo(report)
