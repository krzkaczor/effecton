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


# --- coroutine: value inferred from the awaitable, error channel stays Never ---

assert_type(E.coroutine(fetch), E.Effect[int])
assert_type(E.coroutine(lambda: asyncio.sleep(0, "x")), E.Effect[Literal["x"]])

# --- attempt_async: value from the awaitable, error from the mapper ---

assert_type(
    E.attempt_async(fetch, lambda e: ParseError(str(e))), E.Effect[int, ParseError]
)

failing = E.coroutine(fetch).flat_map(lambda _: E.fail(ParseError("x")))
assert_type(failing, E.Effect[Never, ParseError])


# --- run_async produces an Exit matching the effect's channels ---
# Type-checked only; never called.
async def _run_async_pins() -> None:
    assert_type(await E.run_async(E.coroutine(fetch)), E.Succeeded[int] | E.Failure)
    assert_type(await E.run_async(failing), E.Succeeded[Never] | E.Failure[ParseError])

    # A pure-sync effect runs under run_async too.
    assert_type(await E.run_async(E.success(1)), E.Succeeded[Literal[1]] | E.Failure)

    # An unmet requirement makes the effect unrunnable under run_async as well.
    await E.run_async(E.require(Db))  # ty: ignore[invalid-argument-type]


# --- negative tests ---


def _not_awaitable() -> int:
    return 1


# The thunk must return an awaitable.
E.coroutine(_not_awaitable)  # ty: ignore[invalid-argument-type]

# The thunk takes no arguments.
E.coroutine(asyncio.sleep)  # ty: ignore[invalid-argument-type]
