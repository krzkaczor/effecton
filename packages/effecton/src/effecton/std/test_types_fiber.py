"""Type-level pins for fibers. Nothing here runs: ty checks the function
bodies and pytest never calls them."""

from dataclasses import dataclass
from typing import Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


def _fork_fiber_carries_the_value_and_error_channels() -> None:
    # Fiber is invariant (it holds a Task), so ty widens a literal value type.
    assert_type(E.fork(E.success(1)), E.Effect[E.Fiber[int, Never]])
    assert_type(E.fork(E.fail(ParseError("x"))), E.Effect[E.Fiber[Never, ParseError]])

    assert_type(E.yield_now(), E.Effect[None])


def _fiber_join_restores_the_channels_wait_and_poll_never_fail(
    fiber: E.Fiber[int, ParseError],
) -> None:
    assert_type(fiber.join(), E.Effect[int, ParseError])
    assert_type(fiber.wait(), E.Effect[E.Succeeded[int] | E.Failure[ParseError]])
    assert_type(fiber.poll(), E.Effect[E.Succeeded[int] | E.Failure[ParseError] | None])
    assert_type(fiber.interrupt(), E.Effect[E.Succeeded[int] | E.Failure[ParseError]])


def _fork_negative() -> None:
    # An effect with unmet requirements cannot be forked.
    E.fork(E.require(str))  # ty: ignore[invalid-argument-type]
