---
title: Main programs
description: Use run_main at a process entry point to report failures and choose exit codes.
---

# Main programs

`E.run_main(effect)` runs sync and async effects, returning the successful value so a CLI can print its result:

```python
from dataclasses import dataclass
from typing import ClassVar, final

import effecton as E


@final
@dataclass(frozen=True)
class InvalidName(E.EffectonError):
    name: str
    exit_code: ClassVar[int] = 2

    def __str__(self) -> str:
        return f"Invalid name: {self.name!r}"


def greet(name: str) -> E.Effect[str, InvalidName]:
    if not name.strip():
        return E.fail(InvalidName(name))
    return E.success(f"Hello, {name}!")


if __name__ == "__main__":
    print(E.run_main(greet("world")))
```

Typed failures log their message at ERROR; exception defects start with `Defect occurred`, followed by Python's exception formatting, including any traceback and exception chain, and other defects render as `Unhandled defect: ...`. The report uses the default effecton logger and pretty formatting, independently of logging requirements provided inside the program. It then raises `SystemExit(1)`, or uses an integer `exit_code` attribute on the error or defect. Missing and non-integer attributes (including booleans), as well as codes outside `0..255`, fall back to `1`. A successful integer is returned as a value, never treated as an exit code.

Ctrl+C and cancellation exit quietly with `130`; SIGTERM exits with `143`. The first signal determines the code. Finalizers finish and the event loop closes before control returns or `SystemExit` is raised, and previous signal handlers are restored. Repeated signals continue cancellation without bypassing finalizers; there is no cleanup timeout. Cancellation is cooperative, so blocking synchronous work can delay shutdown. An explicit `SystemExit` inside the effect retains its code after finalization.

Call `run_main` from the main thread, outside a running event loop. Both examples use it: [`skills-cli`](https://github.com/krzkaczor/effecton/blob/main/packages/examples/skills-cli/src/skills_cli/cli.py) and [`changesets`](https://github.com/krzkaczor/effecton/blob/main/packages/changesets/src/changesets/status/cli.py).
