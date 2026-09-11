"""Schedules: sequences of delay steps that drive retry.

A Schedule is a factory of step sequences. Every run of the combinator
it drives takes a fresh iterator, so one schedule value can be shared
and reused. Each step is an effect yielding the delay to wait before the
next attempt, so a step can consult a service such as Random, and
exhaustion ends the recurrence.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from itertools import count, repeat
from typing import final

from effecton.effect import Effect, success
from effecton.gen import EffectGen, gen
from effecton.std.random import _random


@final
@dataclass(frozen=True)
class Schedule:
    """A recurrence policy: how often to recur and how long to wait first.

    The constructors cover the basic policies; from_delays builds a custom
    one from any callable that yields a fresh iterator of delays, and
    passing steps directly admits delays computed by effects.
    """

    steps: Callable[[], Iterator[Effect[timedelta]]]

    @staticmethod
    def from_delays(delays: Callable[[], Iterator[timedelta]]) -> Schedule:
        """A schedule whose steps are the plain delays the callable yields."""
        return Schedule(lambda: map(success, delays()))

    @staticmethod
    def recurs(times: int) -> Schedule:
        """Recur up to times more times, without waiting."""
        return Schedule(lambda: repeat(success(timedelta(0)), times))

    @staticmethod
    def spaced(delay: timedelta) -> Schedule:
        """Recur forever, waiting delay before each attempt."""
        return Schedule(lambda: repeat(success(delay)))

    @staticmethod
    def exponential(base: timedelta, factor: float = 2.0) -> Schedule:
        """Recur forever, waiting base, then base * factor, and so on."""
        return Schedule(lambda: (success(base * factor**i) for i in count()))

    def jittered(self, *, min: float = 0.8, max: float = 1.2) -> Schedule:
        """Scale each delay by a factor drawn uniformly from [min, max].

        The factor comes from the Random service, so providing Random.Test
        makes the jitter deterministic.
        """

        @gen
        def jitter(step: Effect[timedelta]) -> EffectGen[timedelta]:
            rng = yield from _random()

            delay = yield from step
            factor = yield from rng.uniform(min, max)
            return delay * factor

        return Schedule(lambda: map(jitter, self.steps()))

    def __iter__(self) -> Iterator[Effect[timedelta]]:
        return self.steps()
