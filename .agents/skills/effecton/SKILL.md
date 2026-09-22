---
name: effecton
description: Best practices for writing Python with effecton, the typed effect system inspired by Effect-TS (`import effecton as E`, `Effect[A, E, R]`). Use whenever you write, review, refactor or test code that imports effecton — designing typed errors, building services with Protocol/Live/Test, writing `@E.gen` programs, wrapping exception-throwing or async code, providing requirements, running effects.
---

# effecton

effecton is a typed effect system for Python 3.14+, inspired by Effect-TS and typechecked with ty. An `E.Effect[A, E, R]` is a lazy description of a computation that succeeds with `A`, fails with `E` and needs `R` to run. Nothing happens until a runner interprets it. The signature is the contract: keep all three channels precise, and the type checker tells you what can go wrong and what is still missing.

Docs: <https://effecton.dev> · API reference: <https://effecton.dev/api> · exemplar program: [`packages/examples/skills-cli`](https://github.com/krzkaczor/effecton/tree/main/packages/examples/skills-cli).

## Ground rules

- **Import the package once as `import effecton as E`** and reach everything through it: `E.success`, `E.gen`, `class ParseError(E.EffectonError)`. Never use flat `from effecton import ...` imports in consumer code (applications, tests, docs, examples).
- **Check the API reference before inventing a combinator.** Names follow Effect-TS (`suspend`, `attempt`, `catch_all`, `flat_map`, `acquire_and_release`, `retry`, `timeout`), so the Effect-TS name is the first guess.
- **No abstract base classes, ever. Always `typing.Protocol` with `@runtime_checkable`.** Implementing classes still subclass the protocol explicitly, so a missing member is a static error.
- **Typed failures are for expected causes; everything else is a defect.** An unexpected exception must stay a `Die`, never be folded into a catch-all error.

## Errors

One error class per failure cause, never a generic bucket such as `AppError(message)`:

```python
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class UnsupportedHost(E.EffectonError):
    url: str
    host: str

    def __str__(self) -> str:
        return f"Unsupported host {self.host!r} in {self.url}"


@final
@dataclass(frozen=True)
class NotASkillFile(E.EffectonError):
    url: str

    def __str__(self) -> str:
        return f"{self.url} doesn't point to a SKILL.md"


type ParseUrlError = UnsupportedHost | NotASkillFile
```

- **Every error is a `@final`, frozen dataclass extending `E.EffectonError`.** Errors are leaves: never subclass one. `catch(T)` checks `isinstance` at runtime and subtracts `T` from the union statically, and the two only agree when no subclass exists.
- **Override `__str__` with the human-readable message**, so rendering a failure is just `str(error)`. Don't write a describe-the-error `match` at the CLI. An integer `exit_code` class attribute picks the process exit code under `E.run_main`.
- **Errors live in the module that raises them**, never in a central `errors.py`: service errors in the service module, program-level errors next to the program. Each module exports a local union alias (`type ParseUrlError = ...`).
- **Cross-module unions are composed from the exact errors the called operations raise**, through the module namespace: `config.ConfigError | E.FileSystem.FileNotFound | E.FileSystem.PermissionDenied`. Never reach for a service-wide umbrella such as `E.FileSystem.FileSystemError`.
- **Catch by class, never by predicate.** `effect.catch(NotASkillFile)(handler)` removes exactly that class from `E`; `catch_all` handles whatever is left. Both skip defects and interrupts.
- `catch` and `provide` are curried on purpose (`catch(T)(handler)`, `provide(T)(impl)`): binding the class first is what lets the type checker subtract it. Don't wrap them in one-call helpers.

## Wrapping exception-throwing code

`E.attempt(thunk, to_error)` runs the thunk lazily. The mapper translates only the exception types you expect and re-raises the rest, so they stay defects:

```python
import json
from dataclasses import dataclass
from typing import Any, final

import effecton as E


@final
@dataclass(frozen=True)
class InvalidJson(E.EffectonError):
    text: str

    def __str__(self) -> str:
        return f"Invalid JSON: {self.text!r}"


def parse_json(text: str) -> E.Effect[Any, InvalidJson]:
    def to_error(e: Exception) -> InvalidJson:
        if isinstance(e, json.JSONDecodeError):
            return InvalidJson(text)
        raise e  # anything else stays a defect

    return E.attempt(lambda: json.loads(text), to_error)
```

- `E.attempt_async(make_awaitable, to_error)` is the same for coroutines; `E.coroutine(lambda: client.get(url))` defers an awaitable whose exceptions should be defects. Pass a thunk that builds a fresh awaitable, because a coroutine object can be awaited only once.
- `E.sync(thunk)` defers an eager side effect whose exceptions should be defects. It is the usual body of a `Test` service method.
- **Use `@E.suspend` only where the body does eager work.** A body that only builds an `E.attempt(...)` doesn't need it, because `attempt` already defers. `suspend` is overloaded: a zero-argument thunk resolves to the deferred effect itself, and a function with parameters becomes a callable that defers its body on each call.

