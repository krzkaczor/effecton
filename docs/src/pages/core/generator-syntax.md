---
title: Generator syntax
description: Write sequential effect code with @E.gen and yield from while staying fully typed.
---

# Generator syntax

`@E.gen` turns a generator function into a factory of effects: the interpreter runs each yielded effect and sends its success value back into the generator, and the generator's return value becomes the effect's success value. Write `x = yield from effect`, not `x = yield effect` — `Effect.__iter__` is typed so `yield from` gives `x` the effect's success type, while a bare `yield` types as `Any`.

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


# ---cut---
@E.gen
def total(n: int) -> E.EffectGen[int, OopsError]:
    a = yield from E.success(20)  # a: int — yield from types the sent-back value

    if n < 0:
        yield from E.fail(
            OopsError(msg="negative")
        )  # OopsError joins the error channel
    return a + n


E.run_sync(total(22))  # 42
```

A failing yielded effect abandons the generator, so `try/except` around a `yield` never observes effect failures — use `catch` or `catch_all` on the resulting effect instead.

More examples: [`test_gen.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_gen.py).
