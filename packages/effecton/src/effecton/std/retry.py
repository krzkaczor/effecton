"""Retries compose catch_all with Clock sleep, driven by a Schedule.

The public shape is the Effect.retry method; this module is not
re-exported. There is no decorator form because the until predicate is
typed by the effect's error channel, which a decorator cannot see.
"""

from collections.abc import Callable, Iterator
from datetime import timedelta

from effecton.effect import Effect, EffectonError, fail
from effecton.std.clock import _sleep
from effecton.std.schedule import Schedule
from effecton.suspend import suspend


def retry[A, E: EffectonError, R](
    effect: Effect[A, E, R],
    schedule: Schedule,
    *,
    until: Callable[[E], bool] | None = None,
) -> Effect[A, E, R]:
    """Re-run effect on a typed failure while schedule recurs.

    Each attempt after the first runs the schedule's next step and waits
    through the Clock for the delay it yields. When the schedule is
    exhausted, or until holds for the error, the retry fails with that
    last error. Defects and interrupts are never retried. Every run takes
    a fresh step sequence, and each step runs inside the retry's
    environment, so a jittered schedule draws through whatever Random is
    provided there.
    """

    def attempt(steps: Iterator[Effect[timedelta]]) -> Effect[A, E, R]:
        def recover(error: E) -> Effect[A, E, R]:
            if until is not None and until(error):
                return fail(error)
            step = next(steps, None)
            if step is None:
                return fail(error)
            return step.flat_map(_sleep).flat_map(lambda _: attempt(steps))

        return effect.catch_all(recover)

    return suspend(lambda: attempt(iter(schedule)))
