"""Type-level pins for the core Effect API and the sync runners. Nothing
here runs: ty checks the function bodies and pytest never calls them."""

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


@dataclass(frozen=True)
class Db:
    url: str


@dataclass(frozen=True)
class Logger:
    level: str


@dataclass(frozen=True)
class Cache:
    size: int


def parse(s: str) -> E.Effect[int, ParseError]:
    try:
        return E.success(int(s))
    except ValueError:
        return E.fail(ParseError(s))


def _constructors() -> None:
    # ty infers the literal type of the argument; covariance widens it
    # wherever an Effect[int] is expected.
    assert_type(E.success(1), E.Effect[Literal[1]])
    assert_type(E.fail(ParseError("x")), E.Effect[Never, ParseError])
    assert_type(E.die("boom"), E.Effect[Never])


def _map_keeps_the_error_channel_and_transforms_the_value() -> None:
    assert_type(E.success(1).map(lambda x: str(x)), E.Effect[str])
    assert_type(parse("1").map(lambda x: x * 2), E.Effect[int, ParseError])


def _flat_map_accumulates_errors_as_a_union() -> None:
    chain = parse("1").flat_map(
        lambda x: E.success(x) if x > 0 else E.fail(NegativeError(x))
    )
    assert_type(chain, E.Effect[int, ParseError | NegativeError])


def _catch_all_replaces_the_error_channel() -> None:
    assert_type(
        E.fail(ParseError("x")).catch_all(lambda _: E.success(0)),
        E.Effect[Literal[0]],
    )

    def partial_handler(e: ParseError | NegativeError) -> E.Effect[int, ParseError]:
        match e:
            case NegativeError():
                return E.success(0)
            case ParseError():
                return E.fail(e)

    chain = parse("1").flat_map(
        lambda x: E.success(x) if x > 0 else E.fail(NegativeError(x))
    )
    assert_type(chain.catch_all(partial_handler), E.Effect[int, ParseError])


def _run_sync_exit_produces_an_exit_and_run_sync_the_value() -> None:
    chain = parse("1").flat_map(
        lambda x: E.success(x) if x > 0 else E.fail(NegativeError(x))
    )

    # run_sync_exit produces an Exit matching the effect's channels.
    assert_type(
        E.run_sync_exit(chain), E.Succeeded[int] | E.Failure[ParseError | NegativeError]
    )
    assert_type(E.run_sync_exit(E.success(1)), E.Succeeded[int] | E.Failure)

    # run_sync produces the value; failures raise instead.
    assert_type(E.run_sync(chain), int)
    assert_type(E.run_sync(E.success(1)), Literal[1])


def _cause_has_three_states_and_only_fail_carries_the_typed_error() -> None:
    _typed_failure: E.Cause[ParseError] = E.Fail(ParseError("x"))
    _defect: E.Cause[ParseError] = E.Die("boom")
    _interrupt: E.Cause[ParseError] = E.Interrupt(KeyboardInterrupt())
    _never_fails: E.Cause[Never] = E.Interrupt(KeyboardInterrupt())

    # A Fail of another error type does not fit.
    _wrong_error: E.Cause[ParseError] = E.Fail(NegativeError(1))  # ty: ignore[invalid-assignment]


def _sync_value_inferred_from_the_thunk_error_channel_stays_never() -> None:
    assert_type(E.sync(lambda: 1), E.Effect[Literal[1]])
    assert_type(E.sync(lambda: "1").flat_map(parse), E.Effect[int, ParseError])
    assert_type(E.run_sync_exit(E.sync(lambda: 1)), E.Succeeded[int] | E.Failure)


def _sync_negative() -> None:
    def one_arg(x: int) -> int:
        return x

    # The thunk takes no arguments.
    E.sync(one_arg)  # ty: ignore[invalid-argument-type]

    # The value type comes from the thunk, not from the annotation.
    sync_int = E.sync(lambda: 1)
    _must_be_int: E.Effect[str] = sync_int  # ty: ignore[invalid-assignment]


def _variance_a_and_e_are_both_covariant() -> None:
    _widened_value: E.Effect[object, E.EffectonError] = E.success(1)
    _widened_error: E.Effect[int, ParseError] = E.fail(ParseError("x"))
    _success_fits_any_error: E.Effect[int, ParseError | NegativeError] = E.success(1)


def _negative() -> None:
    # The error type must extend EffectonError.
    E.fail(ValueError("x"))  # ty: ignore[invalid-argument-type]

    # The error channel does not narrow implicitly.
    parse_failure = E.fail(ParseError("x"))
    _must_not_narrow: E.Effect[int] = parse_failure  # ty: ignore[invalid-assignment]

    def wrong_input(x: str) -> E.Effect[int]:
        return E.success(len(x))

    # The flat_map callback must accept the effect's value type.
    E.success(1).flat_map(wrong_input)  # ty: ignore[invalid-argument-type]

    # The map result type is not the original value type.
    mapped_str = E.success(1).map(lambda x: str(x))
    _must_be_str: E.Effect[int] = mapped_str  # ty: ignore[invalid-assignment]


def _require_adds_to_the_r_channel() -> None:
    assert_type(E.require(Db), E.Effect[Db, Never, Db])

    needs_two = E.require(Db).flat_map(
        lambda db: E.require(Logger).map(lambda logger: (db, logger))
    )
    assert_type(needs_two, E.Effect[tuple[Db, Logger], Never, Db | Logger])

    needs_three = needs_two.flat_map(
        lambda pair: E.require(Cache).map(lambda cache: (*pair, cache))
    )
    assert_type(
        needs_three, E.Effect[tuple[Db, Logger, Cache], Never, Db | Logger | Cache]
    )

    # Requiring the same type twice adds it only once.
    needs_db_twice = E.require(Db).flat_map(
        lambda a: E.require(Db).map(lambda b: (a, b))
    )
    assert_type(needs_db_twice, E.Effect[tuple[Db, Db], Never, Db])


def _on_exit_preserves_all_three_channels_and_discards_the_finalizer_value() -> None:
    assert_type(E.success(1).on_exit(E.success("cleanup")), E.Effect[Literal[1]])
    assert_type(parse("1").on_exit(E.success(0)), E.Effect[int, ParseError])
    assert_type(E.require(Db).on_exit(E.success(0)), E.Effect[Db, Never, Db])

    # A finalizer can die (defects are unchecked).
    assert_type(E.success(1).on_exit(E.die("boom")), E.Effect[Literal[1]])

    # A finalizer can have requirements: they union into R.
    assert_type(E.success(1).on_exit(E.require(Db)), E.Effect[Literal[1], Never, Db])
    assert_type(
        E.require(Logger).on_exit(E.require(Db)), E.Effect[Logger, Never, Logger | Db]
    )


def _on_exit_negative() -> None:
    # The finalizer cannot have a typed error channel.
    E.success(1).on_exit(E.fail(ParseError("x")))  # ty: ignore[invalid-argument-type]

    # A finalizer requirement makes the effect unrunnable until provided.
    E.run_sync_exit(E.success(1).on_exit(E.require(Db)))  # ty: ignore[invalid-argument-type]
    E.run_sync(E.success(1).on_exit(E.require(Db)))  # ty: ignore[invalid-argument-type]
