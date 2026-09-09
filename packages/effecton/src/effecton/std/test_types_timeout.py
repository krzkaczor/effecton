from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, assert_type, final

import effecton as E

ONE_SECOND = timedelta(seconds=1)


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


# --- timeout: adds TimeoutException to E, keeps A and R ---

assert_type(
    parse("1").timeout(ONE_SECOND), E.Effect[int, ParseError | E.TimeoutException]
)
assert_type(E.require(Db).timeout(ONE_SECOND), E.Effect[Db, E.TimeoutException, Db])
assert_type(
    E.timeout(ONE_SECOND)(parse("1")), E.Effect[int, ParseError | E.TimeoutException]
)
assert_type(E.success(None).timeout(ONE_SECOND), E.Effect[None, E.TimeoutException])

# --- catch subtracts the timeout back out ---

assert_type(
    parse("1").timeout(ONE_SECOND).catch(E.TimeoutException)(lambda _: E.success(0)),
    E.Effect[int, ParseError],
)
assert_type(
    E.success(None)
    .timeout(ONE_SECOND)
    .catch(E.TimeoutException)(lambda e: E.success(e.duration)),
    E.Effect[None | timedelta],
)

# --- timeout as a decorator preserves the call signature ---


@E.timeout(ONE_SECOND)
def _fetch(user_id: int) -> E.Effect[str, ParseError, Db]:
    return E.require(Db).map(lambda db: db.url + str(user_id))


assert_type(_fetch(1), E.Effect[str, ParseError | E.TimeoutException, Db])


@E.timeout(ONE_SECOND)
@E.gen
def _program(name: str) -> E.EffectGen[str, ParseError]:
    value = yield from parse(name)
    return str(value)


assert_type(_program("1"), E.Effect[str, ParseError | E.TimeoutException])

# --- negative tests ---

# The duration is a timedelta, not a number of seconds.
E.success(1).timeout(1)  # ty: ignore[invalid-argument-type]
E.timeout(1)  # ty: ignore[invalid-argument-type]

# The target must be an effect or a function returning one.
E.timeout(ONE_SECOND)(lambda: 1)  # ty: ignore[no-matching-overload]
E.timeout(ONE_SECOND)(1)  # ty: ignore[no-matching-overload]

# The decorator does not change the parameter types.
_fetch("x")  # ty: ignore[invalid-argument-type]

# The timeout stays in E until it is caught.
timed: E.Effect[int, ParseError] = parse("1").timeout(ONE_SECOND)  # ty: ignore[invalid-assignment]


# Errors are leaves: TimeoutException cannot be subclassed.
class LongTimeout(E.TimeoutException):  # ty: ignore[subclass-of-final-class]
    pass


# Catching the only member leaves E = Never.
assert_type(
    E.success(1).timeout(ONE_SECOND).catch(E.TimeoutException)(lambda _: E.success(0)),
    E.Effect[Literal[1, 0]],
)
