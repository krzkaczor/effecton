"""Example CLI built on effecton: install an Agent Skill from a GitHub URL.

Services follow the module-as-namespace pattern: each service module
exports a Protocol plus Live and Test implementations, and consumers
alias the module — ``from skills_cli import file_system as FileSystem``,
then ``FileSystem.Protocol`` / ``FileSystem.Live`` / ``FileSystem.Test``.
"""

from skills_cli import (
    file_system,
    http_client,
    parse_url,
    program,
    skill,
    terminal,
)

__all__ = [
    "file_system",
    "http_client",
    "parse_url",
    "program",
    "skill",
    "terminal",
]
