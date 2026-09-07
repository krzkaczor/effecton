import logging
from pathlib import Path

import typer
from typer.testing import CliRunner

from skills_cli import cli
from skills_cli import file_system as FileSystem
from skills_cli import http_client as HttpClient
from skills_cli import terminal as Terminal


def test_install_success(monkeypatch):
    fs = FileSystem.Test()
    body = "---\ndisable-model-invocation: true\n---\n\nbody"
    http = HttpClient.Test(
        responses={
            "https://raw.githubusercontent.com/octo/my-skill/main/SKILL.md": body
        }
    )
    monkeypatch.setattr(FileSystem, "Live", lambda: fs)
    monkeypatch.setattr(HttpClient, "Live", lambda: http)
    monkeypatch.setattr(Terminal, "Live", Terminal.Test)
    app = typer.Typer()
    app.command()(cli.main)

    result = CliRunner().invoke(
        app, ["https://github.com/octo/my-skill/blob/main/SKILL.md"]
    )

    assert result.exit_code == 0
    assert result.stdout == "Skill my-skill installed.\n"
    assert (Path.home() / ".agents/skills/my-skill/SKILL.md") in fs.files


def test_install_failure(caplog):
    app = typer.Typer()
    app.command()(cli.main)
    logger = logging.getLogger("effecton.pretty")
    logger.addHandler(caplog.handler)

    try:
        result = CliRunner().invoke(app, ["not-a-url"])
    finally:
        logger.removeHandler(caplog.handler)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert "Traceback" not in caplog.text
