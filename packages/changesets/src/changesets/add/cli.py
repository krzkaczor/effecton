"""The `changeset add` command."""

from typing import Annotated

import effecton as E
from changesets.add.program import AddError, AddServices, add_changeset
from changesets.shared import repo
from changesets.shared.semver import Bump

Cli = E.Cli
S = E.Schema


class Add(Cli.Args):
    package: Annotated[str, Cli.Option(help="Package the change belongs to.")]
    bump: Annotated[Bump, Cli.Option(help="major, minor, or patch.")]
    message: Annotated[
        str,
        Cli.Option(
            help="Changelog entry for the change.",
            schema=S.String.check(
                S.filter(
                    lambda m: m.strip() != "", message="expected a non-empty message"
                )
            ),
        ),
    ]


@E.gen
def run_add(
    args: Add,
) -> E.EffectGen[None, AddError, AddServices | E.Process.Protocol]:
    path = yield from repo.from_cwd(
        lambda cwd: add_changeset(cwd, args.package, args.bump, args.message)
    )
    yield from E.sync(lambda: print(f"Created {path}"))


add = Cli.command(
    "add",
    args=Add,
    handler=run_add,
    help="Create a changeset from the given package, bump level, and message.",
)
