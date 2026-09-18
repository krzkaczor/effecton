---
title: Getting started
description: Install effecton, write a first program with generator syntax, run it, test it and handle its errors.
---

# Getting started

## Installation

effecton requires Python 3.14 or later.

```sh
uv add effecton
```

## Getting real

Generator syntax lets you write standard generator functions (decorated with `E.gen`) that produce effects and read like async/await code. In this example, `check_secret` returns an effect that fetches a secret from a web page and checks whether it is valid. If it is not, the effect fails with a specific error.

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class SecretInvalidError(E.EffectonError):
    actual: str


@E.gen
def check_secret() -> E.EffectGen[
    str,
    SecretInvalidError | E.HttpClient.TransportError | E.HttpClient.StatusError,
    E.HttpClient.Protocol,
]:
    http = yield from E.require(E.HttpClient.Protocol)

    response = yield from http.get("https://example.com/secret")
    response = yield from E.HttpClient.filter_status_ok(response)
    if response.text != "hunter2":
        yield from E.fail(SecretInvalidError(response.text))
    return response.text


program = check_secret().provide(E.HttpClient.Protocol)(E.HttpClient.SyncLive())
# ^?

result = E.run_sync(program)
# ^?
```

Three things to notice:

- **The signature is the contract.** `E.EffectGen[A, E, R]` says `check_secret` succeeds with a `str`, can fail with one of three errors, and needs an HTTP client.
- **Requirements are asked for, not looked up.** `yield from E.require(E.HttpClient.Protocol)` puts the client into `R`. Nothing is read from a global.
- **`provide` makes it runnable.** Providing the client turns `R` into `Never`. Before that, handing `program` to a runner is a type error.

## Running effects

`run_sync` returns the value and, on failure, raises the error as an exception (every `EffectonError` is an `Exception`). `run_sync_exit` never raises. It returns an `Exit[A, E]` that you can pattern match on:

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class SecretInvalidError(E.EffectonError):
    actual: str


@E.gen
def check_secret() -> E.EffectGen[
    str,
    SecretInvalidError | E.HttpClient.TransportError | E.HttpClient.StatusError,
    E.HttpClient.Protocol,
]:
    http = yield from E.require(E.HttpClient.Protocol)

    response = yield from http.get("https://example.com/secret")
    response = yield from E.HttpClient.filter_status_ok(response)
    if response.text != "hunter2":
        yield from E.fail(SecretInvalidError(response.text))
    return response.text


program = check_secret().provide(E.HttpClient.Protocol)(E.HttpClient.SyncLive())
# ---cut---
match E.run_sync_exit(program):
    case E.Succeeded(value):
        print(value)  # "hunter2"
    case E.Failure(cause):
        print(cause)  # Fail(SecretInvalidError(...)), Fail(StatusError(...)), Die(...)
```

:::info
There are more ways to run an effect, including `run_main` for CLI entry points, which logs the failure and picks an exit code. See [Running effects](/core/running-effects) and [Main programs](/core/main-programs).
:::

## Async / Sync split

Notice how we provided `E.HttpClient.SyncLive()`. `Live` means it is the real implementation that makes HTTP requests, as opposed to a `Test` implementation that returns canned responses. There is also `E.HttpClient.AsyncLive`, which awaits an async HTTP client, so the event loop keeps turning while a request is in flight. A program that uses it must run under an async runner:

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class SecretInvalidError(E.EffectonError):
    actual: str


@E.gen
def check_secret() -> E.EffectGen[
    str,
    SecretInvalidError | E.HttpClient.TransportError | E.HttpClient.StatusError,
    E.HttpClient.Protocol,
]:
    http = yield from E.require(E.HttpClient.Protocol)

    response = yield from http.get("https://example.com/secret")
    response = yield from E.HttpClient.filter_status_ok(response)
    if response.text != "hunter2":
        yield from E.fail(SecretInvalidError(response.text))
    return response.text


# ---cut---
program = check_secret().provide(E.HttpClient.Protocol)(E.HttpClient.AsyncLive())

