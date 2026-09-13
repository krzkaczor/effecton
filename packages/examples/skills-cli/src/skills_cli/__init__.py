"""Example CLI built on effecton: install an Agent Skill from a GitHub URL.

Services follow the module-as-namespace pattern: each service module
exports a Protocol plus Live and Test implementations, and consumers
alias the module — ``from skills_cli import terminal as Terminal``,
then ``Terminal.Protocol`` / ``Terminal.Live`` / ``Terminal.Test``.
Files and HTTP are reached through the E.FileSystem and E.HttpClient
services that effecton ships.
"""

from skills_cli import (
    parse_url,
    program,
    skill,
    terminal,
)

__all__ = [
    "parse_url",
    "program",
    "skill",
    "terminal",
]
