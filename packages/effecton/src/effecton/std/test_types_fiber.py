from dataclasses import dataclass
from typing import Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


# --- fork: the fiber carries the effect's value and error channels ---
# Fiber is invariant (it holds a Task), so ty widens a literal value type.

assert_type(E.fork(E.success(1)), E.Effect[E.Fiber[int, Never]])
assert_type(E.fork(E.fail(ParseError("x"))), E.Effect[E.Fiber[Never, ParseError]])


assert_type(E.yield_now(), E.Effect[None])


# --- Fiber: join restores the channels, wait and poll never fail ---
# Type-checked only; never called.
def _fiber_pins(fiber: E.Fiber[int, ParseError]) -> None:
    assert_type(fiber.join(), E.Effect[int, ParseError])
    assert_type(fiber.wait(), E.Effect[E.Succeeded[int] | E.Failure[ParseError]])
    assert_type(fiber.poll(), E.Effect[E.Succeeded[int] | E.Failure[ParseError] | None])
    assert_type(fiber.interrupt(), E.Effect[E.Succeeded[int] | E.Failure[ParseError]])


# --- negative tests ---

# An effect with unmet requirements cannot be forked.
E.fork(E.require(str))  # ty: ignore[invalid-argument-type]
