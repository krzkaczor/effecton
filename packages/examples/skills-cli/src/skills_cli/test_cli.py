import logging

import typer
from typer.testing import CliRunner

import effecton as E
from skills_cli import cli
from skills_cli import terminal as Terminal


# @todo: once effecton has built-in CLI support this can inject dependencies properly
def test_install_success(monkeypatch):
    home = E.Path("/home/me")
    fs = E.FileSystem.Test()
    body = "---\ndisable-model-invocation: true\n---\n\nbody"
    http = E.HttpClient.Test(
        responses={
            "https://raw.githubusercontent.com/octo/my-skill/main/SKILL.md": body
        }
    )
    monkeypatch.setattr(E.FileSystem, "AsyncLive", lambda: fs)
    monkeypatch.setattr(E.Process, "Live", lambda: E.Process.Test(home_directory=home))
    monkeypatch.setattr(E.HttpClient, "AsyncLive", lambda: http)
    monkeypatch.setattr(Terminal, "Live", Terminal.Test)
    app = typer.Typer()
    app.command()(cli.main)

    result = CliRunner().invoke(
        app, ["https://github.com/octo/my-skill/blob/main/SKILL.md"]
    )

    assert result.exit_code == 0
    assert result.stdout == "Skill my-skill installed.\n"
    assert home / ".agents/skills/my-skill/SKILL.md" in fs.files


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
