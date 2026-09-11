from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, Never, assert_type, final

import effecton as E

ONE_SECOND = timedelta(seconds=1)
RECURS = E.Schedule.recurs(3)


@final
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


def is_empty(error: ParseError) -> bool:
    return error.value == ""


# --- retry keeps A, E, and R ---

assert_type(parse("1").retry(RECURS), E.Effect[int, ParseError])
assert_type(parse("1").retry(RECURS, until=is_empty), E.Effect[int, ParseError])
assert_type(E.require(Db).retry(RECURS), E.Effect[Db, Never, Db])
assert_type(E.success(1).retry(RECURS), E.Effect[Literal[1]])

# --- the predicate sees the error channel ---

assert_type(
    parse("1").retry(RECURS, until=lambda e: bool(assert_type(e, ParseError))),
    E.Effect[int, ParseError],
)

# --- schedules ---

assert_type(E.Schedule.recurs(3), E.Schedule)
assert_type(E.Schedule.spaced(ONE_SECOND), E.Schedule)
assert_type(E.Schedule.exponential(ONE_SECOND, factor=3), E.Schedule)
assert_type(E.Schedule(lambda: iter([ONE_SECOND])), E.Schedule)

# --- negative tests ---

# The schedule is a Schedule, not a count.
E.success(1).retry(3)  # ty: ignore[invalid-argument-type]

# Delays are timedelta values, counts are ints.
E.Schedule.spaced(1)  # ty: ignore[invalid-argument-type]
E.Schedule.recurs(ONE_SECOND)  # ty: ignore[invalid-argument-type]


# The predicate must accept the effect's error type.
def takes_int(error: int) -> bool:
    return error == 0


parse("1").retry(RECURS, until=takes_int)  # ty: ignore[invalid-argument-type]


# The predicate is keyword-only; passing it positionally also raises, so
# the pin stays uncalled.
def _positional_predicate() -> None:
    parse("1").retry(RECURS, is_empty)  # ty: ignore[too-many-positional-arguments]


# Schedules are leaves: Schedule cannot be subclassed.
class Custom(E.Schedule):  # ty: ignore[subclass-of-final-class]
    pass
