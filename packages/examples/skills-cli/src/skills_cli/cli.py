"""Entry point: the one command, its Live services, and run_main."""

from typing import Annotated

import effecton as E
from skills_cli import terminal as Terminal
from skills_cli.program import InstallError, Services, install_skill

Cli = E.Cli


class Install(Cli.Args):
    skill_url: Annotated[
        str, Cli.Argument(help="GitHub URL of the SKILL.md to install.")
    ]


@E.gen
def run_install(
    args: Install,
) -> E.EffectGen[None, InstallError, Services | E.Process.Protocol]:
    process = yield from E.require(E.Process.Protocol)

    home = yield from process.home()
    skill_name = yield from install_skill(args.skill_url, home)
    yield from E.sync(lambda: print(f"Skill {skill_name} installed."))


app = Cli.command(
    "skills-cli",
    args=Install,
    handler=run_install,
    help="Install an Agent Skill from a GitHub SKILL.md URL.",
)


def run() -> None:
    E.run_main(
        Cli.run(app)
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
        .provide(E.HttpClient.Protocol)(E.HttpClient.AsyncLive())
        .provide(Terminal.Protocol)(Terminal.Live())
    )
