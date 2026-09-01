"""Typer entry point: assemble one CLI from the per-command modules."""

import typer

from changesets.add.cli import add
from changesets.notes.cli import notes
from changesets.status.cli import status
from changesets.version.cli import version

app = typer.Typer(help="Changeset-based changelog and version management.")
app.command()(add)
app.command()(status)
app.command()(version)
app.command()(notes)


def run() -> None:
    app()