## Generator programs

```python
import effecton as E


@E.gen
def read_config(
    root: E.Path,
) -> E.EffectGen[str, E.FileSystem.ReadError, E.FileSystem.Protocol]:
    fs = yield from E.require(E.FileSystem.Protocol)

    text = yield from fs.read_file_string(root / "config.toml")
    yield from E.log_info("Read config from:", root)
    return text
```

- **Always `yield from`, never a bare `yield`.** `Effect.__iter__` types the value sent back per expression; a bare `yield` types as `Any`.
- **Requirement acquisition goes at the top of the body** (`yield from E.require(...)` / `E.require_implicit(...)`), then one blank line, then the rest. Never reorder an acquisition across a guard just to group it.
- Annotate the return as `E.EffectGen[A, E, R]` and spell the error union out. Fail with `yield from E.fail(SomeError(...))`.
- A failing yielded effect abandons the generator, so `try/except` around a `yield from` never sees effect failures. Use `catch` / `catch_all` on the effect instead.
- The generator stays synchronous even when it yields async effects; the runner decides how they execute.

## Services and requirements

One module per service, exporting `Protocol`, `Live` and `Test`. Consumers alias the module and go through it:

```python
"""Terminal service: Protocol plus Live (real prompt) and Test (canned answer)."""

import typing
from dataclasses import dataclass, field
from typing import runtime_checkable

import effecton as E


@runtime_checkable
class Protocol(typing.Protocol):
    def confirm(self, prompt: str) -> E.Effect[bool]: ...


class Live(Protocol):
    @E.suspend
    def confirm(self, prompt: str) -> E.Effect[bool]:
        return E.success(input(f"{prompt} [y/N] ").lower() == "y")


@dataclass
class Test(Protocol):
    answer: bool = True
    prompts: list[str] = field(default_factory=list)

    @E.suspend
    def confirm(self, prompt: str) -> E.Effect[bool]:
        self.prompts.append(prompt)
        return E.success(self.answer)
```

- Import it as `from my_app import terminal as Terminal`, then use `Terminal.Protocol`, `Terminal.Live()`, `Terminal.Test()`. Std services follow the same shape: `E.Clock`, `E.Random`, `E.FileSystem`, `E.Process`, `E.HttpClient`, `E.Cli`, `E.Tracer`.
- `Test` implementations are plain dataclasses that record what they received (`prompts`, `requests`, `files`), so tests can assert on the recorded state afterwards.
- Read a dependency with `E.require(T)`; it lands in `R`. `effect.provide(T)(impl)` subtracts it, one requirement at a time, anywhere in the program. The runners only accept an effect whose `R` is `Never`, so an unmet requirement is a type error.
- Services that touch the outside world ship a live implementation per runner: `SyncLive` for `E.run_sync`, `AsyncLive` for the `E.run_async` family and `E.run_main`.
- **Implicit requirements** are for dependencies that should work out of the box yet stay overridable (logger, log level, clock). Extend `E.ImplicitRequirement` with a `default()` classmethod, mark the class `@final`, keep the default immutable, and read it with `E.require_implicit(X)`; it never enters `R`. Override with `E.provide_implicit(effect, value)`, which is keyed by `type(value)`. A protocol-typed implicit service such as the clock is provided with `.provide(E.Clock.Protocol)(impl)` instead.

## Side effects go through services

- **Paths are `E.Path` and every read or write goes through `E.FileSystem`.** `E.Path` has no I/O members on purpose. Don't reach the disk through `pathlib`, `os.path`, `shutil`, `tempfile` or the `os` file functions; a program that does is no longer testable against `E.FileSystem.Test`.
- **Time goes through `E.now()` and `E.sleep(timedelta)`**, not `datetime.now`, `time.time` or `time.sleep`, so `E.Clock.Test` can drive it. Randomness goes through `E.random()` / `E.Random`, HTTP through `E.HttpClient`, the working and home directories and the environment through `E.Process`, and logging through `E.log_info` and friends.
- Resources are acquired with `E.acquire_and_release(acquire, release)` and discharged with `.scoped()`; one-off cleanup attaches with `.on_exit(finalizer)`. Finalizers run on success, failure and interruption alike.
- Resilience is composition, not hand-rolled loops: `effect.retry(E.Schedule.exponential(base), times=5)`, `effect.timeout(timedelta(seconds=5))`, `E.race_first(...)`, `E.fork(effect)`.

## Command-line programs

