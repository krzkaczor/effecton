"""The ``api-reference`` command: render the page for the docs site."""

from typing import Annotated

import typer

import effecton as E
from api_reference import collect
from api_reference.program import write_reference
from api_reference.topics import TOPICS

app = typer.Typer(help="Render the docs API Reference page from the effecton sources.")


@app.command()
def generate(
    out: Annotated[
        str, typer.Option(help="Where to write the page, relative to the cwd.")
    ] = "docs/src/pages/api.md",
) -> None:
    """Render the API Reference page from the effecton sources."""
    path = E.run_main(
        E.sync(collect.load)
        .flat_map(lambda root: collect.collect(root, TOPICS))
        .flat_map(lambda reference: write_reference(E.Path(out), reference))
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
    )
    typer.echo(f"Wrote {path}")


def run() -> None:
    app()
