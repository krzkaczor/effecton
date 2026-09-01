"""The `changeset add` command."""

from pathlib import Path
from typing import Annotated

import typer

from changesets.add import name_generator as NameGenerator
from changesets.add.program import add_changeset
from changesets.shared import file_system as FileSystem
from changesets.shared.runner import execute
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

    path = execute(
        add_changeset(Path.cwd(), package, level, message)
        .provide(FileSystem.Protocol)(FileSystem.Live())
        .provide(NameGenerator.Protocol)(NameGenerator.Live())
    )
    typer.echo(f"Created {path}")
