"""The `changeset notes` command."""

from typing import Annotated

import effecton as E
from changesets.notes.program import NotesError, latest_notes
from changesets.shared import repo

Cli = E.Cli


class Notes(Cli.Args):
    package: Annotated[str, Cli.Argument(help="Package to print notes for.")]


@E.gen
def run_notes(
    args: Notes,
) -> E.EffectGen[None, NotesError, E.FileSystem.Protocol | E.Process.Protocol]:
    section = yield from repo.from_cwd(lambda cwd: latest_notes(cwd, args.package))
    yield from E.sync(lambda: print(section, end=""))


notes = Cli.command(
    "notes",
    args=Notes,
    handler=run_notes,
    help="Print the latest released CHANGELOG section for a package.",
)
