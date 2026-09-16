---
title: Fibers
description: Forking effects to run concurrently and settling on the returned fiber.
---

# Fibers

`E.fork(effect)` starts an effect concurrently and returns an `E.Fiber`. `fiber.join()` is the fiber's value, failing with the fiber's own cause; `fiber.wait()` is its `Exit` and never fails; `fiber.poll()` peeks without waiting; `fiber.interrupt()` cancels it, lets its finalizers run and returns the `Exit`; `E.yield_now()` lets other fibers take a turn. Fibers are asyncio tasks underneath, so `fork` is async only and a forked run starts with a fresh environment: provide what it needs.

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class FetchError(E.EffectonError):
    pass


def fetch_total() -> E.Effect[int, FetchError]:
    return E.success(1)


def do_other_work() -> E.Effect[int]:
    return E.success(2)


# ---cut---
@E.gen
def program() -> E.EffectGen[int, FetchError]:
    fiber = yield from E.fork(fetch_total())  # runs concurrently
    #  ^?
    other = yield from do_other_work()
    total = yield from fiber.join()  # Effect[int, FetchError]
    return total + other
```

More examples: [`test_fiber.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_fiber.py).
