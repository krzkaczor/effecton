---
effecton: patch
---

Effect.retry takes an optional schedule and a `times` keyword, as in Effect-TS: `retry(times=3)` retries up to three times without waiting, `retry(schedule, times=5)` caps the schedule at five more recurrences, and `retry()` with neither recurs forever.
