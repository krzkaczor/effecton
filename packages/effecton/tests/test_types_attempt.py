from dataclasses import dataclass
from typing import assert_type

import effecton as E


@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


# --- attempt: lifts a raising thunk into the typed channel ---

assert_type(
    E.attempt(lambda: 1, lambda e: ParseError(str(e))),
    E.Effect[int, ParseError],
)

# --- attempt: negative tests ---

# on_error must produce an EffectonError.
E.attempt(lambda: 1, lambda e: ValueError("x"))  # type: ignore[type-var]
