---
title: Wrapping async code
description: Defer awaitables with coroutine and attempt_async, and run them under the async runners.
---

# Wrapping async code

`coroutine` defers an awaitable the way `sync` defers a thunk: the thunk builds a fresh awaitable on every run, because a coroutine object can be awaited only once. Exceptions become defects. `attempt_async` is the `attempt` counterpart that maps expected exceptions into the error channel. `run_main` and the `run_async` family can interpret either:

```python
from dataclasses import dataclass
from typing import final

import httpx

import effecton as E


@final
@dataclass(frozen=True)
class HttpStatusError(E.EffectonError):
    url: str
    status_code: int


url = "https://example.com"
# ---cut---
client = httpx.AsyncClient()

E.coroutine(lambda: client.get(url))  # Effect[httpx.Response] — nothing awaited yet


def get_text(url: str) -> E.Effect[str, HttpStatusError]:
    async def go() -> str:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    def to_error(e: Exception) -> HttpStatusError:
        if isinstance(e, httpx.HTTPStatusError):
            return HttpStatusError(url=url, status_code=e.response.status_code)
        raise e  # anything else stays a defect

    return E.attempt_async(go, to_error)


E.run_async(get_text("https://example.com"))  # text, or raises HttpStatusError

E.run_async_exit(
    get_text("https://example.com")
)  # Succeeded(text) or Failure(Fail(HttpStatusError(...)))
```

Inside `@E.gen` bodies, `yield from E.coroutine(...)` works like any other effect; the generator itself stays synchronous. If the task running `run_async_coroutine` is cancelled, the effect unwinds with an `Interrupt` cause, which `catch_all` and `catch` skip like a `Die`: finalizers and scope releases run, and the run settles as `Failure(Interrupt(exception))`, so an `asyncio.timeout` around `run_async_coroutine` doesn't leak resources and completes normally with that `Exit`. The cancellation is consumed by `run_async_coroutine`; a caller whose task should stop re-raises the carried exception. A finalizer that is mid-await when the cancellation arrives is shielded and runs to completion, and a cancellation raised from a synchronous thunk or callback, such as a cancelled future's `result()`, unwinds the same way.

More examples: [`test_run_async.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_async.py).
