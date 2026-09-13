"""Example CLI built on effecton: install an Agent Skill from a GitHub URL.

Services follow the module-as-namespace pattern: each service module
exports a Protocol plus Live and Test implementations, and consumers
alias the module — ``from skills_cli import http_client as HttpClient``,
then ``HttpClient.Protocol`` / ``HttpClient.Live`` / ``HttpClient.Test``.
Files are reached through the E.FileSystem service that effecton ships.
"""

from skills_cli import (
    http_client,
    parse_url,
    program,
    skill,
    terminal,
)

__all__ = [
    "http_client",
    "parse_url",
    "program",
    "skill",
    "terminal",
]
