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


def test_test_clock_returns_its_time():
    clock = E.Clock.Test(current=JAN_FIRST)

    result = E.run_sync(E.now().provide(E.Clock.Protocol)(clock))

    assert result == JAN_FIRST


def test_test_clock_starts_at_the_epoch_by_default():
    result = E.run_sync(E.now().provide(E.Clock.Protocol)(E.Clock.Test()))

    assert result == datetime(1970, 1, 1, tzinfo=UTC)


def test_adjust_moves_subsequent_reads():
    clock = E.Clock.Test(JAN_FIRST)

    @E.gen
    def program() -> E.EffectGen[tuple[datetime, datetime]]:
        first = yield from E.now()
        yield from E.sync(lambda: clock.adjust(timedelta(minutes=5)))
        second = yield from E.now()
        return first, second

    result = E.run_sync(program().provide(E.Clock.Protocol)(clock))

    assert result == (JAN_FIRST, JAN_FIRST + timedelta(minutes=5))


def test_set_time_replaces_the_current_time():
    clock = E.Clock.Test()
    clock.set_time(JAN_FIRST)

    result = E.run_sync(E.now().provide(E.Clock.Protocol)(clock))

    assert result == JAN_FIRST


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


def test_test_clock_sleep_parks_until_adjust_reaches_the_wake_time():
    clock = E.Clock.Test(JAN_FIRST)
    p = E.sleep(timedelta(minutes=5)).flat_map(lambda _: E.now())

    async def main():
        task = asyncio.create_task(
            E.run_async_coroutine(p.provide(E.Clock.Protocol)(clock))
        )
        await asyncio.sleep(0)
        parked_before = not task.done()
        clock.adjust(timedelta(minutes=4))
        await asyncio.sleep(0)
        parked_after_partial = not task.done()
        clock.adjust(timedelta(minutes=1))
        return parked_before, parked_after_partial, await task

    parked_before, parked_after_partial, result = asyncio.run(main())

    assert parked_before
    assert parked_after_partial
    assert result == E.Succeeded(JAN_FIRST + timedelta(minutes=5))


def test_test_clock_set_time_past_the_wake_time_wakes_the_sleeper():
    clock = E.Clock.Test(JAN_FIRST)
    p = E.sleep(timedelta(minutes=5)).provide(E.Clock.Protocol)(clock)

    async def main():
        task = asyncio.create_task(E.run_async_coroutine(p))
        await asyncio.sleep(0)
        clock.set_time(JAN_FIRST + timedelta(hours=1))
        return await task

    assert asyncio.run(main()) == E.Succeeded(None)


def test_test_clock_wakes_every_sleeper_that_is_due():
    clock = E.Clock.Test(JAN_FIRST)
    order: list[str] = []

    def sleeper(name: str, minutes: int) -> E.Effect[None]:
        return (
            E.sleep(timedelta(minutes=minutes))
            .map(lambda _: order.append(name))
            .provide(E.Clock.Protocol)(clock)
        )

    async def main():
        short = asyncio.create_task(E.run_async_coroutine(sleeper("short", 1)))
        long = asyncio.create_task(E.run_async_coroutine(sleeper("long", 10)))
        await asyncio.sleep(0)
        clock.adjust(timedelta(minutes=10))
        await asyncio.gather(short, long)

    asyncio.run(main())

    assert sorted(order) == ["long", "short"]


def test_test_clock_sleep_of_zero_returns_without_adjust():
    clock = E.Clock.Test(JAN_FIRST)
    p = E.sleep(timedelta(0)).flat_map(lambda _: E.now())

    result = E.run_async(p.provide(E.Clock.Protocol)(clock))

    assert result == JAN_FIRST


def test_test_clock_sleep_is_async_only():
    p = E.sleep(timedelta(minutes=1)).provide(E.Clock.Protocol)(E.Clock.Test())

    assert E.run_sync_exit(p) == E.Failure(cause=E.Die(defect=E.AsyncEffectInSyncRun()))


def test_test_clock_cancelled_sleep_is_forgotten():
    clock = E.Clock.Test(JAN_FIRST)
    p = E.sleep(timedelta(minutes=5)).provide(E.Clock.Protocol)(clock)

    async def main():
        task = asyncio.create_task(E.run_async_coroutine(p))
        await asyncio.sleep(0)
        task.cancel()
        outcome = await task
        clock.adjust(timedelta(minutes=5))
        return outcome

    match asyncio.run(main()):
        case E.Failure(E.Interrupt(exception)):
            assert isinstance(exception, asyncio.CancelledError)
        case other:
            raise AssertionError(other)
