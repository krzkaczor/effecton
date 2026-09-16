---
title: Requirements and providing them
description: Read dependencies with require and satisfy them one at a time with provide.
---

# Requirements and providing them

`require(T)` reads a dependency and records it in the `R` channel; composing effects unions their requirements, exactly like errors. the runners only accept `Effect[A, E]`, so running an effect with unmet requirements is a type error, not a runtime surprise.

```python
from dataclasses import dataclass

import effecton as E


# ---cut---
@dataclass(frozen=True)
class Db:
    url: str


needs_db = E.require(Db).map(lambda db: db.url)  # Effect[str, Never, Db]

program = needs_db.provide(Db)(Db("postgres://x"))  # Effect[str] — runnable
#  ^?

E.run_sync(program)  # "postgres://x"
```

`provide(T)(impl)` subtracts the provided type from `R`, so requirements can be provided one at a time, anywhere in the program — a partially provided effect is an ordinary value carrying the remainder in `R`, and the runners accept it only once `R` reaches `Never`.

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_sync.py).
