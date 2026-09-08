import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest

import effecton as E

JAN_FIRST = datetime(2024, 1, 1, tzinfo=UTC)


def test_default_clock_is_the_live_wall_clock():
    before = datetime.now(UTC)

    result = E.run_sync(E.now())

    assert result.tzinfo is UTC
    assert before <= result <= datetime.now(UTC)


def test_run_sync_installs_the_sync_live_clock():
    clock = E.run_sync(E.require_implicit(E.Clock.Protocol))

    assert isinstance(clock, E.Clock.SyncLive)


def test_run_async_installs_the_async_live_clock():
    clock = E.run_async(E.require_implicit(E.Clock.Protocol))

    assert isinstance(clock, E.Clock.AsyncLive)


def test_protocol_has_no_default_because_runners_inject_a_clock():
    with pytest.raises(RuntimeError, match="run_sync injects SyncLive"):
        E.Clock.Protocol.default()


@E.gen
def test_test_clock_starts_at_the_epoch_by_default(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    result = yield from E.now()

    assert result == datetime(1970, 1, 1, tzinfo=UTC)


@E.gen
def test_set_time_replaces_the_current_time(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    yield from test_clock.set_time(JAN_FIRST)

    result = yield from E.now()

    assert result == JAN_FIRST


@E.gen
def test_adjust_moves_subsequent_reads(test_clock: E.Clock.Test) -> E.EffectGen[None]:
    yield from test_clock.set_time(JAN_FIRST)

    first = yield from E.now()
    yield from test_clock.adjust(timedelta(minutes=5))
    second = yield from E.now()

    assert (first, second) == (JAN_FIRST, JAN_FIRST + timedelta(minutes=5))


def test_override_is_scoped_to_the_wrapped_effect():
    overridden = E.now().provide(E.Clock.Protocol)(E.Clock.Test(JAN_FIRST))
    after = overridden.flat_map(lambda inner: E.now().map(lambda outer: (inner, outer)))

    inner, outer = E.run_sync(after)

    assert inner == JAN_FIRST
    assert outer > JAN_FIRST


def test_sync_live_sleep_blocks_for_the_duration():
    start = time.monotonic()

    result = E.run_sync(E.sleep(timedelta(milliseconds=10)))

    assert result is None
    assert time.monotonic() - start >= 0.01


def test_async_live_sleep_awaits_for_the_duration():
    start = time.monotonic()

    result = E.run_async(E.sleep(timedelta(milliseconds=10)))

    assert result is None
    assert time.monotonic() - start >= 0.01


def test_async_live_sleep_is_interrupted_by_a_timeout():
    async def main():
        async with asyncio.timeout(0.01):
            return await E.run_async_coroutine(E.sleep(timedelta(hours=1)))

    match asyncio.run(main()):
        case E.Failure(E.Interrupt(exception)):
            assert isinstance(exception, asyncio.CancelledError)
        case other:
            raise AssertionError(other)


def test_async_live_sleep_dies_under_run_sync():
    p = E.sleep(timedelta(0)).provide(E.Clock.Protocol)(E.Clock.AsyncLive())

    assert E.run_sync_exit(p) == E.Failure(cause=E.Die(defect=E.AsyncEffectInSyncRun()))


def test_sync_live_sleep_blocks_under_run_async():
    p = E.sleep(timedelta(milliseconds=10)).provide(E.Clock.Protocol)(
        E.Clock.SyncLive()
    )
    start = time.monotonic()

    result = E.run_async(p)

    assert result is None
    assert time.monotonic() - start >= 0.01


@E.gen
def test_test_clock_sleep_parks_until_adjust_reaches_the_wake_time(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    yield from test_clock.set_time(JAN_FIRST)
    sleeper = E.sleep(timedelta(minutes=5)).flat_map(lambda _: E.now())
    fiber = yield from E.fork(sleeper.provide(E.Clock.Protocol)(test_clock))

    yield from test_clock.adjust(timedelta(minutes=4))
    parked = yield from fiber.poll()
    yield from test_clock.adjust(timedelta(minutes=1))
    result = yield from fiber.wait()

    assert parked is None
    assert result == E.Succeeded(JAN_FIRST + timedelta(minutes=5))


@E.gen
def test_test_clock_set_time_past_the_wake_time_wakes_the_sleeper(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    yield from test_clock.set_time(JAN_FIRST)
    sleeper = E.sleep(timedelta(minutes=5)).provide(E.Clock.Protocol)(test_clock)
    fiber = yield from E.fork(sleeper)

    yield from test_clock.set_time(JAN_FIRST + timedelta(hours=1))
    result = yield from fiber.wait()

    assert result == E.Succeeded(None)


@E.gen
def test_test_clock_wakes_every_sleeper_that_is_due(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    order: list[str] = []

    def sleeper(name: str, minutes: int) -> E.Effect[None]:
        return (
            E.sleep(timedelta(minutes=minutes))
            .map(lambda _: order.append(name))
            .provide(E.Clock.Protocol)(test_clock)
        )

    short = yield from E.fork(sleeper("short", 1))
    long = yield from E.fork(sleeper("long", 10))

    yield from test_clock.adjust(timedelta(minutes=10))
    yield from short.join()
    yield from long.join()

    assert sorted(order) == ["long", "short"]


@E.gen
def test_test_clock_sleep_of_zero_returns_without_adjust(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    yield from test_clock.set_time(JAN_FIRST)

    yield from E.sleep(timedelta(0))
    result = yield from E.now()

    assert result == JAN_FIRST


def test_test_clock_sleep_is_async_only():
    p = E.sleep(timedelta(minutes=1)).provide(E.Clock.Protocol)(E.Clock.Test())

    assert E.run_sync_exit(p) == E.Failure(cause=E.Die(defect=E.AsyncEffectInSyncRun()))


def test_test_clock_movers_are_async_only():
    p = E.Clock.Test().adjust(timedelta(minutes=1))

    assert E.run_sync_exit(p) == E.Failure(cause=E.Die(defect=E.AsyncEffectInSyncRun()))


@E.gen
def test_test_clock_cancelled_sleep_is_forgotten(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    sleeper = E.sleep(timedelta(minutes=5)).provide(E.Clock.Protocol)(test_clock)
    fiber = yield from E.fork(sleeper)
    yield from E.yield_now()  # let the fiber park

    outcome = yield from fiber.interrupt()
    yield from test_clock.adjust(timedelta(minutes=5))

    match outcome:
        case E.Failure(E.Interrupt(exception)):
            assert isinstance(exception, asyncio.CancelledError)
        case other:
            raise AssertionError(other)
