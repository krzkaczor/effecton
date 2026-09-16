---
title: Clock
description: Reading the time and sleeping through the implicit Clock service, and moving a test clock by hand.
---

# Clock

`E.now()` reads the current time and `E.sleep(duration)` pauses, both through the implicit `E.Clock` service, so neither enters `R`. `now()` returns a timezone-aware UTC `datetime` and is what the logger stamps `LogData.date` with. Sleeping depends on the runner, so the `Clock` protocol has no `default()`; instead there are two live clocks and each runner injects the matching one: `run_sync` installs `E.Clock.SyncLive`, whose sleep blocks the thread, and the `run_async` family (including `run_main`) installs `E.Clock.AsyncLive`, whose sleep awaits `asyncio.sleep`, keeps the loop turning and is interrupted by a cancellation like any coroutine effect.

```python
from datetime import timedelta

import effecton as E

# ---cut---
E.run_sync(E.now())  # datetime.now(UTC), no setup needed
E.run_sync(E.sleep(timedelta(seconds=1)))  # blocks for a second
E.run_async(E.sleep(timedelta(seconds=1)))  # awaits asyncio.sleep(1)
```

In tests, use `E.Clock.Test` and move it by hand with `adjust(delta)` or `set_time(time)`. Both return effects and are async only, like the clock's `sleep`, which parks until a move reaches its wake time (a sleep of zero returns at once). effecton ships a pytest plugin, loaded automatically wherever the package is installed, that runs a test returning an effect (typically a `@E.gen` function) under the async runner and reports a failure as its cause. A test that requests the `test_clock` fixture gets that clock provided to its effect, so `E.now()`, `E.sleep()` and the movers all see it:

```python
from datetime import UTC, datetime, timedelta

import effecton as E


# ---cut---
@E.gen
def test_reads_move_with_the_clock(test_clock: E.Clock.Test) -> E.EffectGen[None]:
    yield from test_clock.set_time(datetime(2024, 1, 1, tzinfo=UTC))

    first = yield from E.now()
    #  ^?
    yield from test_clock.adjust(timedelta(minutes=5))
    second = yield from E.now()

    assert second == first + timedelta(minutes=5)
```

A sleeping program has to run concurrently with the moves: `E.fork` it and settle on the returned fiber. Each move yields to the loop before and after, so a program forked just before reaches its sleep, and a woken program progresses before the test continues.

Provide clocks with `.provide(E.Clock.Protocol)(...)`: `provide_implicit` is keyed by `type(value)`, so it would register a `Test` clock under `Test` rather than `Protocol`. This repo's ruff config bans direct time reads and sleeps (`datetime.now`, `time.time`, `time.monotonic`, `time.sleep`, `asyncio.sleep`, ...) outside the clock module, so all code goes through `E.now()` and `E.sleep()`.

More examples: [`test_clock.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_clock.py).
