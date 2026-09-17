---
title: Introduction
description: What effecton is and why you would want to use it.
---

# Introduction

`effecton` is an [Effect system](https://en.wikipedia.org/wiki/Effect_system) for Python. In simple words: it's a library built around the idea of the `Effect[A, E, R]` type. An Effect represents a computation that can succeed with `A`, fail with `E`, and requires `R` to run.

An example is worth a thousand words, so:

```python
from dataclasses import dataclass
from typing import final

import effecton as E

program = E.success(5)
# ^?


# Custom errors should extend E.EffectonError
@final
@dataclass(frozen=True)
class CustomError(E.EffectonError):
    actual_value: str


program = E.fail(CustomError("wrong"))
# ^?


# Dependency injection is built right into the framework
program = E.require(E.HttpClient.Protocol)
# ^?
```

:::tip
The convention is to import the whole of effecton as `E`.
:::

:::note
Don't worry, most of the time you will use a [generator syntax](/core/generator-syntax) that reads and writes like async/await.
:::

It's important to understand that **none of these effects do anything yet**. They need to be run to execute. This allows composing effects like Lego blocks (for example: adding timeouts or retries).

## Why would you want to use it?

- **Type-safe errors.** No guessing what a given piece of code might throw. Handle specific errors with `catch` or `catch_all`.
- **Dependency injection.** Requirements are part of the type. All requirements need to be fulfilled before an effect can run.
- **Sync and async runners.** The same effect runs under `run_sync` or `run_async`.
- **Testability.** Since dependencies are explicit, tests can inject side-effect-free stubs.
- **Rich standard library.** Effecton needs building blocks that are also effect-based, and provides many of them: Logger, Tracer, FileSystem (sync/async), HttpClient (sync/async) and more.

## Motivation

Effect based systems provide programmers with building blocks that might be difficult at first but yield benefits in the future. Handling edge cases and thorough testing might be optional in the prototype stage but becomes critical in production.

Furthermore, *agents love* strict type systems and building blocks.

effecton is inspired by [Effect(TS)](https://effect.website/), [ZIO(Scala)](https://zio.dev/) and [stateless](https://github.com/suned/stateless). For a full example, see [skills-cli](https://github.com/krzkaczor/effecton/tree/main/packages/examples/skills-cli), a small CLI for installing agent skills built entirely on effecton services.

If this sounds intriguing, keep on reading the [getting started guide](/getting-started).
