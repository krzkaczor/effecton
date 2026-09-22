"""The ``api-reference`` command: render the page for the docs site."""

from typing import Annotated

import effecton as E
from api_reference import collect
from api_reference.program import write_reference
from api_reference.topics import TOPICS

Cli = E.Cli


class Generate(Cli.Args):
    out: Annotated[
        E.Path, Cli.Option(help="Where to write the page, relative to the cwd.")
    ] = E.Path("docs/src/pages/api.md")


def run_generate(
    args: Generate,
) -> E.Effect[
    None,
    collect.CollectError
    | E.FileSystem.FileNotFound
    | E.FileSystem.PermissionDenied
    | E.FileSystem.PathAlreadyExists
    | E.FileSystem.PathIsADirectory
    | E.FileSystem.PathIsNotADirectory,
    E.FileSystem.Protocol,
]:
    return (
        E.sync(collect.load)
        .flat_map(lambda root: collect.collect(root, TOPICS))
        .flat_map(lambda reference: write_reference(args.out, reference))
        .flat_map(lambda path: E.sync(lambda: print(f"Wrote {path}")))
    )


app = Cli.command(
    "api-reference",
    args=Generate,
    handler=run_generate,
    help="Render the docs API Reference page from the effecton sources.",
)


def run() -> None:
    E.run_main(
        Cli.run(app)
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
    )
