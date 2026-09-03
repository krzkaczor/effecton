"""Git service: Protocol plus Live (subprocess) and Test (in-memory).

Live shells out to `git` inside the directory it is constructed with, which
must lie within the repository. A non-zero exit is typed; git being absent
from the machine stays a defect.
"""

import subprocess
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import runtime_checkable

import effecton as E


@dataclass(frozen=True)
class GitCommandFailed(E.EffectonError):
    command: tuple[str, ...]
    stderr: str

    def __str__(self) -> str:
        return f"git {' '.join(self.command)} failed: {self.stderr.strip()}"


type GitError = GitCommandFailed


@runtime_checkable
class Protocol(typing.Protocol):
    def added_in(self, path: Path) -> E.Effect[str | None, GitCommandFailed]:
        """Subject of the first-parent commit that added `path`, if any."""
        ...

    def remote_url(self, name: str) -> E.Effect[str, GitCommandFailed]: ...


@dataclass(frozen=True)
class Live(Protocol):
    cwd: Path

    def added_in(self, path: Path) -> E.Effect[str | None, GitCommandFailed]:
        # --first-parent follows main-branch history only, so the adding
        # commit is the squash or merge commit that landed the PR, whose
        # subject carries the PR number.
        args = (
            "log",
            "--first-parent",
            "--diff-filter=A",
            "--format=%s",
            "--",
            str(path),
        )
        return _run(self.cwd, args).map(
            lambda out: next((line for line in out.splitlines() if line.strip()), None)
        )

    def remote_url(self, name: str) -> E.Effect[str, GitCommandFailed]:
        return _run(self.cwd, ("remote", "get-url", name)).map(str.strip)


@dataclass
class Test(Protocol):
    __test__ = False

    subjects: dict[Path, str] = field(default_factory=dict)
    remotes: dict[str, str] = field(default_factory=dict)

    def added_in(self, path: Path) -> E.Effect[str | None]:
        return E.sync(lambda: self.subjects.get(path))

    @E.suspend
    def remote_url(self, name: str) -> E.Effect[str, GitCommandFailed]:
        if name not in self.remotes:
            args = ("remote", "get-url", name)
            return E.fail(
                GitCommandFailed(command=args, stderr=f"error: No such remote '{name}'")
            )
        return E.success(self.remotes[name])


def _run(cwd: Path, args: tuple[str, ...]) -> E.Effect[str, GitCommandFailed]:
    def go() -> str:
        completed = subprocess.run(
            ("git", *args), cwd=cwd, capture_output=True, text=True, check=True
        )
        return completed.stdout

    def to_error(e: Exception) -> GitCommandFailed:
        if isinstance(e, subprocess.CalledProcessError):
            return GitCommandFailed(command=args, stderr=e.stderr)
        raise e

    return E.attempt(go, to_error)
