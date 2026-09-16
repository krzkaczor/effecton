---
title: Process
description: What the running process knows about its environment, as an explicit requirement with a pinnable test implementation.
---

# Process

`E.Process` is what the running process knows about its environment: `cwd()` and `home()` today, with environment variables to follow. Both return an `E.Path`. It is an explicit requirement like the FileSystem, so a CLI reads its starting directory through it and a test pins that directory with `E.Process.Test(current_directory=..., home_directory=...)` instead of depending on where pytest happens to run.

```python
from collections.abc import Callable
from typing import Never

import effecton as E


def status(cwd: E.Path) -> E.Effect[None, Never, E.FileSystem.Protocol]:
    return E.success(None)


# ---cut---
def from_cwd[A, Err: E.EffectonError, R](
    program: Callable[[E.Path], E.Effect[A, Err, R]],
) -> E.Effect[A, Err, R | E.Process.Protocol]:
    return E.require(E.Process.Protocol).flat_map(lambda p: p.cwd()).flat_map(program)


E.run_main(
    from_cwd(status)
    .provide(E.Process.Protocol)(E.Process.Live())
    .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
)
```
