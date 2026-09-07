---
effecton: minor
---

Split the runners: `run_sync` and `run_async` now return the value and raise on failure (the error, the defect, or `UnhandledDefect` for a non-exception defect); `run_sync_exit`, `run_async_exit` and the coroutine `run_async_coroutine` return the `Exit`
