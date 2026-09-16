---
title: Tracer
description: Opening named, nested spans around effects with the implicit Tracer service, and inspecting them in tests.
---

# Tracer

`E.with_span(effect, name)` opens a span around an effect: one named, timed unit that nests. A span opened inside another becomes its child and shares its trace id, and it ends with the effect's `Exit` when the effect settles, on success, typed failure, defect and interruption alike. Spans go through the implicit `E.Tracer` service, so nothing enters `R`; timestamps come from `E.now()` and ids are drawn through `E.random()`. `with_span` takes the effect first, like `annotate_logs`, and is also a method:

```python
from dataclasses import dataclass
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


# ---cut---
@E.gen
def fetch_user(user_id: int) -> E.EffectGen[User, FetchError]:
    yield from E.annotate_current_span(user_id=user_id)  # attributes on the open span
    return User(user_id)


traced = E.with_span(fetch_user(1), "fetch_user")
#  ^?
program = traced.with_span("handle_request", kind="server", route="/users/1")
```

`E.annotate_current_span(**attributes)` adds attributes to the innermost open span and is a no-op outside one; `E.current_span()` returns that span and fails with `E.Tracer.NoCurrentSpan` outside one. The default tracer, `E.Tracer.Live`, opens in-memory spans that nothing collects, so tracing costs nothing until a tracer that exports them is provided: an OpenTelemetry exporter would be another implementation of `E.Tracer.Protocol`, and the hex ids already match the W3C `traceparent` header. A forked fiber starts with a fresh environment, so it opens root spans unless the parent is passed along with `E.provide_implicit(forked, E.Tracer.ParentSpan(span))`, `span` being the result of `E.current_span()`; `race_first` and `timeout` inherit the current span.

In tests, provide `E.Tracer.Test`, which records every span it opens in `spans`, in opening order. Each span carries `name`, `kind`, `attributes`, `parent`, `trace_id`, `span_id` and a `status` that is `Started(start_time)` while open and `Ended(start_time, end_time, exit)` afterwards. A test that requests the `test_tracer` fixture gets one provided to its effect:

```python
from dataclasses import dataclass
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


@E.gen
def fetch_user(user_id: int) -> E.EffectGen[User, FetchError]:
    yield from E.annotate_current_span(user_id=user_id)  # attributes on the open span
    return User(user_id)


# ---cut---
@E.gen
def test_opens_a_span_per_request(
    test_tracer: E.Tracer.Test,
) -> E.EffectGen[None, FetchError]:
    yield from fetch_user(1).with_span("handle_request", kind="server")

    request, user = test_tracer.spans
    assert (request.name, user.parent) == ("handle_request", request)
    assert isinstance(user.status, E.Tracer.Ended)
```

More examples: [`test_tracer.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_tracer.py).
