"""Type-level pins for suspend. Nothing here runs: ty checks the function
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


def parse(s: str) -> E.Effect[int, ParseError]:
    try:
        return E.success(int(s))
    except ValueError:
        return E.fail(ParseError(s))


def _suspend_thunk_defers_an_effect_and_all_three_channels_pass_through() -> None:
    assert_type(E.suspend(lambda: E.success(1)), E.Effect[Literal[1]])
    assert_type(E.suspend(lambda: parse("1")), E.Effect[int, ParseError])
    assert_type(E.suspend(lambda: E.require(Db)), E.Effect[Db, Never, Db])


def _suspend_as_a_decorator_preserves_the_call_signature() -> None:
    @E.suspend
    def fetch(user_id: int) -> E.Effect[str, ParseError]:
        return E.success(str(user_id))

    assert_type(fetch(1), E.Effect[str, ParseError])

    # The decorator does not change the parameter types.
    fetch("x")  # ty: ignore[invalid-argument-type]


def _suspend_zero_arg_function_resolves_to_the_thunk_overload() -> None:
    # The name is the effect.
    @E.suspend
    def config() -> E.Effect[int]:
        return E.success(1)

    assert_type(config, E.Effect[int])


def _suspend_negative() -> None:
    def one_arg(x: int) -> int:
        return x

    # The callable must return an Effect.
    E.suspend(lambda: 1)  # ty: ignore[no-matching-overload]
    E.suspend(one_arg)  # ty: ignore[no-matching-overload]

    # The value type comes from the thunk, not from the annotation.
    suspended_int = E.suspend(lambda: E.success(1))
    _must_be_int_suspended: E.Effect[str] = suspended_int  # ty: ignore[invalid-assignment]
