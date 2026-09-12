import random
from collections.abc import Iterator
from datetime import timedelta
from itertools import islice

import effecton as E

ONE_SECOND = timedelta(seconds=1)
FIVE_SECONDS = timedelta(seconds=5)
LIVE = E.Random.Live()


def run_delays(
    schedule: E.Schedule,
    count: int | None = None,
    *,
    rng: E.Random.Protocol = LIVE,
) -> list[timedelta]:
    """Run the first count steps (all of them when None) under rng."""
    return [
        E.run_sync(step.provide(E.Random.Protocol)(rng))
        for step in islice(schedule, count)
    ]


def factors(seed: int, count: int, low: float = 0.8, high: float = 1.2) -> list[float]:
    """The factors a Random.Test with seed draws for jittered(min=low, max=high)."""
    stdlib = random.Random(seed)
    return [stdlib.uniform(low, high) for _ in range(count)]


def test_recurs_yields_a_zero_delay_per_recurrence():
    schedule = E.Schedule.recurs(3)

    delays = run_delays(schedule)

    assert delays == [timedelta(0)] * 3


def test_recurs_zero_never_recurs():
    schedule = E.Schedule.recurs(0)

    delays = run_delays(schedule)

    assert delays == []


def test_spaced_repeats_the_delay():
    schedule = E.Schedule.spaced(ONE_SECOND)

    delays = run_delays(schedule, 3)

    assert delays == [ONE_SECOND] * 3


def test_exponential_doubles_by_default():
    schedule = E.Schedule.exponential(ONE_SECOND)

    delays = run_delays(schedule, 4)

    assert delays == [timedelta(seconds=s) for s in (1, 2, 4, 8)]


def test_exponential_honours_the_factor():
    schedule = E.Schedule.exponential(ONE_SECOND, factor=3)

    delays = run_delays(schedule, 3)

    assert delays == [timedelta(seconds=s) for s in (1, 3, 9)]


def test_iterating_a_schedule_twice_starts_over():
    schedule = E.Schedule.recurs(2)

    first = run_delays(schedule)
    second = run_delays(schedule)

    assert first == second == [timedelta(0)] * 2


def test_from_delays_lifts_plain_delays_into_steps():
    schedule = E.Schedule.from_delays(lambda: iter([ONE_SECOND, FIVE_SECONDS]))

    delays = run_delays(schedule)

    assert delays == [ONE_SECOND, FIVE_SECONDS]


def test_a_custom_schedule_runs_each_step():
    calls: list[int] = []

    def steps() -> Iterator[E.Effect[timedelta]]:
        yield E.success(ONE_SECOND)
        yield E.sync(lambda: calls.append(1)).map(lambda _: FIVE_SECONDS)

    schedule = E.Schedule(steps)

    delays = run_delays(schedule)

    assert delays == [ONE_SECOND, FIVE_SECONDS]
    assert calls == [1]


def test_jittered_scales_each_delay_by_a_factor_from_random():
    schedule = E.Schedule.spaced(FIVE_SECONDS).jittered()

    delays = run_delays(schedule, 4, rng=E.Random.Test(seed=1))

    assert delays == [FIVE_SECONDS * f for f in factors(1, 4)]


def test_jittered_honours_min_and_max():
    schedule = E.Schedule.spaced(FIVE_SECONDS).jittered(min=0.5, max=1.5)

    delays = run_delays(schedule, 4, rng=E.Random.Test(seed=1))

    assert delays == [FIVE_SECONDS * f for f in factors(1, 4, 0.5, 1.5)]


def test_jittered_defaults_stay_within_the_effect_ts_bounds():
    schedule = E.Schedule.spaced(FIVE_SECONDS).jittered()

    delays = run_delays(schedule, 50)

    assert all(FIVE_SECONDS * 0.8 <= delay <= FIVE_SECONDS * 1.2 for delay in delays)


def test_jittered_keeps_a_zero_delay_at_zero():
    schedule = E.Schedule.recurs(3).jittered()

    delays = run_delays(schedule, rng=E.Random.Test(seed=3))

    assert delays == [timedelta(0)] * 3


def test_iterating_a_jittered_schedule_twice_starts_over():
    schedule = E.Schedule.spaced(FIVE_SECONDS).jittered()

    first = run_delays(schedule, 3, rng=E.Random.Test(seed=1))
    second = run_delays(schedule, 3, rng=E.Random.Test(seed=1))

    assert first == second


def test_jittered_composes_with_exponential():
    schedule = E.Schedule.exponential(ONE_SECOND).jittered()

    delays = run_delays(schedule, 3, rng=E.Random.Test(seed=1))

    assert delays == [
        ONE_SECOND * 2**i * f for i, f in enumerate(factors(1, 3), start=0)
    ]
