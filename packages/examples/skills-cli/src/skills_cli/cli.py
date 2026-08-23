"""Typer entry point: wire the Live services, run the program, render the Exit."""

from pathlib import Path
from typing import assert_never

import typer

import effecton as E
from skills_cli import file_system as FileSystem
from skills_cli import http_client as HttpClient
from skills_cli import terminal as Terminal
from skills_cli.errors import (
    FrontmatterParseError,
    HttpRequestError,
    HttpStatusError,
    InstallError,
    MalformedSkillPath,
    NotASkillFile,
    PathAlreadyExists,
    PathIsADirectory,
    PathIsNotADirectory,
    PermissionDenied,
    UnsupportedHost,
)
from skills_cli.program import install_skill


def main(skill_url: str) -> None:
    runnable = (
        E.RequirementProvider()
        .and_provide(FileSystem.Protocol)(FileSystem.Live())
        .and_provide(HttpClient.Protocol)(HttpClient.Live())
        .and_provide(Terminal.Protocol)(Terminal.Live())
        .apply(install_skill(skill_url, Path.home()))
    )

    match E.run_sync(runnable):
        case E.Succeeded(value=skill_name):
            typer.echo(f"Skill {skill_name} installed.")
        case E.Failure(cause=E.Fail(error=error)):
            typer.echo(_describe(error), err=True)
            raise typer.Exit(code=1)
        case E.Failure(cause=E.Die(defect=defect)):
            if isinstance(defect, BaseException):
                raise defect
            raise RuntimeError(str(defect))


def _describe(error: InstallError) -> str:
    match error:
        case UnsupportedHost(url=url, host=host):
            return f"Unsupported host {host!r} in {url}"
        case NotASkillFile(url=url):
            return f"{url} doesn't point to a SKILL.md"
        case MalformedSkillPath(url=url, reason=reason):
            return f"Couldn't parse {url}: {reason}"
        case HttpRequestError(url=url, message=message):
            return f"Request to {url} failed: {message}"
        case HttpStatusError(url=url, status_code=status_code):
            return f"Fetching {url} returned HTTP {status_code}"
        case FrontmatterParseError(message=message):
            return f"Invalid skill frontmatter: {message}"
        case PermissionDenied(path=path):
            return f"Permission denied: {path}"
        case PathIsNotADirectory(path=path):
            return f"{path} exists but is not a directory"
        case PathIsADirectory(path=path):
            return f"Can't write {path}: it is a directory"
        case PathAlreadyExists(path=path):
            return f"Can't create symlink {path}: it already exists"
        case _ as unreachable:
            assert_never(unreachable)


def run() -> None:
    typer.run(main)
