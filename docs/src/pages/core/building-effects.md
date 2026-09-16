---
title: Building effects
description: Construct effects with success, sync, fail and suspend without running anything.
---

# Building effects

```python
from dataclasses import dataclass
from typing import final

import effecton as E

# ---cut---
E.success(21).map(lambda x: x * 2)  # Effect[int]

E.sync(lambda: print("hi"))  # Effect[None] — defers a side effect until the effect runs


# Custom errors extend EffectonError and are final: one leaf class per cause
@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


E.fail(OopsError(msg="oops"))  # Effect[Never, OopsError]
```

`suspend` defers building an effect. The thunk form wraps one effect; as a decorator on a function with parameters, each call captures its arguments and defers the body until the effect runs:

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


# ---cut---
E.suspend(lambda: E.fail(OopsError(msg="later")))  # Effect[Never, OopsError]


@E.suspend
def find_user(user_id: int) -> E.Effect[str, OopsError]:
    print("runs only when the effect is interpreted")
    return E.success(f"user-{user_id}")


find_user(1)  # Effect[str, OopsError] — nothing printed yet
```

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_sync.py), [`test_suspend.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_suspend.py).
