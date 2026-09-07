"""The `changeset notes` command."""

from pathlib import Path
from typing import Annotated

import typer

import effecton as E
from changesets.notes.program import latest_notes
from changesets.shared import file_system as FileSystem


def notes(
    package: Annotated[str, typer.Argument(help="Package to print notes for.")],
) -> None:
    """Print the latest released CHANGELOG section for a package."""
    section = E.run_main(
        latest_notes(Path.cwd(), package).provide(FileSystem.Protocol)(
            FileSystem.Live()
        )
    )
    typer.echo(section, nl=False)
