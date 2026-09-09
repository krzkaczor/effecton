import asyncio
from datetime import timedelta

import pytest

import effecton as E

FIVE_SECONDS = timedelta(seconds=5)
TIMED_OUT = E.Failure(cause=E.Fail(error=E.TimeoutException(FIVE_SECONDS)))


def forever() -> E.Effect[bool]:
    return E.coroutine(lambda: asyncio.Event().wait())


def test_timeout_exception_renders_the_duration():
    assert str(E.TimeoutException(FIVE_SECONDS)) == "Timed out after 0:00:05"


def test_a_fast_effect_completes_under_the_live_clock():
    result = E.run_async(E.success(1).timeout(FIVE_SECONDS))

    assert result == 1


@E.gen
def test_the_clock_passing_the_deadline_fails_with_timeout_exception(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    program = forever().timeout(FIVE_SECONDS).provide(E.Clock.Protocol)(test_clock)
    fiber = yield from E.fork(program)

    yield from test_clock.adjust(FIVE_SECONDS)
    result = yield from fiber.wait()

    assert result == TIMED_OUT


@E.gen
def test_the_timed_out_effect_is_interrupted_before_the_failure_is_returned(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    actions: list[str] = []
    program = (
        forever()
        .on_exit(E.sync(lambda: actions.append("finalized")))
        .timeout(FIVE_SECONDS)
        .catch_all(lambda e: E.sync(lambda: actions.append(str(e))))
        .provide(E.Clock.Protocol)(test_clock)
    )
    fiber = yield from E.fork(program)

    yield from test_clock.adjust(FIVE_SECONDS)
    yield from fiber.join()

    assert actions == ["finalized", "Timed out after 0:00:05"]


@E.gen
def test_a_clock_that_stops_short_does_not_fire(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    gate = asyncio.Event()
    program = E.coroutine(gate.wait).timeout(FIVE_SECONDS)
    fiber = yield from E.fork(program.provide(E.Clock.Protocol)(test_clock))

    yield from test_clock.adjust(FIVE_SECONDS - timedelta(seconds=1))
    pending = yield from fiber.poll()
    yield from E.sync(gate.set)
    result = yield from fiber.wait()

    assert pending is None
    assert result == E.Succeeded(True)


@E.gen
def test_catch_handles_the_timeout(test_clock: E.Clock.Test) -> E.EffectGen[None]:
    program = (
        forever()
        .timeout(FIVE_SECONDS)
        .catch(E.TimeoutException)(lambda e: E.success(f"late by {e.duration}"))
        .provide(E.Clock.Protocol)(test_clock)
    )
    fiber = yield from E.fork(program)

    yield from test_clock.adjust(FIVE_SECONDS)
    result = yield from fiber.join()

    assert result == "late by 0:00:05"


@E.gen
def test_the_timed_effect_inherits_the_environment() -> E.EffectGen[
    None, E.TimeoutException
]:
    program = E.require(str).timeout(FIVE_SECONDS).provide(str)("provided")

    result = yield from program

    assert result == "provided"


@pytest.mark.parametrize("inner", [timedelta(seconds=1), timedelta(hours=1)])
@E.gen
def test_nested_timeouts_use_the_earlier_deadline_and_finalize(
    test_clock: E.Clock.Test,
    inner: timedelta,
) -> E.EffectGen[None]:
    actions: list[str] = []
    deadline = min(inner, FIVE_SECONDS)
    program = (
        forever()
        .on_exit(E.sync(lambda: actions.append("finalized")))
        .timeout(inner)
        .timeout(FIVE_SECONDS)
        .provide(E.Clock.Protocol)(test_clock)
    )
    fiber = yield from E.fork(program)

    yield from test_clock.adjust(deadline)
    result = yield from fiber.wait()

    assert result == E.Failure(E.Fail(E.TimeoutException(deadline)))
    assert actions == ["finalized"]


@E.gen
def test_the_winners_timer_is_cancelled(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None, E.TimeoutException]:
    yield from E.success(1).timeout(FIVE_SECONDS)

    tasks = yield from E.sync(asyncio.all_tasks)

    assert tasks == {asyncio.current_task()}


def test_the_live_clock_fires_a_timeout():
    program = forever().timeout(timedelta(milliseconds=10))

    result = E.run_async_exit(program)

    assert result == E.Failure(
        cause=E.Fail(error=E.TimeoutException(timedelta(milliseconds=10)))
    )


@E.gen
def test_the_decorator_wraps_every_result(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    @E.timeout(FIVE_SECONDS)
    @E.gen
    def wait_for(name: str) -> E.EffectGen[str]:
        yield from forever()
        return name

    fiber = yield from E.fork(wait_for("x").provide(E.Clock.Protocol)(test_clock))

    yield from test_clock.adjust(FIVE_SECONDS)
    result = yield from fiber.wait()

    assert wait_for.__name__ == "wait_for"
    assert result == TIMED_OUT


@E.gen
def test_the_curried_form_applies_to_an_effect() -> E.EffectGen[
    None, E.TimeoutException
]:
    program = E.timeout(FIVE_SECONDS)(E.success("done"))

    result = yield from program

    assert result == "done"


def test_timeout_dies_under_run_sync():
    p = E.success(1).timeout(FIVE_SECONDS)

    assert E.run_sync_exit(p) == E.Failure(cause=E.Die(defect=E.AsyncEffectInSyncRun()))


def test_a_clock_defect_passes_through_and_interrupts_the_effect():
    defect = ValueError("clock failed")
    actions: list[str] = []

    class BrokenClock(E.Clock.Protocol):
        def now(self):
            return E.die(defect)

        def sleep(self, duration):
            return E.die(defect)

    program = (
        forever()
        .on_exit(E.sync(lambda: actions.append("finalized")))
        .timeout(FIVE_SECONDS)
        .provide(E.Clock.Protocol)(BrokenClock())
    )

    result = E.run_async_exit(program)

    assert result == E.Failure(E.Die(defect))
    assert actions == ["finalized"]
