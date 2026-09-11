# Effecton

[![PyPI](https://img.shields.io/pypi/v/effecton?logo=pypi&logoColor=white)](https://pypi.org/project/effecton/)
[![Discord](https://img.shields.io/badge/Discord-join%20chat-5865F2?logo=discord&logoColor=white)](https://discord.gg/fNhY7AxMyh)

A typed effect system for Python, inspired by [Effect-TS](https://effect.website/). Early stage and experimental.

An `Effect[A, E, R]` is a description of a computation that succeeds with `A`, fails with a typed error `E` and requires `R` dependencies.

```python
from dataclasses import dataclass
from typing import final

import effecton as E


# Custom errors extend EffectonError and are final: one leaf class per cause
@final
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
program = check_secret().provide(HttpClient.Protocol)(HttpClient.Live())

match E.run_sync_exit(program):
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


# Custom errors extend EffectonError and are final: one leaf class per cause
@final
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

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_sync.py), [`test_suspend.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_suspend.py).

### Running effects

Effects are inert values; a runner interprets one. The sync and async runners come in a throwing form that returns the value and an `_exit` form that returns an `Exit`. Use `run_main` at a process entry point to report failures and choose exit codes:

| Runner | Runs | Returns |
|---|---|---|
| `run_sync(effect)` | synchronously | the value, raising on failure |
| `run_sync_exit(effect)` | synchronously | `Exit[A, E]` |
| `run_async(effect)` | on a fresh asyncio loop (`asyncio.run` inside) | the value, raising on failure |
| `run_async_exit(effect)` | on a fresh asyncio loop (`asyncio.run` inside) | `Exit[A, E]` |
| `run_main(effect)` | on a fresh asyncio loop | the value, logging and exiting on failure |
| `await run_async_coroutine(effect)` | inside a loop you already own | `Exit[A, E]` |

`run_sync` and `run_async` raise a typed failure as the error itself (every `EffectonError` is an `Exception`), re-raise an exception defect as it is, wrap any other defect in `UnhandledDefect`, and re-raise the exception carried by an interruption:

```python
try:
    value = E.run_sync(effect)  # A
except HttpStatusError as e:  # a typed failure
    ...
```

The `_exit` forms never raise; they return an `Exit` to match on:

```python
match E.run_sync_exit(effect):  # Exit[A, E] = Succeeded[A] | Failure[E]
    case E.Succeeded(value):
        ...
    case E.Failure(cause):
        ...  # cause is Fail(error) for typed failures, Die(defect) for unexpected exceptions, Interrupt(exception) for cancellations
```

`run_async` and `run_async_exit` interpret the same effect under asyncio, awaiting every `coroutine` effect they reach. They own the event loop through `asyncio.run`, so they cannot be called from a running loop; `run_async_coroutine` is the coroutine underneath, for a caller that already has one:

```python
exit = await E.run_async_coroutine(
    effect
)  # Exit[A, E], awaiting coroutine effects along the way
```

Running an effect that contains a `coroutine` effect synchronously doesn't await it: `run_sync_exit` settles as `Failure(Die(AsyncEffectInSyncRun()))`, `run_sync` raises `AsyncEffectInSyncRun`, and finalizers still run in both cases.

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_sync.py), [`test_run_async.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_async.py).

### Main programs

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

Call `run_main` from the main thread, outside a running event loop. Both examples use it: [`skills-cli`](packages/examples/skills-cli/src/skills_cli/cli.py) and [`changesets`](packages/changesets/src/changesets/status/cli.py).

### Error handling

Use `catch_all` to handle errors:

```python
p = E.fail(OopsError(msg="oops")).catch_all(
    lambda e: E.success(f"recovered from {e.msg}")
)  # Effect[str] — the error channel is now Never

E.run_sync(p)  # "recovered from oops"
```

Use `catch` to handle one error type and leave the rest in the error channel. The handler receives the narrowed error, and defects (`Die`) pass through untouched:

```python
roll = E.random().flat_map(lambda rng: rng.randint(1, 4))

p = roll.flat_map(
    lambda r: E.fail(FatalError()) if r == 2 else E.fail(RecoverableError())
)  # Effect[Never, FatalError | RecoverableError]

p2 = p.catch(RecoverableError)(lambda e: E.success(42))  # Effect[int, FatalError]
```

`catch` is curried like `provide`: the error class is bound first so the type checker can subtract it from the union. Catching a class the effect cannot fail with is a well-typed no-op.

Error classes are leaves: mark every error `@final` and never subclass one. `catch` matches by class, and `@final` keeps its runtime `isinstance` check and the static subtraction in agreement, because the type checker cannot distinguish a subclass from its base when subtracting from a union.

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_sync.py).

### Requirements and providing them

`require(T)` reads a dependency and records it in the `R` channel; composing effects unions their requirements, exactly like errors. the runners only accept `Effect[A, E]`, so running an effect with unmet requirements is a type error, not a runtime surprise.

```python
@dataclass(frozen=True)
class Db:
    url: str


needs_db = E.require(Db).map(lambda db: db.url)  # Effect[str, Never, Db]

program = needs_db.provide(Db)(Db("postgres://x"))  # Effect[str] — runnable

E.run_sync(program)  # "postgres://x"
```

`provide(T)(impl)` subtracts the provided type from `R`, so requirements can be provided one at a time, anywhere in the program — a partially provided effect is an ordinary value carrying the remainder in `R`, and the runners accept it only once `R` reaches `Never`.

More examples: [`test_run_sync.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_sync.py).

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


E.run_sync(E.require_implicit(Greeting))  # Greeting("hello") — nothing provided

# override for a sub-effect only; the env is restored when it settles
E.run_sync(E.provide_implicit(E.require_implicit(Greeting), Greeting("hi")))
```

`provide_implicit(effect, value)` is keyed by `type(value)`, so mark implicit requirement classes `@final`. A `typing.Protocol` that extends `ImplicitRequirement` with a concrete `default()` is an implicit requirement too; its implementations are provided with `effect.provide(Protocol)(impl)` (the std `Clock` service works this way). Overrides also compose in a `provide` chain: `effect.provide(Greeting)(Greeting("hi"))`. `require_implicit` is a separate accessor rather than an overload on `require` because the overload pair silently drops requirements from `R` in some inference positions (pinned in `test_types_implicit_requirement.py`). One footgun: the runtime check only tests that a `default` attribute exists, so a plain requirement class that defines one gets the default fallback instead of a `MissingRequirement` defect.

More examples: [`test_implicit_requirement.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_implicit_requirement.py).

### Resource management with `on_exit` and Scope

`on_exit` attaches a finalizer that runs when the effect settles, on success and failure alike. A `Scope` collects finalizers from a whole sub-tree: `acquire_and_release` registers a release for an acquired resource, and `.scoped()` provides the `Scope` and runs the collected finalizers in reverse order when the wrapped effect settles. It composes with `provide` chains — `program.provide(Db)(db).scoped()` — and is a no-op on effects that never acquired a `Scope`, so it can uniformly terminate a chain.

```python
E.success(21).on_exit(E.log_info("done"))  # finalizer runs on success and failure alike

conn = E.acquire_and_release(
    E.sync(lambda: pool.connect()),  # acquire
    lambda c: E.sync(c.close),  # release, guaranteed by the enclosing scope
)  # Effect[Connection, Never, Scope]

program = conn.flat_map(
    run_queries
).scoped()  # Scope discharged; close() runs when program settles
```

A finalizer that dies doesn't skip the remaining finalizers; its defect surfaces in the final `Exit`.

More examples: [`test_scope.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_scope.py).

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


E.run_sync(total(22))  # 42
```

A failing yielded effect abandons the generator, so `try/except` around a `yield` never observes effect failures — use `catch` or `catch_all` on the resulting effect instead.

More examples: [`test_gen.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_gen.py).

### Wrapping third party code

`attempt` runs an exception-throwing thunk lazily and maps expected exceptions into the typed error channel. Re-raise unexpected exceptions from the mapper so they stay defects:

```python
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

### Wrapping async code

`coroutine` defers an awaitable the way `sync` defers a thunk: the thunk builds a fresh awaitable on every run, because a coroutine object can be awaited only once. Exceptions become defects. `attempt_async` is the `attempt` counterpart that maps expected exceptions into the error channel. `run_main` and the `run_async` family can interpret either:

```python
client = httpx.AsyncClient()

E.coroutine(lambda: client.get(url))  # Effect[httpx.Response] — nothing awaited yet


def get_text(url: str) -> E.Effect[str, HttpStatusError]:
    async def go() -> str:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    def to_error(e: Exception) -> HttpStatusError:
        if isinstance(e, httpx.HTTPStatusError):
            return HttpStatusError(url=url, status_code=e.response.status_code)
        raise e  # anything else stays a defect

    return E.attempt_async(go, to_error)


E.run_async(get_text("https://example.com"))  # text, or raises HttpStatusError

E.run_async_exit(
    get_text("https://example.com")
)  # Succeeded(text) or Failure(Fail(HttpStatusError(...)))
```

Inside `@E.gen` bodies, `yield from E.coroutine(...)` works like any other effect; the generator itself stays synchronous. If the task running `run_async_coroutine` is cancelled, the effect unwinds with an `Interrupt` cause, which `catch_all` and `catch` skip like a `Die`: finalizers and scope releases run, and the run settles as `Failure(Interrupt(exception))`, so an `asyncio.timeout` around `run_async_coroutine` doesn't leak resources and completes normally with that `Exit`. The cancellation is consumed by `run_async_coroutine`; a caller whose task should stop re-raises the carried exception. A finalizer that is mid-await when the cancellation arrives is shielded and runs to completion, and a cancellation raised from a synchronous thunk or callback, such as a cancelled future's `result()`, unwinds the same way.

More examples: [`test_run_async.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/test_run_async.py).

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

More examples: [`test_logger.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_logger.py), [`test_pretty_logger.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_pretty_logger.py).

### Clock

`E.now()` reads the current time and `E.sleep(duration)` pauses, both through the implicit `E.Clock` service, so neither enters `R`. `now()` returns a timezone-aware UTC `datetime` and is what the logger stamps `LogData.date` with. Sleeping depends on the runner, so the `Clock` protocol has no `default()`; instead there are two live clocks and each runner injects the matching one: `run_sync` installs `E.Clock.SyncLive`, whose sleep blocks the thread, and the `run_async` family (including `run_main`) installs `E.Clock.AsyncLive`, whose sleep awaits `asyncio.sleep`, keeps the loop turning and is interrupted by a cancellation like any coroutine effect.

```python
E.run_sync(E.now())  # datetime.now(UTC), no setup needed
E.run_sync(E.sleep(timedelta(seconds=1)))  # blocks for a second
E.run_async(E.sleep(timedelta(seconds=1)))  # awaits asyncio.sleep(1)
```

In tests, use `E.Clock.Test` and move it by hand with `adjust(delta)` or `set_time(time)`. Both return effects and are async only, like the clock's `sleep`, which parks until a move reaches its wake time (a sleep of zero returns at once). effecton ships a pytest plugin, loaded automatically wherever the package is installed, that runs a test returning an effect (typically a `@E.gen` function) under the async runner and reports a failure as its cause. A test that requests the `test_clock` fixture gets that clock provided to its effect, so `E.now()`, `E.sleep()` and the movers all see it:

```python
@E.gen
def test_reads_move_with_the_clock(test_clock: E.Clock.Test) -> E.EffectGen[None]:
    yield from test_clock.set_time(datetime(2024, 1, 1, tzinfo=UTC))

    first = yield from E.now()
    yield from test_clock.adjust(timedelta(minutes=5))
    second = yield from E.now()

    assert second == first + timedelta(minutes=5)
```

A sleeping program has to run concurrently with the moves: `E.fork` it and settle on the returned fiber. Each move yields to the loop before and after, so a program forked just before reaches its sleep, and a woken program progresses before the test continues.

Provide clocks with `.provide(E.Clock.Protocol)(...)`: `provide_implicit` is keyed by `type(value)`, so it would register a `Test` clock under `Test` rather than `Protocol`. This repo's ruff config bans direct time reads and sleeps (`datetime.now`, `time.time`, `time.monotonic`, `time.sleep`, `asyncio.sleep`, ...) outside the clock module, so all code goes through `E.now()` and `E.sleep()`.

More examples: [`test_clock.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_clock.py).

### Random

`E.random()` resolves the implicit `E.Random` service, so it never enters `R`. Its methods keep the names of the `random` standard library and each returns an effect: `random()`, `uniform(a, b)`, `randint(a, b)`, `choice(seq)` and `shuffle(seq)`, where `shuffle` returns a new list and leaves its input untouched. The default is `E.Random.Live`, which draws from the process-global generator behind the `random` module.

```python
@E.gen
def roll() -> E.EffectGen[int]:
    rng = yield from E.random()

    return (yield from rng.randint(1, 6))


E.run_sync(roll())  # 1..6, no setup needed
```

In tests, provide `E.Random.Test(seed)`: every draw is a function of the seed, and one instance advances as a single sequence, so the same seed always reproduces the same run. A test that requests the `test_random` fixture gets a `Test` seeded with 0 provided to its effect:

```python
@E.gen
def test_rolls_are_reproducible(test_random: E.Random.Test) -> E.EffectGen[None]:
    first = yield from roll()
    second = yield from roll()

    assert (first, second) == (4, 4)
```

Provide generators with `.provide(E.Random.Protocol)(...)`, as with the Clock. This repo's ruff config bans the `random` module's drawing functions (`random.random`, `random.randint`, `random.choice`, ...) outside the service module, so all code goes through `E.random()`; building a `random.Random(seed)` to compute expected values in a test is still allowed.

More examples: [`test_random.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_random.py).

### Fibers

`E.fork(effect)` starts an effect concurrently and returns an `E.Fiber`. `fiber.join()` is the fiber's value, failing with the fiber's own cause; `fiber.wait()` is its `Exit` and never fails; `fiber.poll()` peeks without waiting; `fiber.interrupt()` cancels it, lets its finalizers run and returns the `Exit`; `E.yield_now()` lets other fibers take a turn. Fibers are asyncio tasks underneath, so `fork` is async only and a forked run starts with a fresh environment: provide what it needs.

```python
@E.gen
def program() -> E.EffectGen[int]:
    fiber = yield from E.fork(fetch_total())  # runs concurrently
    other = yield from do_other_work()
    total = yield from fiber.join()  # Effect[int, FetchError]
    return total + other
```

More examples: [`test_fiber.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_fiber.py).

### Racing

`E.race_first(left, right)` returns the first completed outcome, whether success, typed failure, defect, or interruption. It interrupts the loser and awaits its finalizers; loser cleanup cannot replace the winner's outcome. The left wins when both are complete at selection. Cancelling the parent waits for both branches to finish cleanup.

Both branches inherit surrounding requirements, including the Clock, and the result carries the union of their value, error, and requirement types. Racing is async only: synchronous runners report `AsyncEffectInSyncRun`.

```python
# Stop the heartbeat when the operation completes; a heartbeat failure
# also stops the operation.
program = E.race_first(fetch_total(), heartbeat_forever())
```

Resource lifetime follows the owning scope: use `branch.scoped()` to release that branch's resources before the race returns. Resources acquired into a surrounding scope live until that scope closes. Racing `fiber.join()` interrupts the waiter; the independently forked fiber keeps running.

More examples: [`test_race.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_race.py).

### Timeouts

`effect.timeout(duration)` composes `race_first` with Clock sleep followed by a typed `TimeoutException`. If the deadline wins, it interrupts the effect and awaits its finalizers. The effect's own outcome, or a defect in the clock, otherwise propagates unchanged. Timeouts are async only, with the same requirement inheritance and cleanup rules as racing.

```python
fetch_total().timeout(
    timedelta(seconds=5)
)  # Effect[int, FetchError | TimeoutException]


@E.timeout(timedelta(seconds=5))
@E.gen
def fetch_user(user_id: int) -> E.EffectGen[User, FetchError]: ...


fetch_user(1).catch(E.TimeoutException)(lambda _: E.success(None))
# Effect[User | None, FetchError]
```

`E.timeout(duration)(effect)` is the curried form; decorating an effect-returning function wraps each result and preserves its call signature. Durations are `timedelta` values. Cancellation is cooperative: blocking synchronous work can delay a timeout, and cleanup can extend the total time beyond the deadline.

For deterministic tests, provide `E.Clock.Test` around the timeout, fork the program, then advance the clock and await the fiber. Both race branches start eagerly when the race runs, so the timer is registered before a subsequent clock adjustment.

More examples: [`test_timeout.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_timeout.py).

### Retries

`effect.retry(schedule, until=...)` re-runs an effect on a typed failure while the schedule recurs, sleeping through the Clock for each delay. Defects and interrupts are never retried. When the schedule is exhausted, or `until` holds for the error, the retry fails with that last error, so the error channel is unchanged.

```python
fetch_total().retry(E.Schedule.recurs(3))  # Effect[int, FetchError]

fetch_user(1).retry(
    E.Schedule.exponential(timedelta(seconds=1)),
    until=lambda e: isinstance(e, NotFound),
)  # Effect[User, FetchError | NotFound]
```

`E.Schedule.recurs(times)` recurs up to `times` more times without waiting, `E.Schedule.spaced(delay)` waits `delay` before every attempt, and `E.Schedule.exponential(base, factor=2.0)` waits `base`, then `base * factor`, and so on. The last two are unbounded; bound them with `until`. `schedule.jittered(min=0.8, max=1.2)` scales every delay by a factor drawn uniformly from `[min, max]` through the `E.Random` service, so `E.Random.Test(seed)` makes the jitter reproducible. Every run of the retried effect starts its schedule over.

```python
fetch_user(1).retry(E.Schedule.exponential(timedelta(seconds=1)).jittered())
```

A schedule is a factory of steps, and each step is an effect yielding the next delay, which is what lets `jittered` consult `Random`. Build a custom one with `E.Schedule.from_delays(...)` from any callable that yields a fresh iterator of `timedelta` values, or with `E.Schedule(steps=...)` when the delays are computed by effects.

There is no decorator form because `until` is typed by the effect's error channel, which a decorator cannot see. `recurs` needs no waiting and works under `run_sync`; for deterministic tests of delayed schedules, provide `E.Clock.Test`, fork the program, then advance the clock once per gap and await the fiber. A forked run starts with a fresh environment, so provide the test clock and a seeded `E.Random.Test` inside the forked program.

More examples: [`test_retry.py`](https://github.com/krzkaczor/effecton/blob/main/packages/effecton/src/effecton/std/test_retry.py).

## Roadmap

- [x] `ty` support
- [x] Support for async/sync code
- [x] Retries
- [x] Timeouts
- [x] `Random` implicit service
- [ ] More examples of integrations with existing ecosystem (fastapi, pydantic etc.)

## Inspirations

* Effect-TS/ZIO
* stateless

## Contributing

See [CONTRIBUTING.md](https://github.com/krzkaczor/effecton/blob/main/CONTRIBUTING.md) for repo setup and development commands.
