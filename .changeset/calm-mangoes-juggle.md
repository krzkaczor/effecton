---
effecton: patch
---

Ship a pytest plugin, registered through the pytest11 entry point so it loads wherever effecton is installed. A test that returns an Effect (typically an @E.gen function) runs under the async runner and a failure is reported as its cause. The test_clock fixture provides an E.Clock.Test to the test's effect.
