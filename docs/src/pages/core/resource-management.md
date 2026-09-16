---
title: Resource management with on_exit and Scope
description: Attach finalizers with on_exit and release acquired resources in reverse order through Scope.
---

# Resource management with `on_exit` and Scope

`on_exit` attaches a finalizer that runs when the effect settles, on success and failure alike. A `Scope` collects finalizers from a whole sub-tree: `acquire_and_release` registers a release for an acquired resource, and `.scoped()` provides the `Scope` and runs the collected finalizers in reverse order when the wrapped effect settles. It composes with `provide` chains — `program.provide(Db)(db).scoped()` — and is a no-op on effects that never acquired a `Scope`, so it can uniformly terminate a chain.

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class Connection:
    def close(self) -> None: ...


@final
@dataclass(frozen=True)
class Pool:
    def connect(self) -> Connection:
        return Connection()


pool = Pool()


def run_queries(conn: Connection) -> E.Effect[int]:
    return E.success(1)


# ---cut---
E.success(21).on_exit(E.log_info("done"))  # finalizer runs on success and failure alike

conn = E.acquire_and_release(
    E.sync(lambda: pool.connect()),  # acquire
    lambda c: E.sync(c.close),  # release, guaranteed by the enclosing scope
)  # Effect[Connection, Never, Scope]

program = conn.flat_map(
    run_queries
).scoped()  # Scope discharged; close() runs when program settles
```

`on_exit` also takes a function that receives the `Exit` and returns the finalizer, so cleanup can depend on how the effect settled:

```python
import effecton as E

# ---cut---
E.success(21).on_exit(
    lambda exit: E.log_info("settled", exit)
)  # Succeeded(21), or Failure(cause) carrying Fail, Die or Interrupt
```

A finalizer that dies doesn't skip the remaining finalizers; its defect surfaces in the final `Exit`.

More examples: [`test_scope.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_scope.py).
