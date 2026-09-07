"""Typer entry point: wire the Live services, run the program, render the Exit."""

from pathlib import Path

import typer

import effecton as E
from skills_cli import file_system as FileSystem
from skills_cli import http_client as HttpClient
from skills_cli import terminal as Terminal
from skills_cli.program import install_skill


def main(skill_url: str) -> None:
    runnable = (
        install_skill(skill_url, Path.home())
        .provide(FileSystem.Protocol)(FileSystem.Live())
        .provide(HttpClient.Protocol)(HttpClient.Live())
        .provide(Terminal.Protocol)(Terminal.Live())
    )

    skill_name = E.run_main(runnable)
    typer.echo(f"Skill {skill_name} installed.")


def run() -> None:
    typer.run(main)