result = E.run_async(program)
# ^?
```

`check_secret` itself did not change. The same effect runs synchronously or asynchronously depending on the implementations you provide and the runner you pick. `run_async` owns the event loop through `asyncio.run`. From inside a loop you already own, `await E.run_async_coroutine(program)` returns the `Exit` instead. See [Wrapping async code](/core/wrapping-async-code) for mixing in existing coroutines.

## Testing

Because the HTTP client is a requirement rather than a global, a test provides `E.HttpClient.Test` in its place. Seed it with a URL-to-body mapping, and it answers those URLs with a 200 and everything else with a 404:

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class SecretInvalidError(E.EffectonError):
    actual: str


@E.gen
def check_secret() -> E.EffectGen[
    str,
    SecretInvalidError | E.HttpClient.TransportError | E.HttpClient.StatusError,
    E.HttpClient.Protocol,
]:
    http = yield from E.require(E.HttpClient.Protocol)

    response = yield from http.get("https://example.com/secret")
    response = yield from E.HttpClient.filter_status_ok(response)
    if response.text != "hunter2":
        yield from E.fail(SecretInvalidError(response.text))
    return response.text


# ---cut---
def test_accepts_the_right_secret():
    http = E.HttpClient.Test(responses={"https://example.com/secret": "hunter2"})

    result = E.run_sync(check_secret().provide(E.HttpClient.Protocol)(http))

    assert result == "hunter2"


def test_rejects_a_wrong_secret():
    http = E.HttpClient.Test(responses={"https://example.com/secret": "letmein"})

    exit = E.run_sync_exit(check_secret().provide(E.HttpClient.Protocol)(http))

    assert exit == E.Failure(E.Fail(SecretInvalidError("letmein")))
```

No network, no monkeypatching, and the test client records every request it received in `http.requests`. Every standard library service ships with a `Test` implementation like this one. See [HttpClient](/std/http-client).

## Handling errors

`catch` handles one error class and removes it from the error channel, so the type checker knows exactly what can still go wrong:

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class SecretInvalidError(E.EffectonError):
    actual: str


@E.gen
def check_secret() -> E.EffectGen[
    str,
    SecretInvalidError | E.HttpClient.TransportError | E.HttpClient.StatusError,
    E.HttpClient.Protocol,
]:
    http = yield from E.require(E.HttpClient.Protocol)

    response = yield from http.get("https://example.com/secret")
    response = yield from E.HttpClient.filter_status_ok(response)
    if response.text != "hunter2":
        yield from E.fail(SecretInvalidError(response.text))
    return response.text


# ---cut---
tolerant = check_secret().catch(SecretInvalidError)(
    #  ^?
    lambda e: E.success(f"wrong secret: {e.actual}")
)
```

`SecretInvalidError` is gone from the error type. The two HTTP errors remain, and `catch_all` handles whatever is left. See [Error handling](/core/error-handling).

## Coding with agents

The repository ships an [Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) that teaches coding agents effecton's best practices: one `@final` error class per cause, the `Protocol` / `Live` / `Test` service pattern, `yield from` in `@E.gen` programs, side effects only through services, and tests against `Test` implementations. It lives in [`.agents/skills/effecton`](https://github.com/krzkaczor/effecton/tree/main/.agents/skills/effecton) as a single `SKILL.md`. Copy it into your project, and symlink it for Claude Code, which reads skills from `.claude/skills`:

```sh
mkdir -p .agents/skills/effecton .claude/skills
curl -fsSL https://raw.githubusercontent.com/krzkaczor/effecton/main/.agents/skills/effecton/SKILL.md \
  -o .agents/skills/effecton/SKILL.md
ln -s ../../.agents/skills/effecton .claude/skills/effecton
```

The agent sees the skill's one-line description in every session and loads the full guide when it works on code that imports effecton; in Claude Code you can also invoke it directly as `/effecton`.

## Where next

- [Building effects](/core/building-effects) starts the Core section: constructing and composing effects, typed errors, requirements, resources and generator syntax.
- [Logger](/std/logger) starts the Standard library section: the built-in services, each with a live and a test implementation, plus fibers, racing, timeouts and retries.
- The [API Reference](/api) lists every exported name with its signature and docstring.
- [skills-cli](https://github.com/krzkaczor/effecton/tree/main/packages/examples/skills-cli) is a complete CLI built entirely on effecton services.
