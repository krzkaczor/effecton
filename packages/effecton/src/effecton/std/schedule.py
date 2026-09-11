"""Schedules: sequences of delays that drive retry.

A Schedule is a factory of delay sequences. Every run of the combinator
it drives takes a fresh iterator, so one schedule value can be shared
and reused. Each element is the delay to wait before the next attempt,
and exhaustion ends the recurrence.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from itertools import count, repeat
from typing import final


@final
@dataclass(frozen=True)
class Schedule:
    """A recurrence policy: how often to recur and how long to wait first.

    The constructors cover the basic policies; pass delays directly to
    build a custom one from any callable that yields a fresh iterator.
    """

    delays: Callable[[], Iterator[timedelta]]

    @staticmethod
    def recurs(times: int) -> Schedule:
        """Recur up to times more times, without waiting."""
        return Schedule(lambda: repeat(timedelta(0), times))

    @staticmethod
    def spaced(delay: timedelta) -> Schedule:
        """Recur forever, waiting delay before each attempt."""
        return Schedule(lambda: repeat(delay))

    @staticmethod
    def exponential(base: timedelta, factor: float = 2.0) -> Schedule:
        """Recur forever, waiting base, then base * factor, and so on."""
        return Schedule(lambda: (base * factor**i for i in count()))

    def __iter__(self) -> Iterator[timedelta]:
        return self.delays()
