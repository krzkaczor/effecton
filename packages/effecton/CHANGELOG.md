# effecton

## 0.3.0

### Minor Changes

- Launch the docs site: a landing page, an introduction, and a generated API Reference, with every Python snippet type-checked by ty at build time. ([#26](https://github.com/krzkaczor/effecton/pull/26))

### Patch Changes

- Add the E.HttpClient service: SyncLive and AsyncLive on httpx2, Test with canned responses or a handler, Request/Response values and filter_status_ok; HTTP client libraries are banned outside the service ([#24](https://github.com/krzkaczor/effecton/pull/24))
- sleep, timeout and Schedule.spaced/exponential accept a duration as timedelta's keyword parts (seconds=5, minutes=1, ...) in place of a timedelta. ([#26](https://github.com/krzkaczor/effecton/pull/26))
- Add the `E.Tracer` service: `E.with_span(effect, name, kind=..., **attributes)` opens a span around an effect (also as `effect.with_span`), `E.annotate_current_span` adds attributes, `E.current_span` reads the open span, `E.Tracer.Live` is the in-memory default, `E.Tracer.Test` records its spans, and the `test_tracer` pytest fixture provides one ([#25](https://github.com/krzkaczor/effecton/pull/25))
- Add `effect.retry(schedule, until=...)` with `E.Schedule.recurs`, `E.Schedule.spaced`, and `E.Schedule.exponential` ([#19](https://github.com/krzkaczor/effecton/pull/19))
- Effect.retry takes an optional schedule and a `times` keyword, as in Effect-TS: `retry(times=3)` retries up to three times without waiting, `retry(schedule, times=5)` caps the schedule at five more recurrences, and `retry()` with neither recurs forever. ([#26](https://github.com/krzkaczor/effecton/pull/26))
- Add `schedule.jittered(min=0.8, max=1.2)`, which scales every delay by a factor drawn through `E.random()`; schedule steps are now effects, so build a plain custom schedule with `E.Schedule.from_delays(...)` and an effectful one with `E.Schedule(steps=...)` ([#22](https://github.com/krzkaczor/effecton/pull/22))
- Add the `E.FileSystem` service (`SyncLive`, `AsyncLive` on aiofiles, in-memory `Test`) the immutable `E.Path`, and the `E.Process` service (`cwd`, `home`); stdlib path and file APIs are banned outside the service ([#23](https://github.com/krzkaczor/effecton/pull/23))
- `on_exit` also accepts a function receiving the effect's `Exit` and returning the finalizer, so cleanup can depend on how the effect settled ([#25](https://github.com/krzkaczor/effecton/pull/25))
- Add the `E.Random` implicit service: `E.random()` resolves it, its methods keep the `random` module names (`random`, `uniform`, `randint`, `choice`, `shuffle`), `E.Random.Live` is the default, `E.Random.Test(seed)` is deterministic, and the `test_random` pytest fixture provides one seeded with 0 ([#22](https://github.com/krzkaczor/effecton/pull/22))

## 0.2.1

### Patch Changes

- Ship a pytest plugin, registered through the pytest11 entry point so it loads wherever effecton is installed. A test that returns an Effect (typically an @E.gen function) runs under the async runner and a failure is reported as its cause. The test_clock fixture provides an E.Clock.Test to the test's effect. ([#16](https://github.com/krzkaczor/effecton/pull/16))
- Add E.now() and E.sleep() backed by the implicit E.Clock service, with SyncLive, AsyncLive and Test clocks; each runner installs the matching live clock. ([#16](https://github.com/krzkaczor/effecton/pull/16))
- Add `E.run_main` to execute sync and async programs with failure logging, defect tracebacks, custom exit codes, and graceful signal handling. ([#14](https://github.com/krzkaczor/effecton/pull/14))
- Add E.fork, E.Fiber (join, wait, poll, interrupt) and E.yield_now backed by asyncio tasks, and make the Test clock's adjust and set_time return effects. ([#16](https://github.com/krzkaczor/effecton/pull/16))
- Add E.race_first(left, right) and E.timeout(duration) ([#18](https://github.com/krzkaczor/effecton/pull/18))

## 0.2.0

### Minor Changes

- Add `run_async`, `coroutine` and `attempt_async` for awaitable-backed effects ([#12](https://github.com/krzkaczor/effecton/pull/12))
- Split the runners: `run_sync` and `run_async` now return the value and raise on failure (the error, the defect, or `UnhandledDefect` for a non-exception defect); `run_sync_exit`, `run_async_exit` and the coroutine `run_async_coroutine` return the `Exit` ([#13](https://github.com/krzkaczor/effecton/pull/13))

### Patch Changes

- Add `Effect.catch`: handle one error type and subtract it from the error channel. ([#10](https://github.com/krzkaczor/effecton/pull/10))
- Add `Interrupt` as a third `Cause` state, produced when a cancellation unwinds `run_async` ([#12](https://github.com/krzkaczor/effecton/pull/12))

## 0.1.1

### Patch Changes

- Migrate from mypy to ty. Simplify api where possible. ([#1](https://github.com/krzkaczor/effecton/pull/1))
