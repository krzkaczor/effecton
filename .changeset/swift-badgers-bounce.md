---
effecton: patch
---

Add the `E.Random` implicit service: `E.random()` resolves it, its methods keep the `random` module names (`random`, `uniform`, `randint`, `choice`, `shuffle`), `E.Random.Live` is the default, `E.Random.Test(seed)` is deterministic, and the `test_random` pytest fixture provides one seeded with 0
