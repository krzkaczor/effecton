from dataclasses import dataclass
from typing import Any, Literal, Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


@dataclass(frozen=True)
class Db:
    url: str


# --- gen: the decorator turns a generator function into an effect factory ---
# E and R default to Never.


@E.gen
def _simple() -> E.EffectGen[int]:
    x = yield from E.success(20)
    y = yield from E.success(22)
    return x + y


assert_type(_simple(), E.Effect[int])
assert_type(E.run_sync(_simple()), E.Succeeded[int] | E.Failure)


# The error channel flows from the annotated yield type.


@E.gen
def _failing() -> E.EffectGen[int, ParseError]:
    yield from E.fail(ParseError("x"))
    return 0


assert_type(_failing(), E.Effect[int, ParseError])
assert_type(E.run_sync(_failing()), E.Succeeded[int] | E.Failure[ParseError])

# catch_all composes over a gen effect like any other.
assert_type(_failing().catch_all(lambda _: E.success(0)), E.Effect[int])


# Requirements flow into R, and a provider chain discharges them.


@E.gen
def _needs_db() -> E.EffectGen[str, Never, Db]:
    db = yield from E.require(Db)
    return db.url


assert_type(_needs_db(), E.Effect[str, Never, Db])
assert_type(
    _needs_db().provide(Db)(Db("postgres://x")),
    E.Effect[str],
)


# The decorator preserves the call signature.


@E.gen
def _parameterized(base: int) -> E.EffectGen[int]:
    x = yield from E.success(base)
    return x * 2


assert_type(_parameterized(21), E.Effect[int])


# yield from types the sent-back value as the effect's A (through
# Effect.__iter__), checked per expression; a bare yield types as Any,
# so an annotation on it is trusted rather than checked.


@E.gen
def _yield_from_is_typed() -> E.EffectGen[int]:
    x = yield from E.success(1)
    assert_type(x, Literal[1])
    return x


@E.gen
def _bare_yield_is_any() -> E.EffectGen[int]:
    x = yield E.success(1)
    assert_type(x, Any)
    return 0


# --- gen: negative tests ---


def _not_a_generator(x: int) -> int:
    return x


# The decorated function must be a generator of effects.
E.gen(_not_a_generator)  # ty: ignore[invalid-argument-type]

# The decorator does not change the parameter types.
_parameterized("x")  # ty: ignore[invalid-argument-type]

# The value channel comes from the EffectGen annotation.
must_be_int_gen: E.Effect[str] = _simple()  # ty: ignore[invalid-assignment]


# A gen effect with unmet requirements is not runnable.
# Type-checked only; never called.
def _unprovided_gen_is_not_runnable() -> None:
    E.run_sync(_needs_db())  # ty: ignore[invalid-argument-type]


# The yield from result really is typed, not Any: a wrong annotation is
# an assignment error (contrast with the earlier bare yield).
@E.gen
def _yield_from_result_is_not_any() -> E.EffectGen[int]:
    x: str = yield from E.success(1)  # ty: ignore[invalid-assignment]
    return len(x)
