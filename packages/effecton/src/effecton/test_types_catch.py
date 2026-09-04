from dataclasses import dataclass
from typing import Literal, Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


@final
@dataclass(frozen=True)
class NegativeError(E.EffectonError):
    value: int


@final
@dataclass(frozen=True)
class OtherError(E.EffectonError):
    code: int


@dataclass(frozen=True)
class Db:
    url: str


def parse(s: str) -> E.Effect[int, ParseError]:
    try:
        return E.success(int(s))
    except ValueError:
        return E.fail(ParseError(s))


chain = parse("1").flat_map(
    lambda x: E.success(x) if x > 0 else E.fail(NegativeError(x))
)
assert_type(chain, E.Effect[int, ParseError | NegativeError])

# --- catch: subtracts the caught type from E, unions the handler's channels ---

assert_type(
    chain.catch(NegativeError)(lambda _: E.success(0)), E.Effect[int, ParseError]
)
assert_type(
    chain.catch(NegativeError)(lambda _: E.fail(OtherError(1))),
    E.Effect[int, ParseError | OtherError],
)
assert_type(
    chain.catch(NegativeError)(lambda _: E.success("zero")),
    E.Effect[int | Literal["zero"], ParseError],
)

# The handler receives the narrowed error, not the whole union.
assert_type(
    chain.catch(NegativeError)(lambda e: E.success(e.value)),
    E.Effect[int, ParseError],
)

# Catching the only member leaves E = Never (the remainder defaults to Never).
assert_type(
    E.fail(ParseError("x")).catch(ParseError)(lambda _: E.success(0)),
    E.Effect[Literal[0]],
)

# A chain subtracts one member at a time down to a runnable effect.
handled = chain.catch(NegativeError)(lambda _: E.success(0)).catch(ParseError)(
    lambda _: E.success(1)
)
assert_type(handled, E.Effect[int])
assert_type(E.run_sync(handled), E.Succeeded[int] | E.Failure)

# The handler's requirements union into R; the source's ride through.
assert_type(
    chain.catch(NegativeError)(lambda _: E.require(Db).map(lambda _: 0)),
    E.Effect[int, ParseError, Db],
)
needs_db = E.require(Db).flat_map(lambda _: chain)
assert_type(
    needs_db.catch(NegativeError)(lambda _: E.success(0)),
    E.Effect[int, ParseError, Db],
)

# --- catch: over-catching is a well-typed no-op ---

# E's covariance means an absent member subtracts nothing, so it cannot be
# rejected (that would need type negation) and E stays unchanged.
assert_type(
    E.success(1).catch(ParseError)(lambda _: E.success(0)), E.Effect[Literal[1, 0]]
)
assert_type(
    E.die("boom").catch(ParseError)(lambda _: E.success(0)), E.Effect[Literal[0]]
)

# --- catch: negative tests ---


def wrong_input(e: str) -> E.Effect[int]:
    return E.success(len(e))


# The handler must accept the caught error type.
chain.catch(NegativeError)(wrong_input)  # ty: ignore[invalid-argument-type]


# Error classes are leaves: subclassing a final error is rejected, so the
# runtime isinstance check and the static subtraction of T from E always agree.
class BigNegativeError(NegativeError):  # ty: ignore[subclass-of-final-class]
    pass


# The caught type must be an EffectonError class, not an instance.
chain.catch(ValueError)  # ty: ignore[invalid-argument-type]
chain.catch(ParseError("x"))  # ty: ignore[invalid-argument-type]

# The uncaught remainder stays in E.
partially_handled = chain.catch(NegativeError)(lambda _: E.success(0))
must_be_handled: E.Effect[int] = partially_handled  # ty: ignore[invalid-assignment]


# An effect with an uncaught error still runs, but its Exit carries it.
def _remainder_is_in_the_exit() -> None:
    assert_type(E.run_sync(partially_handled), E.Succeeded[int] | E.Failure[ParseError])
    assert_type(E.run_sync(chain), E.Succeeded[int] | E.Failure[Never])  # ty: ignore[type-assertion-failure]
