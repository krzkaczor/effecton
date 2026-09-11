from dataclasses import dataclass
from datetime import timedelta
from typing import final

import effecton as E

ONE_SECOND = timedelta(seconds=1)
FIVE_SECONDS = timedelta(seconds=5)


@final
@dataclass(frozen=True)
class Boom(E.EffectonError):
    attempt: int


@dataclass
class Flaky:
    """Fails with Boom on every attempt before succeed_on; None never succeeds."""

    succeed_on: int | None
    attempts: int = 0

    def run(self) -> E.Effect[str, Boom]:
        def go() -> E.Effect[str, Boom]:
            self.attempts += 1
            if self.succeed_on is None or self.attempts < self.succeed_on:
                return E.fail(Boom(self.attempts))
            return E.success("ok")

        return E.suspend(go)


def test_recurs_retries_until_the_effect_succeeds():
    flaky = Flaky(succeed_on=3)
    program = flaky.run().retry(E.Schedule.recurs(3))

    result = E.run_sync(program)

    assert result == "ok"
    assert flaky.attempts == 3


def test_an_exhausted_schedule_fails_with_the_last_error():
    flaky = Flaky(succeed_on=None)
    program = flaky.run().retry(E.Schedule.recurs(3))

    result = E.run_sync_exit(program)

    assert result == E.Failure(E.Fail(Boom(4)))
    assert flaky.attempts == 4


def test_recurs_zero_runs_the_effect_once():
    flaky = Flaky(succeed_on=None)
    program = flaky.run().retry(E.Schedule.recurs(0))

    result = E.run_sync_exit(program)

    assert result == E.Failure(E.Fail(Boom(1)))
    assert flaky.attempts == 1


def test_until_stops_retrying_with_the_matched_error():
    flaky = Flaky(succeed_on=None)
    program = flaky.run().retry(E.Schedule.recurs(5), until=lambda e: e.attempt == 2)

    result = E.run_sync_exit(program)

    assert result == E.Failure(E.Fail(Boom(2)))
    assert flaky.attempts == 2


def test_until_lets_the_effect_succeed_when_it_never_holds():
    flaky = Flaky(succeed_on=2)
    program = flaky.run().retry(E.Schedule.recurs(5), until=lambda e: e.attempt > 10)

    result = E.run_sync(program)

    assert result == "ok"
    assert flaky.attempts == 2


def test_a_raising_predicate_is_a_defect():
    defect = ValueError("bad predicate")

    def explode(error: Boom) -> bool:
        raise defect

    program = Flaky(succeed_on=None).run().retry(E.Schedule.recurs(3), until=explode)

    result = E.run_sync_exit(program)

    assert result == E.Failure(E.Die(defect))


def test_defects_are_not_retried():
    attempts: list[int] = []
    defect = RuntimeError("boom")
    program = (
        E.sync(lambda: attempts.append(1))
        .flat_map(lambda _: E.die(defect))
        .retry(E.Schedule.recurs(3))
    )

    result = E.run_sync_exit(program)

    assert result == E.Failure(E.Die(defect))
    assert attempts == [1]


def test_each_run_starts_the_schedule_fresh():
    flaky = Flaky(succeed_on=None)
    program = flaky.run().retry(E.Schedule.recurs(2))

    first = E.run_sync_exit(program)
    second = E.run_sync_exit(program)

    assert first == E.Failure(E.Fail(Boom(3)))
    assert second == E.Failure(E.Fail(Boom(6)))


def test_retrying_many_times_is_stack_safe():
    flaky = Flaky(succeed_on=None)
    program = flaky.run().retry(E.Schedule.recurs(10_000))

    result = E.run_sync_exit(program)

    assert result == E.Failure(E.Fail(Boom(10_001)))


def test_the_retried_effect_inherits_the_environment():
    program = E.require(str).retry(E.Schedule.recurs(1)).provide(str)("provided")

    result = E.run_sync(program)

    assert result == "provided"


@E.gen
def test_spaced_retries_once_per_delay(test_clock: E.Clock.Test) -> E.EffectGen[None]:
    flaky = Flaky(succeed_on=3)
    program = (
        flaky.run()
        .retry(E.Schedule.spaced(FIVE_SECONDS))
        .provide(E.Clock.Protocol)(test_clock)
    )
    fiber = yield from E.fork(program)

    yield from test_clock.adjust(FIVE_SECONDS)
    attempts_after_one_delay = flaky.attempts
    yield from test_clock.adjust(FIVE_SECONDS)
    result = yield from fiber.wait()

    assert attempts_after_one_delay == 2
    assert result == E.Succeeded("ok")
    assert flaky.attempts == 3


@E.gen
def test_spaced_waits_the_delay_before_the_next_attempt(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    flaky = Flaky(succeed_on=2)
    program = (
        flaky.run()
        .retry(E.Schedule.spaced(FIVE_SECONDS))
        .provide(E.Clock.Protocol)(test_clock)
    )
    fiber = yield from E.fork(program)

    yield from test_clock.adjust(FIVE_SECONDS - ONE_SECOND)
    parked = yield from fiber.poll()
    attempts_before = flaky.attempts
    yield from test_clock.adjust(ONE_SECOND)
    result = yield from fiber.wait()

    assert parked is None
    assert attempts_before == 1
    assert result == E.Succeeded("ok")
    assert flaky.attempts == 2


@E.gen
def test_exponential_grows_the_delay_between_attempts(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    flaky = Flaky(succeed_on=4)
    program = (
        flaky.run()
        .retry(E.Schedule.exponential(ONE_SECOND))
        .provide(E.Clock.Protocol)(test_clock)
    )
    fiber = yield from E.fork(program)

    attempts: list[int] = []
    for gap in (1, 2, 4):
        yield from test_clock.adjust(timedelta(seconds=gap))
        attempts.append(flaky.attempts)
    result = yield from fiber.wait()

    assert attempts == [2, 3, 4]
    assert result == E.Succeeded("ok")


@E.gen
def test_a_timeout_interrupts_a_sleeping_retry(
    test_clock: E.Clock.Test,
) -> E.EffectGen[None]:
    flaky = Flaky(succeed_on=None)
    program = (
        flaky.run()
        .retry(E.Schedule.spaced(FIVE_SECONDS))
        .timeout(ONE_SECOND)
        .provide(E.Clock.Protocol)(test_clock)
    )
    fiber = yield from E.fork(program)

    yield from test_clock.adjust(ONE_SECOND)
    result = yield from fiber.wait()

    assert result == E.Failure(E.Fail(E.TimeoutException(ONE_SECOND)))
    assert flaky.attempts == 1
