---
title: Error handling
description: Recover from typed failures with catch_all and catch, which subtracts one error class from the union.
---

# Error handling

Use `catch_all` to handle errors:

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


# ---cut---
p = E.fail(OopsError(msg="oops")).catch_all(
    lambda e: E.success(f"recovered from {e.msg}")
)  # Effect[str] — the error channel is now Never

E.run_sync(p)  # "recovered from oops"
```

Use `catch` to handle one error type and leave the rest in the error channel. The handler receives the narrowed error, and defects (`Die`) pass through untouched:

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class FatalError(E.EffectonError):
    pass


@final
@dataclass(frozen=True)
class RecoverableError(E.EffectonError):
    pass


# ---cut---
roll = E.random().flat_map(lambda rng: rng.randint(1, 4))

p = roll.flat_map(
    lambda r: E.fail(FatalError()) if r == 2 else E.fail(RecoverableError())
)  # Effect[Never, FatalError | RecoverableError]

p2 = p.catch(RecoverableError)(lambda _: E.success(42))  # Effect[int, FatalError]
# ^?
```

`catch` is curried like `provide`: the error class is bound first so the type checker can subtract it from the union. Catching a class the effect cannot fail with is a well-typed no-op.

Error classes are leaves: mark every error `@final` and never subclass one. `catch` matches by class, and `@final` keeps its runtime `isinstance` check and the static subtraction in agreement, because the type checker cannot distinguish a subclass from its base when subtracting from a union.

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_sync.py).
