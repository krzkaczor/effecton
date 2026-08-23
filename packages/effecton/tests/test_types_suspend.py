from dataclasses import dataclass
from typing import Never, assert_type

import effecton as E


@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


@dataclass(frozen=True)
class Db:
    url: str


def parse(s: str) -> E.Effect[int, ParseError]:
    try:
        return E.success(int(s))
    except ValueError:
        return E.fail(ParseError(s))


def _one_arg(x: int) -> int:
    return x


# --- suspend: a thunk defers an effect, all three channels pass through ---

assert_type(E.suspend(lambda: E.success(1)), E.Effect[int])
assert_type(E.suspend(lambda: parse("1")), E.Effect[int, ParseError])
assert_type(E.suspend(lambda: E.require(Db)), E.Effect[Db, Never, Db])

# --- suspend as a decorator preserves the call signature ---


@E.suspend
def _fetch(user_id: int) -> E.Effect[str, ParseError]:
    return E.success(str(user_id))


assert_type(_fetch(1), E.Effect[str, ParseError])


# A zero-arg function resolves to the thunk overload; the name is the effect.


@E.suspend
def _config() -> E.Effect[int]:
    return E.success(1)


assert_type(_config, E.Effect[int])

# --- suspend: negative tests ---

# The callable must return an Effect.
E.suspend(lambda: 1)  # type: ignore[arg-type, return-value]
E.suspend(_one_arg)  # type: ignore[arg-type]

# The decorator does not change the parameter types.
_fetch("x")  # type: ignore[arg-type]

# The value type comes from the thunk, not from the annotation.
suspended_int = E.suspend(lambda: E.success(1))
must_be_int_suspended: E.Effect[str] = suspended_int  # type: ignore[assignment]
