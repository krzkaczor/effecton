"""Type-level pins for gen. Nothing here runs: ty checks the function
bodies and pytest never calls them."""

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


def _gen_turns_a_generator_function_into_an_effect_factory() -> None:
    # E and R default to Never.
    @E.gen
    def simple() -> E.EffectGen[int]:
        x = yield from E.success(20)
        y = yield from E.success(22)
        return x + y

    assert_type(simple(), E.Effect[int])
    assert_type(E.run_sync_exit(simple()), E.Succeeded[int] | E.Failure)

    # The value channel comes from the EffectGen annotation.
    _must_be_int_gen: E.Effect[str] = simple()  # ty: ignore[invalid-assignment]


def _gen_error_channel_flows_from_the_annotated_yield_type() -> None:
    @E.gen
    def failing() -> E.EffectGen[int, ParseError]:
        yield from E.fail(ParseError("x"))
        return 0

    assert_type(failing(), E.Effect[int, ParseError])
    assert_type(E.run_sync_exit(failing()), E.Succeeded[int] | E.Failure[ParseError])

    # catch_all composes over a gen effect like any other.
    assert_type(failing().catch_all(lambda _: E.success(0)), E.Effect[int])


def _gen_requirements_flow_into_r_and_a_provider_chain_discharges_them() -> None:
    @E.gen
    def needs_db() -> E.EffectGen[str, Never, Db]:
        db = yield from E.require(Db)
        return db.url

    assert_type(needs_db(), E.Effect[str, Never, Db])
    assert_type(needs_db().provide(Db)(Db("postgres://x")), E.Effect[str])

    # A gen effect with unmet requirements is not runnable.
    E.run_sync_exit(needs_db())  # ty: ignore[invalid-argument-type]


def _gen_preserves_the_call_signature() -> None:
    @E.gen
    def parameterized(base: int) -> E.EffectGen[int]:
        x = yield from E.success(base)
        return x * 2

    assert_type(parameterized(21), E.Effect[int])

    # The decorator does not change the parameter types.
    parameterized("x")  # ty: ignore[invalid-argument-type]


def _gen_yield_from_is_typed_and_bare_yield_is_any() -> None:
    # yield from types the sent-back value as the effect's A (through
    # Effect.__iter__), checked per expression; a bare yield types as Any,
    # so an annotation on it is trusted rather than checked.
    @E.gen
    def yield_from_is_typed() -> E.EffectGen[int]:
        x = yield from E.success(1)
        assert_type(x, Literal[1])
        return x

    @E.gen
    def bare_yield_is_any() -> E.EffectGen[int]:
        x = yield E.success(1)
        assert_type(x, Any)
        return 0

    # The yield from result really is typed, not Any: a wrong annotation is
    # an assignment error (contrast with the bare yield above).
    @E.gen
    def yield_from_result_is_not_any() -> E.EffectGen[int]:
        x: str = yield from E.success(1)  # ty: ignore[invalid-assignment]
        return len(x)


def _gen_negative() -> None:
    def not_a_generator(x: int) -> int:
        return x

    # The decorated function must be a generator of effects.
    E.gen(not_a_generator)  # ty: ignore[invalid-argument-type]
