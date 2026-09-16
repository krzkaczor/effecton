---
title: Running effects
description: The sync and async runners, the throwing and Exit-returning forms, and run_async_coroutine.
---

# Running effects

Effects are inert values; a runner interprets one. The sync and async runners come in a throwing form that returns the value and an `_exit` form that returns an `Exit`. Use `run_main` at a process entry point to report failures and choose exit codes:

| Runner | Runs | Returns |
|---|---|---|
| `run_sync(effect)` | synchronously | the value, raising on failure |
| `run_sync_exit(effect)` | synchronously | `Exit[A, E]` |
| `run_async(effect)` | on a fresh asyncio loop (`asyncio.run` inside) | the value, raising on failure |
| `run_async_exit(effect)` | on a fresh asyncio loop (`asyncio.run` inside) | `Exit[A, E]` |
| `run_main(effect)` | on a fresh asyncio loop | the value, logging and exiting on failure |
| `await run_async_coroutine(effect)` | inside a loop you already own | `Exit[A, E]` |

`run_sync` and `run_async` raise a typed failure as the error itself (every `EffectonError` is an `Exception`), re-raise an exception defect as it is, wrap any other defect in `UnhandledDefect`, and re-raise the exception carried by an interruption:

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class HttpStatusError(E.EffectonError):
    url: str
    status_code: int


effect: E.Effect[str, HttpStatusError] = E.success("ok")
# ---cut---
try:
    value = E.run_sync(effect)  # A
except HttpStatusError as e:  # a typed failure
    ...
```

The `_exit` forms never raise; they return an `Exit` to match on:

```python
import effecton as E

effect: E.Effect[str, E.TimeoutException] = E.success("ok")
# ---cut---
match E.run_sync_exit(effect):  # Exit[A, E] = Succeeded[A] | Failure[E]
    case E.Succeeded(value):
        ...
    case E.Failure(cause):
        ...  # cause is Fail(error) for typed failures, Die(defect) for unexpected exceptions, Interrupt(exception) for cancellations
```

`run_async` and `run_async_exit` interpret the same effect under asyncio, awaiting every `coroutine` effect they reach. They own the event loop through `asyncio.run`, so they cannot be called from a running loop; `run_async_coroutine` is the coroutine underneath, for a caller that already has one:

```python
import effecton as E

effect: E.Effect[str, E.TimeoutException] = E.success("ok")


# ---cut---
async def main() -> None:
    exit = await E.run_async_coroutine(
        effect
    )  # Exit[A, E], awaiting coroutine effects along the way
    print(exit)
```

Running an effect that contains a `coroutine` effect synchronously doesn't await it: `run_sync_exit` settles as `Failure(Die(AsyncEffectInSyncRun()))`, `run_sync` raises `AsyncEffectInSyncRun`, and finalizers still run in both cases.

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_sync.py), [`test_run_async.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_async.py).
