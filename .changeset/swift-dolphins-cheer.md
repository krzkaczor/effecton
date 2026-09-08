---
effecton: patch
---

Add E.fork and E.Fiber (join, wait, poll, interrupt) backed by asyncio tasks, make the Test clock's adjust and set_time return effects, and ship a pytest plugin that runs tests written as effects with a test_clock fixture.
