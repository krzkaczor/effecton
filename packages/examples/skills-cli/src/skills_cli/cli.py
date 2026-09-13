"""Typer entry point: wire the Live services, run the program, render the Exit."""

import typer

import effecton as E
from skills_cli import http_client as HttpClient
from skills_cli import terminal as Terminal
from skills_cli.program import install_skill


def main(skill_url: str) -> None:
    runnable = (
        E.require(E.Process.Protocol)
        .flat_map(lambda process: process.home())
        .flat_map(lambda home: install_skill(skill_url, home))
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
        .provide(HttpClient.Protocol)(HttpClient.Live())
        .provide(Terminal.Protocol)(Terminal.Live())
    )

    skill_name = E.run_main(runnable)
    typer.echo(f"Skill {skill_name} installed.")


def run() -> None:
    typer.run(main)
