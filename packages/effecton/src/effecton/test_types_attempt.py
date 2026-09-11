"""Type-level pins for attempt. Nothing here runs: ty checks the function
bodies and pytest never calls them."""

from dataclasses import dataclass
from typing import Literal, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


def _attempt_lifts_a_raising_thunk_into_the_typed_channel() -> None:
    assert_type(
        E.attempt(lambda: 1, lambda e: ParseError(str(e))),
        E.Effect[Literal[1], ParseError],
    )


def _attempt_negative() -> None:
    # on_error must produce an EffectonError.
    E.attempt(lambda: 1, lambda e: ValueError("x"))  # ty: ignore[invalid-argument-type]
