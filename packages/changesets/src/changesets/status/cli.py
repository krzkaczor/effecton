"""The `changeset status` command."""

import effecton as E
from changesets.shared import repo
from changesets.status.program import StatusError
from changesets.status.program import status as status_program

Cli = E.Cli


@E.gen
def run_status() -> E.EffectGen[
    None, StatusError, E.FileSystem.Protocol | E.Process.Protocol
]:
    report = yield from repo.from_cwd(status_program)
    yield from E.sync(lambda: print(report))


status = Cli.command(
    "status",
    handler=run_status,
    help="Show pending changesets and the releases they would produce.",
)
