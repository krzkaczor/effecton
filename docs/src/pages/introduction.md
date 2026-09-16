---
title: Introduction
description: What effecton is, how to install it, and a first program.
---

# Introduction

effecton is a typed effect system for Python, inspired by [Effect-TS](https://effect.website/). It is early stage and experimental.

The core type is `Effect[A, E, R]`: a description of a computation that succeeds with `A`, fails with a typed error `E`, and requires `R` dependencies. Building an effect performs no work. You get a plain value that you can compose, pass around and test, and a runner executes it at the edge of your program.

## Installation

effecton requires Python 3.14 or later.

```sh
uv add effecton
# or
pip install effecton
```

## A first program

Consumer code imports the package once as `E` and reaches everything through it. Hover any name in the snippet to see the type ty infers for it.

```python
from dataclasses import dataclass
from typing import final

import effecton as E


# Custom errors extend EffectonError and are final: one leaf class per cause
@final
@dataclass(frozen=True)
class SecretInvalidError(E.EffectonError):
    actual: str


# Succeeds with str, fails with SecretInvalidError or an HTTP error,
# and requires an HttpClient
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


# The program can only run once its requirements are provided
program = check_secret().provide(E.HttpClient.Protocol)(E.HttpClient.SyncLive())
#  ^?

match E.run_sync_exit(program):
    case E.Succeeded(value):
        print(value)  # "hunter2"
    case E.Failure(cause):
        print(cause)  # Fail(SecretInvalidError(...)) or Fail(StatusError(...))
```

Three things happen here:

- **Errors are typed.** The signature lists every way `check_secret` can fail. `catch` handles one error class at a time and removes it from the type, so the checker knows what is left.
- **Requirements are visible.** `E.require` puts `HttpClient.Protocol` into the `R` channel. Forgetting to provide it is a type error, not a runtime surprise, and a test can provide `E.HttpClient.Test` instead of the live client.
- **Nothing runs until you say so.** `program` is a value. `run_sync_exit` interprets it and returns an `Exit` to match on. `run_sync` returns the value and raises on failure.

## What you get

- **Type-safe errors.** One frozen `EffectonError` dataclass per failure cause, precise unions in signatures, and `catch` / `catch_all` to handle them.
- **Dependency injection.** Requirements are part of the type. Provide them one at a time with `provide(T)(impl)`.
- **Resource management.** `on_exit` finalizers and `Scope` release resources in reverse order, on success and failure alike.
- **Generator syntax.** `@E.gen` with `yield from` reads like ordinary sequential code while staying fully typed.
- **A standard library.** Logger, `Clock`, `Random`, `FileSystem`, `Process` and `HttpClient` services, each with a live and a test implementation, plus fibers, racing, timeouts and retries.
- **Sync and async runners.** The same effect runs under `run_sync` or `run_async`. `run_main` is the entry point for CLIs and reports failures with proper exit codes.

## Where next

The docs are being written. Until they cover more ground, the [README on GitHub](https://github.com/krzkaczor/effecton#readme) walks through every feature with examples, and [skills-cli](https://github.com/krzkaczor/effecton/tree/main/packages/examples/skills-cli) is a small CLI built entirely on effecton services.
