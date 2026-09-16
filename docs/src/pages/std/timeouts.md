---
title: Timeouts
description: Bounding an effect with a deadline that interrupts it and fails with a typed TimeoutException.
---

# Timeouts

`effect.timeout(duration)` composes `race_first` with Clock sleep followed by a typed `TimeoutException`. If the deadline wins, it interrupts the effect and awaits its finalizers. The effect's own outcome, or a defect in the clock, otherwise propagates unchanged. Timeouts are async only, with the same requirement inheritance and cleanup rules as racing.

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


def fetch_total() -> E.Effect[int, FetchError]:
    return E.success(1)


def load_user(user_id: int) -> E.Effect[User, FetchError]:
    return E.success(User(user_id))


# ---cut---
fetch_total().timeout(
    timedelta(seconds=5)
)  # Effect[int, FetchError | TimeoutException]


@E.timeout(timedelta(seconds=5))
@E.gen
def fetch_user(user_id: int) -> E.EffectGen[User, FetchError]:
    return (yield from load_user(user_id))


fetch_user(1).catch(E.TimeoutException)(lambda _: E.success(None))
# Effect[User | None, FetchError]
```

`E.timeout(duration)(effect)` is the curried form; decorating an effect-returning function wraps each result and preserves its call signature. Durations are `timedelta` values. Cancellation is cooperative: blocking synchronous work can delay a timeout, and cleanup can extend the total time beyond the deadline.

For deterministic tests, provide `E.Clock.Test` around the timeout, fork the program, then advance the clock and await the fiber. Both race branches start eagerly when the race runs, so the timer is registered before a subsequent clock adjustment.

More examples: [`test_timeout.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_timeout.py).
