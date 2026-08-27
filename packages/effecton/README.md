# Effecton

[![Discord](https://img.shields.io/badge/Discord-join%20chat-5865F2?logo=discord&logoColor=white)](https://discord.gg/fNhY7AxMyh)

A typed effect system for Python, inspired by [Effect-TS](https://effect.website/). Early stage and experimental.

An `Effect[A, E, R]` is a description of a computation that succeeds with `A`, fails with a typed error `E` and requires `R` dependencies.

```python
from dataclasses import dataclass

import effecton as E


# Custom errors need to extend EffectonError
@dataclass(frozen=True)
class SecretInvalidError(E.EffectonError):
    actual: str


# signature means that it succeeds with str, fails with SecretInvalidError or HttpError and it requires HttpClient
@E.gen
def check_secret() -> E.EffectGen[
    str, SecretInvalidError | HttpError, HttpClient.Protocol
]:
    http = yield from E.require(HttpClient.Protocol)  # requires HttpClient.Protocol

    secret = yield from http.get_text(
        "https://example.com/secret"
    )  # secret is a str; HttpError joins the error channel
    if secret != "hunter2":
        yield from E.fail(
            SecretInvalidError(secret)
        )  # SecretInvalidError joins the error channel
    return secret


# program can be executed only after its requirements are provided
program = (
    E.RequirementProvider()
    .and_provide(HttpClient.Protocol)(HttpClient.Live())
    .apply(check_secret())
)

match E.run_sync(program):
    case E.Succeeded(value):
        print(value)  # "hunter2"
    case E.Failure(cause):
        print(cause)  # Fail(SecretInvalidError(...)) or Fail(HttpStatusError(...))
```

## Installation

Requires Python 3.14 or later.

```sh
uv add effecton
# or
pip install effecton
```

## Features

* *Type-safe errors* -- stop guessing what a given function throws; implement surgical error handling to build reliable systems.
* *Dependency injection* -- with requirements, dependencies become visible. In tests, another implementation can be trivially injected. Forgetting to do so is a type error.
* *Finalizers* -- granular resource management.
* *Ergonomic* -- generator-based syntax with `@E.gen` and functional-style `flat_map`, `map`, and friends.


## Motivation

Effect based systems provide programmers with building blocks that might be difficult at first but yield benefits in the future. Handling edge cases and thorough testing might be optional in the prototype stage but becomes critical in production.

Furthermore, *agents love* strict type systems and building blocks.

*Full example*: [skills-cli](https://github.com/krzkaczor/effecton/tree/main/packages/examples/skills-cli), a small CLI for installing agent skills built entirely on effecton services.

## Overview

### Building effects

```python
E.success(21).map(lambda x: x * 2)  # Effect[int]

E.sync(lambda: print("hi"))  # Effect[None] — defers a side effect until the effect runs


# Custom errors need to extend EffectonError
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


E.fail(OopsError(msg="oops"))  # Effect[Never, OopsError]
```

`suspend` defers building an effect. The thunk form wraps one effect; as a decorator on a function with parameters, each call captures its arguments and defers the body until the effect runs:

```python
E.suspend(lambda: E.fail(OopsError(msg="later")))  # Effect[Never, OopsError]


@E.suspend
def find_user(user_id: int) -> E.Effect[str, OopsError]:
    print("runs only when the effect is interpreted")
    return E.success(f"user-{user_id}")


find_user(1)  # Effect[str, OopsError] — nothing printed yet
```

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/test_run_sync.py), [`test_suspend.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/test_suspend.py).

### Running effects

Effects are inert values; `run_sync` interprets one and returns an `Exit`:

```python
match E.run_sync(effect):  # Exit[A, E] = Succeeded[A] | Failure[E]
    case E.Succeeded(value):
        ...
    case E.Failure(cause):
        ...  # cause is Fail(error) for typed failures, Die(defect) for unexpected exceptions
```

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/test_run_sync.py).

### Error handling

Use `catch_all` to handle errors:

```python
p = E.fail(OopsError(msg="oops")).catch_all(
    lambda e: E.success(f"recovered from {e.msg}")
)  # Effect[str] — the error channel is now Never

E.run_sync(p)  # Succeeded("recovered from oops")
```

Use `catch_all` with `if` to selectively handle errors:

```python
n = random.randint(1, 4)

p = E.success(n).flat_map(
    lambda r: E.fail(FatalError()) if r == 2 else E.fail(RecoverableError())
)  # Effect[never, FatalError | RecoverableError]

p2 = p.catch_all(
    lambda e: E.success(42) if isinstance(e, RecoverableError) else E.fail(e)
)  # Effect[int, FatalError]
```

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/test_run_sync.py).

### Requirements and providing them

`require(T)` reads a dependency and records it in the `R` channel; composing effects unions their requirements, exactly like errors. `run_sync` only accepts `Effect[A, E]`, so running an effect with unmet requirements is a type error, not a runtime surprise.

```python
@dataclass(frozen=True)
class Db:
    url: str


needs_db = E.require(Db).map(lambda db: db.url)  # Effect[str, Never, Db]

program = (
    E.RequirementProvider().and_provide(Db)(Db("postgres://x")).apply(needs_db)
)  # Effect[str] — requirements discharged, runnable

E.run_sync(program)  # Succeeded("postgres://x")
```

`and_provide(T)(impl)` is curried so a mismatched implementation is a static error, and `apply` demands that the provided union covers the effect's whole `R`. Requirement keys are exact types: providing a base class for a subclass requirement type-checks but dies with a `MissingRequirement` defect.

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/test_run_sync.py).

### Implicit requirements

Some dependencies, such as a logger or a log level, should work out of the box yet stay overridable. An implicit requirement is a class that extends the `ImplicitRequirement` protocol with a `default()` classmethod. Reading one with `require_implicit(X)` types as `Effect[X]`: it never enters `R`, so a program that only uses implicit requirements runs bare. If the lookup misses, the interpreter falls back to `X.default()`, computed once per process and memoized, so defaults must be immutable values.

```python
@final
@dataclass(frozen=True)
class Greeting(E.ImplicitRequirement):
    text: str

    @classmethod
    def default(cls) -> Greeting:
        return Greeting("hello")


E.run_sync(
    E.require_implicit(Greeting)
)  # Succeeded(Greeting("hello")) — nothing provided

# override for a sub-effect only; the env is restored when it settles
E.run_sync(E.provide_implicit(E.require_implicit(Greeting), Greeting("hi")))
```

`provide_implicit(effect, value)` is keyed by `type(value)`, so mark implicit requirement classes `@final`. Overrides also compose in a `RequirementProvider` chain through `and_provide`. `require_implicit` is a separate accessor rather than an overload on `require` because the overload pair silently drops requirements from `R` in some inference positions (pinned in `test_types_implicit_requirement.py`). One footgun: the runtime check only tests that a `default` attribute exists, so a plain requirement class that defines one gets the default fallback instead of a `MissingRequirement` defect.

More examples: [`test_implicit_requirement.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/test_implicit_requirement.py).

### Resource management with `on_exit` and Scope

`on_exit` attaches a finalizer that runs when the effect settles, on success and failure alike. A `Scope` collects finalizers from a whole sub-tree: `acquire_and_release` registers a release for an acquired resource, and `scoped` provides the `Scope` and runs the collected finalizers in reverse order when the wrapped effect settles.

```python
E.success(21).on_exit(E.log_info("done"))  # finalizer runs on success and failure alike

conn = E.acquire_and_release(
    E.sync(lambda: pool.connect()),  # acquire
    lambda c: E.sync(c.close),  # release, guaranteed by the enclosing scope
)  # Effect[Connection, Never, Scope]

program = E.scoped(
    conn.flat_map(run_queries)
)  # Scope discharged; close() runs when program settles
```

A finalizer that dies doesn't skip the remaining finalizers; its defect surfaces in the final `Exit`.

More examples: [`test_scope.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/std/test_scope.py).

### Generator syntax

`@E.gen` turns a generator function into a factory of effects: the interpreter runs each yielded effect and sends its success value back into the generator, and the generator's return value becomes the effect's success value. Write `x = yield from effect`, not `x = yield effect` — `Effect.__iter__` is typed so `yield from` gives `x` the effect's success type, while a bare `yield` types as `Any`.

```python
@E.gen
def total(n: int) -> E.EffectGen[int, OopsError]:
    a = yield from E.success(20)  # a: int — yield from types the sent-back value

    if n < 0:
        yield from E.fail(
            OopsError(msg="negative")
        )  # OopsError joins the error channel
    return a + n


E.run_sync(total(22))  # Succeeded(42)
```

A failing yielded effect abandons the generator, so `try/except` around a `yield` never observes effect failures — use `catch_all` on the resulting effect instead.

More examples: [`test_gen.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/test_gen.py).

### Wrapping third party code

`attempt` runs an exception-throwing thunk lazily and maps expected exceptions into the typed error channel. Re-raise unexpected exceptions from the mapper so they stay defects:

```python
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

More examples: [`test_attempt.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/test_attempt.py).

## Standard library

### Logger

Effecton comes with pretty logger out of the box.

```python
E.run_sync(E.log_info("user created", 42))  # pretty-printed to stderr, no setup needed

program = E.annotate_logs(
    handle_request(), request_id="r-1"
)  # every log inside carries request_id=r-1

captured: list[E.LogData] = []
E.run_sync(
    E.provide_implicit(
        program, E.CurrentLoggers((E.EffectonLogger(log=captured.append),))
    )
)
```

More examples: [`test_logger.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/std/test_logger.py), [`test_pretty_logger.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/tests/std/test_pretty_logger.py).

## Roadmap

- [ ] `ty` support
- [ ] Support for async/sync code
- [ ] Retries
- [ ] Timeouts
- [ ] `Random` implicit service
- [ ] More examples of integrations with existing ecosystem (fastapi, pydantic etc.)

## Inspirations

* Effect-TS/ZIO
* stateless

## Contributing

See [CONTRIBUTING.md](https://github.com/krzkaczor/effecton/blob/main/CONTRIBUTING.md) for repo setup and development commands.
