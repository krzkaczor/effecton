"""Type-level pins for retry and Schedule. Nothing here runs: ty checks the
function bodies and pytest never calls them."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, Never, assert_type, final

import effecton as E

ONE_SECOND = timedelta(seconds=1)


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


@dataclass(frozen=True)
class Db:
    url: str


def parse(s: str) -> E.Effect[int, ParseError]:
    try:
        return E.success(int(s))
    except ValueError:
        return E.fail(ParseError(s))


def is_empty(error: ParseError) -> bool:
    return error.value == ""


def plain_delays() -> Iterator[timedelta]:
    yield ONE_SECOND


def effect_steps() -> Iterator[E.Effect[timedelta]]:
    yield E.success(ONE_SECOND)


def steps_needing_db() -> Iterator[E.Effect[timedelta, Never, Db]]:
    yield E.require(Db).map(lambda _: ONE_SECOND)


def failing_steps() -> Iterator[E.Effect[timedelta, ParseError]]:
    yield parse("x").map(lambda _: ONE_SECOND)


def _retry_keeps_a_e_and_r() -> None:
    recurs = E.Schedule.recurs(3)

    assert_type(parse("1").retry(recurs), E.Effect[int, ParseError])
    assert_type(parse("1").retry(recurs, until=is_empty), E.Effect[int, ParseError])
    assert_type(E.require(Db).retry(recurs), E.Effect[Db, Never, Db])
    assert_type(E.success(1).retry(recurs), E.Effect[Literal[1]])

    # The predicate sees the error channel.
    assert_type(
        parse("1").retry(recurs, until=lambda e: bool(assert_type(e, ParseError))),
        E.Effect[int, ParseError],
    )


def _schedules() -> None:
    assert_type(E.Schedule.recurs(3), E.Schedule)
    assert_type(E.Schedule.spaced(ONE_SECOND), E.Schedule)
    assert_type(E.Schedule.exponential(ONE_SECOND, factor=3), E.Schedule)
    assert_type(E.Schedule(effect_steps), E.Schedule)
    assert_type(E.Schedule(lambda: iter([E.success(ONE_SECOND)])), E.Schedule)
    assert_type(E.Schedule.from_delays(plain_delays), E.Schedule)
    assert_type(E.Schedule.from_delays(lambda: iter([ONE_SECOND])), E.Schedule)
    assert_type(E.Schedule.spaced(ONE_SECOND).jittered(), E.Schedule)
    assert_type(E.Schedule.recurs(3).jittered(min=0.5, max=1.5), E.Schedule)

    # Steps are effects yielding delays.
    assert_type(next(iter(E.Schedule.recurs(1))), E.Effect[timedelta])


def _retry_negative() -> None:
    recurs = E.Schedule.recurs(3)

    # The schedule is a Schedule, not a count.
    E.success(1).retry(3)  # ty: ignore[invalid-argument-type]

    # Delays are timedelta values, counts are ints.
    E.Schedule.spaced(1)  # ty: ignore[invalid-argument-type]
    E.Schedule.recurs(ONE_SECOND)  # ty: ignore[invalid-argument-type]

    # The predicate must accept the effect's error type.
    def takes_int(error: int) -> bool:
        return error == 0

    parse("1").retry(recurs, until=takes_int)  # ty: ignore[invalid-argument-type]

    # The predicate is keyword-only.
    parse("1").retry(recurs, is_empty)  # ty: ignore[too-many-positional-arguments]

    # Steps are effects; plain delays go through from_delays, and only there.
    E.Schedule(plain_delays)  # ty: ignore[invalid-argument-type]
    E.Schedule.from_delays(effect_steps)  # ty: ignore[invalid-argument-type]

    # A step cannot require anything or fail: R and E must be Never.
    E.Schedule(steps_needing_db)  # ty: ignore[invalid-argument-type]
    E.Schedule(failing_steps)  # ty: ignore[invalid-argument-type]

    # The jitter bounds are keyword-only floats.
    E.Schedule.recurs(3).jittered(0.5, 1.5)  # ty: ignore[too-many-positional-arguments]
    E.Schedule.recurs(3).jittered(min="0.5")  # ty: ignore[invalid-argument-type]

    # Schedules are leaves: Schedule cannot be subclassed.
    class Custom(E.Schedule):  # ty: ignore[subclass-of-final-class]
        pass
