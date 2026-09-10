# effecton

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
