---
title: Random
description: Drawing random values through the implicit Random service, and seeding a reproducible generator in tests.
---

# Random

`E.random()` resolves the implicit `E.Random` service, so it never enters `R`. Its methods keep the names of the `random` standard library and each returns an effect: `random()`, `uniform(a, b)`, `randint(a, b)`, `choice(seq)` and `shuffle(seq)`, where `shuffle` returns a new list and leaves its input untouched. The default is `E.Random.Live`, which draws from the process-global generator behind the `random` module.

```python
import effecton as E


# ---cut---
@E.gen
def roll() -> E.EffectGen[int]:
    rng = yield from E.random()

    return (yield from rng.randint(1, 6))


E.run_sync(roll())  # 1..6, no setup needed
```

In tests, provide `E.Random.Test(seed)`: every draw is a function of the seed, and one instance advances as a single sequence, so the same seed always reproduces the same run. A test that requests the `test_random` fixture gets a `Test` seeded with 0 provided to its effect:

```python
import effecton as E


@E.gen
def roll() -> E.EffectGen[int]:
    rng = yield from E.random()

    return (yield from rng.randint(1, 6))


# ---cut---
@E.gen
def test_rolls_are_reproducible(test_random: E.Random.Test) -> E.EffectGen[None]:
    first = yield from roll()
    #  ^?
    second = yield from roll()

    assert (first, second) == (4, 4)
```

Provide generators with `.provide(E.Random.Protocol)(...)`, as with the Clock. This repo's ruff config bans the `random` module's drawing functions (`random.random`, `random.randint`, `random.choice`, ...) outside the service module, so all code goes through `E.random()`; building a `random.Random(seed)` to compute expected values in a test is still allowed.

More examples: [`test_random.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_random.py).
