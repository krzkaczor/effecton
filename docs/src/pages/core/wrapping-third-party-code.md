---
title: Wrapping third party code
description: Turn exception-throwing code into typed effects with attempt, keeping unexpected exceptions as defects.
---

# Wrapping third party code

`attempt` runs an exception-throwing thunk lazily and maps expected exceptions into the typed error channel. Re-raise unexpected exceptions from the mapper so they stay defects:

```python
import json
from dataclasses import dataclass
from typing import Any, final

import effecton as E


# ---cut---
@final
@dataclass(frozen=True)
class InvalidJson(E.EffectonError):
    text: str


def parse_json(text: str) -> E.Effect[Any, InvalidJson]:
    def to_error(e: Exception) -> InvalidJson:
        if isinstance(e, json.JSONDecodeError):
            return InvalidJson(text)
        raise e  # anything else stays a defect

    return E.attempt(lambda: json.loads(text), to_error)
```

More examples: [`test_attempt.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_attempt.py).
