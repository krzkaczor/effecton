from datetime import timedelta
from itertools import islice

import effecton as E

ONE_SECOND = timedelta(seconds=1)


def test_recurs_yields_a_zero_delay_per_recurrence():
    schedule = E.Schedule.recurs(3)

    delays = list(schedule)

    assert delays == [timedelta(0)] * 3


def test_recurs_zero_never_recurs():
    schedule = E.Schedule.recurs(0)

    delays = list(schedule)

    assert delays == []


def test_spaced_repeats_the_delay():
    schedule = E.Schedule.spaced(ONE_SECOND)

    delays = list(islice(schedule, 3))

    assert delays == [ONE_SECOND] * 3


def test_exponential_doubles_by_default():
    schedule = E.Schedule.exponential(ONE_SECOND)

    delays = list(islice(schedule, 4))

    assert delays == [timedelta(seconds=s) for s in (1, 2, 4, 8)]


def test_exponential_honours_the_factor():
    schedule = E.Schedule.exponential(ONE_SECOND, factor=3)

    delays = list(islice(schedule, 3))

    assert delays == [timedelta(seconds=s) for s in (1, 3, 9)]


def test_iterating_a_schedule_twice_starts_over():
    schedule = E.Schedule.recurs(2)

    first = list(schedule)
    second = list(schedule)

    assert first == second == [timedelta(0)] * 2


def test_a_custom_schedule_yields_its_delays():
    schedule = E.Schedule(lambda: iter([ONE_SECOND, timedelta(seconds=5)]))

    delays = list(schedule)

    assert delays == [ONE_SECOND, timedelta(seconds=5)]
