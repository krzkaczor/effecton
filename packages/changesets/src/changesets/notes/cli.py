"""The `changeset notes` command."""

from pathlib import Path
from typing import Annotated

import typer

from changesets.notes.program import latest_notes
from changesets.shared import file_system as FileSystem
from changesets.shared.runner import execute


def notes(
    package: Annotated[str, typer.Argument(help="Package to print notes for.")],
) -> None:
    """Print the latest released CHANGELOG section for a package."""
    section = execute(
        latest_notes(Path.cwd(), package).provide(FileSystem.Protocol)(
            FileSystem.Live()
        )
    )
    typer.echo(section, nl=False)
