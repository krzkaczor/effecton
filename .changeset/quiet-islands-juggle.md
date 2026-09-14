---
effecton: patch
---

`on_exit` also accepts a function receiving the effect's `Exit` and returning the finalizer, so cleanup can depend on how the effect settled
