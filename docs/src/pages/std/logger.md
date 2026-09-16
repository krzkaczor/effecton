---
title: Logger
description: The built-in pretty logger, annotating logs with context, and capturing logs in tests.
---

# Logger

Effecton comes with pretty logger out of the box.

```python
import effecton as E


def handle_request() -> E.Effect[None]:
    return E.log_info("handling")


# ---cut---
E.run_sync(E.log_info("user created", 42))  # pretty-printed to stderr, no setup needed

program = E.annotate_logs(
    #  ^?
    handle_request(),
    request_id="r-1",
)  # every log inside carries request_id=r-1

captured: list[E.LogData] = []
E.run_sync(
    E.provide_implicit(
        program, E.CurrentLoggers((E.EffectonLogger(log=captured.append),))
    )
)
```

More examples: [`test_logger.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_logger.py), [`test_pretty_logger.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_pretty_logger.py).
