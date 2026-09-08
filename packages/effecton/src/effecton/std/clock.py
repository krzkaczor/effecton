"""Clock service: Protocol plus two live clocks and a Test clock.

The Protocol is an implicit requirement: programs read the time through
E.now() and pause through E.sleep() without declaring anything in R.
Sleeping depends on the runner, so there are two live clocks and each
runner installs the matching one: run_sync installs SyncLive, whose
sleep blocks the thread, and the run_async family installs AsyncLive,
whose sleep awaits asyncio.sleep so the loop keeps turning and a
cancellation interrupts it. Tests override either with
.provide(Protocol)(Test(...)), whose sleep is async only and parks until
adjust or set_time moves the clock to or past the wake time.

The accessors live here as _now and _sleep and are exported only as
E.now and E.sleep, so there is one way to reach the clock rather than
both E.now() and E.Clock.now().
"""

import asyncio
import time
import typing
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Never, final, runtime_checkable

from effecton.effect import Effect, coroutine, sync
from effecton.implicit_requirement import ImplicitRequirement, require_implicit


def _now() -> Effect[datetime]:
    """The current time as a timezone-aware UTC datetime, read from the Clock."""
    return require_implicit(Protocol).flat_map(lambda clock: clock.now())


def _sleep(duration: timedelta) -> Effect[None]:
    """Pause for duration through the Clock; how depends on the runner."""
    return require_implicit(Protocol).flat_map(lambda clock: clock.sleep(duration))


@runtime_checkable
class Protocol(ImplicitRequirement, typing.Protocol):
    def now(self) -> Effect[datetime]: ...

    def sleep(self, duration: timedelta) -> Effect[None]: ...

    @classmethod
    def default(cls) -> Never:
        # Sleeping depends on the runner, so no single clock can be the
        # default: every runner injects its own live clock instead.
        raise RuntimeError(
            "The Clock has no default: run_sync injects SyncLive and the "
            "run_async family injects AsyncLive; provide one explicitly "
            "under a custom interpreter"
        )


@final
@dataclass(frozen=True)
class SyncLive(Protocol):
    """The wall clock with a blocking sleep; run_sync installs it."""

    def now(self) -> Effect[datetime]:
        return sync(lambda: datetime.now(UTC))

    def sleep(self, duration: timedelta) -> Effect[None]:
        return sync(lambda: time.sleep(duration.total_seconds()))


@final
@dataclass(frozen=True)
class AsyncLive(Protocol):
    """The wall clock with an awaiting sleep; the run_async family installs it."""

    def now(self) -> Effect[datetime]:
        return sync(lambda: datetime.now(UTC))

    def sleep(self, duration: timedelta) -> Effect[None]:
        return coroutine(lambda: asyncio.sleep(duration.total_seconds()))


@final
@dataclass
class Test(Protocol):
    """A clock that only moves when told to.

    Pass current to start elsewhere; the default is the Unix epoch. sleep
    is async only: it parks until adjust or set_time moves the clock to
    or past the wake time. Both movers are effects, so a test written as
    an effect moves the clock with yield from, and the effecton pytest
    plugin provides this clock to such a test through its test_clock
    fixture.
    """

    __test__ = False

    current: datetime = datetime(1970, 1, 1, tzinfo=UTC)
    _sleepers: list[tuple[datetime, asyncio.Future[None]]] = field(
        default_factory=list, repr=False, compare=False
    )

    def now(self) -> Effect[datetime]:
        return sync(lambda: self.current)

    def sleep(self, duration: timedelta) -> Effect[None]:
        async def wait() -> None:
            # A zero sleep must not park until the next adjust.
            if duration == timedelta(0):
                return
            wake_at = self.current + duration
            sleeper = (wake_at, asyncio.get_running_loop().create_future())
            self._sleepers.append(sleeper)
            try:
                await sleeper[1]
            finally:
                if sleeper in self._sleepers:
                    self._sleepers.remove(sleeper)

        return coroutine(wait)

    def adjust(self, delta: timedelta) -> Effect[None]:
        return self.set_time(self.current + delta)

    def set_time(self, time: datetime) -> Effect[None]:
        """Move the clock, waking every sleeper whose wake time has come.

        Async only, like sleep. The move yields to the loop before and
        after, so a program forked just before reaches its sleep and
        registers, and the woken programs progress before the caller
        continues.
        """

        async def move() -> None:
            await asyncio.sleep(0)
            self.current = time
            due = [sleeper for sleeper in self._sleepers if sleeper[0] <= time]
            for sleeper in due:
                self._sleepers.remove(sleeper)
                sleeper[1].set_result(None)
            await asyncio.sleep(0)

        return coroutine(move)
