"""Random service: Protocol plus a Live generator and a seeded Test one.

The Protocol is an implicit requirement: programs draw randomness by
resolving the service with E.random() and calling its methods, which keep
the names of the random standard library, without declaring anything in
R. Live is the default and delegates to the module-level functions, so
it shares the process-global generator; it holds no state of its own,
which is what lets the interpreter memoize it once per process. Tests
override it with .provide(Protocol)(Test(seed)), whose private generator
makes every draw a function of the seed.

The accessor lives here as _random and is exported only as E.random, so
there is one way to reach the service rather than both E.random() and
E.Random.random().
"""

import random
import typing
from collections.abc import Sequence
from dataclasses import dataclass, field
from random import Random
from typing import final, runtime_checkable

from effecton.effect import Effect, sync
from effecton.implicit_requirement import ImplicitRequirement, require_implicit


def _random() -> Effect[Protocol]:
    """The Random service, resolved from the environment or its default."""
    return require_implicit(Protocol)


@runtime_checkable
class Protocol(ImplicitRequirement, typing.Protocol):
    def random(self) -> Effect[float]:
        """A float in [0.0, 1.0)."""
        ...

    def uniform(self, a: float, b: float) -> Effect[float]:
        """A float in [a, b]."""
        ...

    def randint(self, a: int, b: int) -> Effect[int]:
        """An int in [a, b], both ends included."""
        ...

    def choice[T](self, seq: Sequence[T]) -> Effect[T]:
        """One element of a non-empty sequence."""
        ...

    def shuffle[T](self, seq: Sequence[T]) -> Effect[list[T]]:
        """A new list with the elements of seq in random order; seq is untouched."""
        ...

    @classmethod
    def default(cls) -> Protocol:
        return Live()


@final
@dataclass(frozen=True)
class Live(Protocol):
    """The process-global generator behind the random module's functions."""

    def random(self) -> Effect[float]:
        return sync(random.random)

    def uniform(self, a: float, b: float) -> Effect[float]:
        return sync(lambda: random.uniform(a, b))

    def randint(self, a: int, b: int) -> Effect[int]:
        return sync(lambda: random.randint(a, b))

    def choice[T](self, seq: Sequence[T]) -> Effect[T]:
        return sync(lambda: random.choice(seq))

    def shuffle[T](self, seq: Sequence[T]) -> Effect[list[T]]:
        def go() -> list[T]:
            items = list(seq)
            random.shuffle(items)
            return items

        return sync(go)


@final
@dataclass
class Test(Protocol):
    """A generator seeded once, so the same seed always yields the same draws.

    The default seed is 0. Each instance advances on its own: provide one
    instance to every effect whose draws should form a single sequence.
    """

    seed: int = 0
    _rng: Random = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._rng = Random(self.seed)

    def random(self) -> Effect[float]:
        return sync(self._rng.random)

    def uniform(self, a: float, b: float) -> Effect[float]:
        return sync(lambda: self._rng.uniform(a, b))

    def randint(self, a: int, b: int) -> Effect[int]:
        return sync(lambda: self._rng.randint(a, b))

    def choice[T](self, seq: Sequence[T]) -> Effect[T]:
        return sync(lambda: self._rng.choice(seq))

    def shuffle[T](self, seq: Sequence[T]) -> Effect[list[T]]:
        def go() -> list[T]:
            items = list(seq)
            self._rng.shuffle(items)
            return items

        return sync(go)
