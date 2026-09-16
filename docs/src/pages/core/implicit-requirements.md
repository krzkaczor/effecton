---
title: Implicit requirements
description: Dependencies with a default that stay overridable and never enter the R channel.
---

# Implicit requirements

Some dependencies, such as a logger or a log level, should work out of the box yet stay overridable. An implicit requirement is a class that extends the `ImplicitRequirement` protocol with a `default()` classmethod. Reading one with `require_implicit(X)` types as `Effect[X]`: it never enters `R`, so a program that only uses implicit requirements runs bare. If the lookup misses, the interpreter falls back to `X.default()`, computed once per process and memoized, so defaults must be immutable values.

```python
from dataclasses import dataclass
from typing import final

import effecton as E


# ---cut---
@final
@dataclass(frozen=True)
class Greeting(E.ImplicitRequirement):
    text: str

    @classmethod
    def default(cls) -> Greeting:
        return Greeting("hello")


E.run_sync(E.require_implicit(Greeting))  # Greeting("hello") — nothing provided

# override for a sub-effect only; the env is restored when it settles
E.run_sync(E.provide_implicit(E.require_implicit(Greeting), Greeting("hi")))
```

`provide_implicit(effect, value)` is keyed by `type(value)`, so mark implicit requirement classes `@final`. A `typing.Protocol` that extends `ImplicitRequirement` with a concrete `default()` is an implicit requirement too; its implementations are provided with `effect.provide(Protocol)(impl)` (the std `Clock` service works this way). Overrides also compose in a `provide` chain: `effect.provide(Greeting)(Greeting("hi"))`. `require_implicit` is a separate accessor rather than an overload on `require` because the overload pair silently drops requirements from `R` in some inference positions (pinned in `test_types_implicit_requirement.py`). One footgun: the runtime check only tests that a `default` attribute exists, so a plain requirement class that defines one gets the default fallback instead of a `MissingRequirement` defect.

More examples: [`test_implicit_requirement.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_implicit_requirement.py).
