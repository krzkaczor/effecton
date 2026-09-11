"""Type-level pins for the async runners. Nothing here runs: ty checks the
function bodies and pytest never calls them."""

import asyncio
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


async def fetch() -> int:
    return 1


def _coroutine_value_from_the_awaitable_error_channel_stays_never() -> None:
    assert_type(E.coroutine(fetch), E.Effect[int])
    assert_type(E.coroutine(lambda: asyncio.sleep(0, "x")), E.Effect[Literal["x"]])


def _attempt_async_value_from_the_awaitable_error_from_the_mapper() -> None:
    assert_type(
        E.attempt_async(fetch, lambda e: ParseError(str(e))), E.Effect[int, ParseError]
    )

    failing = E.coroutine(fetch).flat_map(lambda _: E.fail(ParseError("x")))
    assert_type(failing, E.Effect[Never, ParseError])


async def _run_async_coroutine_produces_an_exit_matching_the_channels() -> None:
    failing = E.coroutine(fetch).flat_map(lambda _: E.fail(ParseError("x")))

    assert_type(
        await E.run_async_coroutine(E.coroutine(fetch)), E.Succeeded[int] | E.Failure
    )
    assert_type(
        await E.run_async_coroutine(failing), E.Succeeded[Never] | E.Failure[ParseError]
    )

    # A pure-sync effect runs under run_async_coroutine too.
    assert_type(
        await E.run_async_coroutine(E.success(1)), E.Succeeded[Literal[1]] | E.Failure
    )

    # An unmet requirement makes the effect unrunnable here as well.
    await E.run_async_coroutine(E.require(Db))  # ty: ignore[invalid-argument-type]


def _run_async_exit_returns_the_same_exit_and_run_async_the_value() -> None:
    failing = E.coroutine(fetch).flat_map(lambda _: E.fail(ParseError("x")))

    assert_type(E.run_async_exit(E.coroutine(fetch)), E.Succeeded[int] | E.Failure)
    assert_type(E.run_async_exit(failing), E.Succeeded[Never] | E.Failure[ParseError])
    assert_type(E.run_async(E.coroutine(fetch)), int)
    assert_type(E.run_async(E.success(1)), Literal[1])

    # An unmet requirement is a type error for every runner.
    E.run_async_exit(E.require(Db))  # ty: ignore[invalid-argument-type]
    E.run_async(E.require(Db))  # ty: ignore[invalid-argument-type]


def _coroutine_negative() -> None:
    def not_awaitable() -> int:
        return 1

    # The thunk must return an awaitable.
    E.coroutine(not_awaitable)  # ty: ignore[invalid-argument-type]

    # The thunk takes no arguments.
    E.coroutine(asyncio.sleep)  # ty: ignore[invalid-argument-type]
