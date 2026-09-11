---
effecton: patch
---

Add `schedule.jittered(min=0.8, max=1.2)`, which scales every delay by a factor drawn through `E.random()`; schedule steps are now effects, so build a plain custom schedule with `E.Schedule.from_delays(...)` and an effectful one with `E.Schedule(steps=...)`
