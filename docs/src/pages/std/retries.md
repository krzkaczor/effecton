---
title: Retries
description: Re-running a failed effect on a schedule of delays, bounded by a count or a predicate on the error.
---

# Retries

`effect.retry(schedule=None, times=None, until=...)` re-runs an effect on a typed failure while the schedule recurs, sleeping through the Clock for each delay. `times` caps the retries at that many more attempts; `retry(times=3)` alone retries up to three times without waiting, and `retry()` with neither recurs forever. Defects and interrupts are never retried. When the schedule is exhausted, `times` is used up, or `until` holds for the error, the retry fails with that last error, so the error channel is unchanged.

```python
from dataclasses import dataclass
from datetime import timedelta
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class User:
    id: int


@final
@dataclass(frozen=True)
class FetchError(E.EffectonError):
    pass


@final
@dataclass(frozen=True)
class NotFound(E.EffectonError):
    pass


def fetch_total() -> E.Effect[int, FetchError]:
    return E.success(1)


def fetch_user(user_id: int) -> E.Effect[User, FetchError | NotFound]:
    return E.success(User(user_id))


# ---cut---
fetch_total().retry(times=3)  # Effect[int, FetchError]

fetch_total().retry(E.Schedule.exponential(timedelta(seconds=1)), times=5)

fetch_user(1).retry(
    E.Schedule.exponential(timedelta(seconds=1)),
    until=lambda e: isinstance(e, NotFound),
)  # Effect[User, FetchError | NotFound]
```

`E.Schedule.recurs(times)` recurs up to `times` more times without waiting, `E.Schedule.spaced(delay)` waits `delay` before every attempt, and `E.Schedule.exponential(base, factor=2.0)` waits `base`, then `base * factor`, and so on. The last two are unbounded; bound them with `times=` or `until`. `schedule.jittered(min=0.8, max=1.2)` scales every delay by a factor drawn uniformly from `[min, max]` through the `E.Random` service, so `E.Random.Test(seed)` makes the jitter reproducible. Every run of the retried effect starts its schedule over.

```python
from dataclasses import dataclass
from datetime import timedelta
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class User:
    id: int


@final
@dataclass(frozen=True)
class FetchError(E.EffectonError):
    pass


@final
@dataclass(frozen=True)
class NotFound(E.EffectonError):
    pass


def fetch_total() -> E.Effect[int, FetchError]:
    return E.success(1)


def fetch_user(user_id: int) -> E.Effect[User, FetchError | NotFound]:
    return E.success(User(user_id))


# ---cut---
fetch_user(1).retry(E.Schedule.exponential(timedelta(seconds=1)).jittered())
```

A schedule is a factory of steps, and each step is an effect yielding the next delay, which is what lets `jittered` consult `Random`. Build a custom one with `E.Schedule.from_delays(...)` from any callable that yields a fresh iterator of `timedelta` values, or with `E.Schedule(steps=...)` when the delays are computed by effects.

There is no decorator form because `until` is typed by the effect's error channel, which a decorator cannot see. `recurs` needs no waiting and works under `run_sync`; for deterministic tests of delayed schedules, provide `E.Clock.Test`, fork the program, then advance the clock once per gap and await the fiber. A forked run starts with a fresh environment, so provide the test clock and a seeded `E.Random.Test` inside the forked program.

More examples: [`test_retry.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_retry.py).
