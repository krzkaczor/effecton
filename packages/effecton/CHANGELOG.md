# effecton

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
