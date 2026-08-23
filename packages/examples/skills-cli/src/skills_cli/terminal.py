"""Terminal service: Protocol plus Live (typer prompt) and Test (canned answer)."""

import typing
from dataclasses import dataclass, field
from typing import runtime_checkable

import typer

import effecton as E


@runtime_checkable
class Protocol(typing.Protocol):
    def confirm(self, prompt: str) -> E.Effect[bool]: ...


class Live(Protocol):
    @E.suspend
    def confirm(self, prompt: str) -> E.Effect[bool]:
        # Ctrl-C or EOF raises typer.Abort, which stays a defect.
        return E.success(typer.confirm(prompt))


@dataclass
class Test(Protocol):
    __test__ = False

    answer: bool = True
    prompts: list[str] = field(default_factory=list)

    @E.suspend
    def confirm(self, prompt: str) -> E.Effect[bool]:
        self.prompts.append(prompt)
        return E.success(self.answer)
