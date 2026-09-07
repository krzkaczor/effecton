"""The `changeset status` command."""

from pathlib import Path

import typer

import effecton as E
from changesets.shared import file_system as FileSystem
from changesets.status.program import status as status_program


def status() -> None:
    """Show pending changesets and the releases they would produce."""
    report = E.run_main(
        status_program(Path.cwd()).provide(FileSystem.Protocol)(FileSystem.Live())
    )
    typer.echo(report)
