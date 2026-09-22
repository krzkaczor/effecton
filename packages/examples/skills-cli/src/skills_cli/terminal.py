"""Terminal service: Protocol plus Live (stdin prompt) and Test (canned answer)."""

import typing
from dataclasses import dataclass, field
from typing import runtime_checkable

import effecton as E


@runtime_checkable
class Protocol(typing.Protocol):
    def confirm(self, prompt: str) -> E.Effect[bool]: ...


class Live(Protocol):
    def confirm(self, prompt: str) -> E.Effect[bool]:
        # EOF or Ctrl-C inside input() raises and stays a defect.
        return E.sync(
            lambda: input(f"{prompt} [y/N]: ").strip().lower() in ("y", "yes")
        )


@dataclass
class Test(Protocol):
    answer: bool = True
    prompts: list[str] = field(default_factory=list)

    @E.suspend
    def confirm(self, prompt: str) -> E.Effect[bool]:
        self.prompts.append(prompt)
        return E.success(self.answer)
