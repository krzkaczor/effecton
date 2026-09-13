"""The `changeset status` command."""

import typer

import effecton as E
from changesets.shared import repo
from changesets.status.program import status as status_program


def status() -> None:
    """Show pending changesets and the releases they would produce."""
    report = E.run_main(
        repo.from_cwd(status_program)
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
    )
    typer.echo(report)
