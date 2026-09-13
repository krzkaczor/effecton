"""The `changeset notes` command."""

from typing import Annotated

import typer

import effecton as E
from changesets.notes.program import latest_notes
from changesets.shared import repo


def notes(
    package: Annotated[str, typer.Argument(help="Package to print notes for.")],
) -> None:
    """Print the latest released CHANGELOG section for a package."""
    section = E.run_main(
        repo.from_cwd(lambda cwd: latest_notes(cwd, package))
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
    )
    typer.echo(section, nl=False)
