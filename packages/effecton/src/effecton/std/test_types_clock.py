"""Type-level pins for the Clock service. Nothing here runs: ty checks the
function bodies and pytest never calls them, so nothing sleeps."""

from datetime import datetime, timedelta
from typing import assert_type

import effecton as E


def _now_and_sleep_are_implicit_reads_so_r_stays_never() -> None:
    assert_type(E.now(), E.Effect[datetime])
    assert_type(E.run_sync(E.now()), datetime)
    assert_type(E.sleep(timedelta(seconds=1)), E.Effect[None])
    assert_type(E.require_implicit(E.Clock.Protocol), E.Effect[E.Clock.Protocol])
    assert_type(E.run_sync(E.sleep(timedelta(seconds=1))), None)
    assert_type(E.run_async(E.sleep(timedelta(seconds=1))), None)


def _provide_any_implementation_overrides_the_runner_live_clock() -> None:
    assert_type(E.now().provide(E.Clock.Protocol)(E.Clock.Test()), E.Effect[datetime])
    assert_type(
        E.now().provide(E.Clock.Protocol)(E.Clock.SyncLive()), E.Effect[datetime]
    )
    assert_type(
        E.now().provide(E.Clock.Protocol)(E.Clock.AsyncLive()), E.Effect[datetime]
    )
    assert_type(
        E.sleep(timedelta(seconds=1)).provide(E.Clock.Protocol)(E.Clock.Test()),
        E.Effect[None],
    )


def _clock_negative() -> None:
    # Only a Clock implementation can be provided as the Clock.
    E.now().provide(E.Clock.Protocol)(object())  # ty: ignore[invalid-argument-type]

    # The duration is a timedelta, not a number of seconds.
    E.sleep(1)  # ty: ignore[invalid-argument-type]