- **Use `E.Cli`, not typer or click.** Arguments are a `Cli.Args` class with `Annotated[T, Cli.Option(help=...)]` / `Cli.Argument(...)` fields; `str`, `int`, `float`, `E.Path`, `datetime`, `date` and `Literal[...]` of strings infer their text codec, `bool` is a flag, `T | None` is optional, `tuple[T, ...]` repeats, and any `S.Schema[T, str]` goes in `schema=`.
- A command is `Cli.command(name, args=Args, handler=run_it, help=...)`, where the handler returns `E.Effect[None, E, R]`; parents are `Cli.command(name, help=...).with_subcommands(...)`. `Cli.run(app)` is one effect requiring `E.Process`; wire the `Live` services at the root and hand it to `E.run_main`. Output is `E.sync(lambda: print(...))` inside the handler.
- Parsing failures are one `Cli.UsageError` (exit code 2) carrying a `reason` — `UnknownOption`, `MissingCommand`, `InvalidArguments`, and the like — so `effect.catch(Cli.UsageError)(handler)` catches every parsing failure at once; `--help` and `--version` succeed. Test a CLI with `E.Process.Test(arguments=(...))`, `Test` services and `E.run_sync_exit`; never a `CliRunner` or monkeypatching.

## Running effects

- **`E.run_main(effect)` at a process entry point.** It runs sync and async effects, logs a typed failure through `str(error)`, exits with the error's `exit_code` (default `1`), handles Ctrl+C and SIGTERM, and returns the success value so the CLI can print it. Wire the `Live` services in the entry point and nowhere else.
- `E.run_sync(effect)` returns the value or raises the error; `E.run_sync_exit(effect)` never raises and returns an `E.Exit` to match on (`E.Succeeded(value)` / `E.Failure(cause)` with `E.Fail`, `E.Die` or `E.Interrupt`). `E.run_async`, `E.run_async_exit` and `await E.run_async_coroutine(effect)` are the async counterparts.
- The same program runs under either runner; only the provided implementations change (`SyncLive` vs `AsyncLive`).

## Tests

```python
import effecton as E


@E.gen
def read_config(
    root: E.Path,
) -> E.EffectGen[str, E.FileSystem.ReadError, E.FileSystem.Protocol]:
    fs = yield from E.require(E.FileSystem.Protocol)

    return (yield from fs.read_file_string(root / "config.toml"))


def test_reads_the_config():
    fs = E.FileSystem.Test(files={E.Path("/repo/config.toml"): "[packages]\n"})

    result = E.run_sync(read_config(E.Path("/repo")).provide(E.FileSystem.Protocol)(fs))

    assert result == "[packages]\n"


def test_fails_when_the_config_is_missing():
    fs = E.FileSystem.Test()

    exit = E.run_sync_exit(
        read_config(E.Path("/repo")).provide(E.FileSystem.Protocol)(fs)
    )

    assert exit == E.Failure(
        E.Fail(E.FileSystem.FileNotFound(E.Path("/repo/config.toml")))
    )
```

- **Arrange-Act-Assert, with exactly one blank line between the three blocks.**
- **Provide `Test` implementations instead of monkeypatching.** No network, no disk, no real clock. Assert on the `Exit` for failures (`E.Failure(E.Fail(SomeError(...)))`) and on the recorded state of the test services.
- Collocate tests next to the module they cover as `test_<module>.py`.
- effecton ships a pytest plugin: a test may itself be a `@E.gen` function returning an effect, and requesting the `test_clock` fixture provides an `E.Clock.Test` to move by hand with `adjust(delta)` / `set_time(time)`. To test sleeps, retries and timeouts, `E.fork` the program, advance the clock, then await the fiber.
- Capture logs by providing loggers: `E.provide_implicit(effect, E.CurrentLoggers((E.EffectonLogger(log=entries.append),)))`.

## Code style

- **Nest helpers inside their only caller**, closing over locals (like `to_error` above). Module-level private helpers are for logic several functions share.
- **Order functions by importance**: public and more important functions come before the private helpers they call, so a module's entry point reads first and details follow. Forward references inside function bodies make this safe.
- Use exactly one blank line to separate blocks; never stack two, and never put one directly after a `def`.
- Literal arguments stay literal under ty (`E.success(1)` is `Effect[Literal[1]]`); covariance widens it wherever an `Effect[int]` is expected, so don't add casts or annotations to "fix" it.

## Review checklist

Before finishing a change that touches effecton code, confirm:

1. Every new error is `@final`, frozen, extends `E.EffectonError`, overrides `__str__`, lives in the module that raises it, and is listed in that module's union alias.
2. Every signature carries a precise `E` union and `R` union. No umbrella error types, no `Exception` in `E`.
3. `attempt` mappers re-raise what they don't recognise.
4. `@E.gen` bodies use `yield from` only, with requirement acquisition first.
5. No direct disk, clock, randomness, network or process access outside a service.
6. New services export `Protocol` (runtime-checkable), `Live` and `Test`, and the classes subclass the protocol.
7. Tests follow Arrange-Act-Assert and run against `Test` implementations.
8. The type checker and the tests pass.
