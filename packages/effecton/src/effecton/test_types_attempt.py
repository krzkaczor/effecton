from dataclasses import dataclass
from typing import Literal, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


# --- attempt: lifts a raising thunk into the typed channel ---

assert_type(
    E.attempt(lambda: 1, lambda e: ParseError(str(e))),
    E.Effect[Literal[1], ParseError],
)

# --- attempt: negative tests ---

# on_error must produce an EffectonError.
E.attempt(lambda: 1, lambda e: ValueError("x"))  # ty: ignore[invalid-argument-type]
