"""Type-level pins for run_main. Nothing here runs: ty checks the function
bodies and pytest never calls them."""

from dataclasses import dataclass
from typing import Literal, Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


@dataclass(frozen=True)
class Db:
    url: str


def _run_main_produces_the_value() -> None:
    async def fetch() -> int:
        return 1

    assert_type(E.run_main(E.success(1)), Literal[1])
    assert_type(E.run_main(E.coroutine(fetch)), int)
    assert_type(E.run_main(E.fail(ParseError("x"))), Never)


def _run_main_negative() -> None:
    # An unmet requirement makes the effect unrunnable.
    E.run_main(E.require(Db))  # ty: ignore[invalid-argument-type]
