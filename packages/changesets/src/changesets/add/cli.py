"""The `changeset add` command."""

from typing import Annotated

import typer

import effecton as E
from changesets.add import name_generator as NameGenerator
from changesets.add.program import add_changeset
from changesets.shared import repo
from changesets.shared.semver import Bump


def add(
    package: Annotated[str, typer.Option(help="Package the change belongs to.")],
    bump: Annotated[str, typer.Option(help="major, minor, or patch.")],
    message: Annotated[str, typer.Option(help="Changelog entry for the change.")],
) -> None:
    """Create a changeset from the given package, bump level, and message."""
    level: Bump
    match bump:
        case "major" | "minor" | "patch":
            level = bump
        case _:
            error_text = (
                f"Invalid bump level {bump!r}: expected major, minor, or patch."
            )
            typer.echo(error_text, err=True)
            raise typer.Exit(code=2)
    if not message.strip():
        typer.echo("The message must not be empty.", err=True)
        raise typer.Exit(code=2)

    path = E.run_main(
        repo.from_cwd(lambda cwd: add_changeset(cwd, package, level, message))
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
        .provide(NameGenerator.Protocol)(NameGenerator.Live())
    )
    typer.echo(f"Created {path}")
