"""Entry point: assemble one CLI from the per-command modules."""

import effecton as E
from changesets.add import name_generator as NameGenerator
from changesets.add.cli import add
from changesets.notes.cli import notes
from changesets.status.cli import status
from changesets.version.cli import version

Cli = E.Cli

app = Cli.command(
    "changeset", help="Changeset-based changelog and version management."
).with_subcommands(add, status, version, notes)


def run() -> None:
    E.run_main(
        Cli.run(app)
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
        .provide(NameGenerator.Protocol)(NameGenerator.Live())
    )
