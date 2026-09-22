"""Process service: what the running process knows about its environment.

Today that is the current working directory, the home directory and the
command-line arguments; environment variables belong here too when they
arrive. Reading them is ambient process state rather than file I/O, so
they live apart from FileSystem and E.Path stays a pure value. Like
FileSystem it is an explicit requirement: provide Live at the edge, and
Test in tests, where all three are plain fields.
"""

import os
import sys
import typing
from dataclasses import dataclass
from typing import final, runtime_checkable

from effecton.effect import Effect, sync
from effecton.std.path import Path


@runtime_checkable
class Protocol(typing.Protocol):
    def cwd(self) -> Effect[Path]:
        """The current working directory."""
        ...

    def home(self) -> Effect[Path]:
        """The current user's home directory."""
        ...

    def argv(self) -> Effect[tuple[str, ...]]:
        """The command-line arguments, without the program name."""
        ...


@final
@dataclass(frozen=True)
class Live(Protocol):
    """The real process; its reads are plain sync effects under either runner."""

    def cwd(self) -> Effect[Path]:
        return sync(lambda: Path(os.getcwd()))

    def home(self) -> Effect[Path]:
        return sync(lambda: Path(os.path.expanduser("~")))

    def argv(self) -> Effect[tuple[str, ...]]:
        return sync(lambda: tuple(sys.argv[1:]))


_ROOT = Path("/")
_HOME = Path("/home")


@final
@dataclass
class Test(Protocol):
    current_directory: Path = _ROOT
    home_directory: Path = _HOME
    arguments: tuple[str, ...] = ()

    def cwd(self) -> Effect[Path]:
        return sync(lambda: self.current_directory)

    def home(self) -> Effect[Path]:
        return sync(lambda: self.home_directory)

    def argv(self) -> Effect[tuple[str, ...]]:
        return sync(lambda: self.arguments)
