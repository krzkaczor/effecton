from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, assert_never, final

from typing_extensions import TypeForm

from effecton.effect import (
    Coroutine,
    Die,
    Effect,
    EffectonError,
    Fail,
    FailCause,
    FlatMap,
    Node,
    OnExit,
    OnFailure,
    ProvideRequirement,
    Require,
    Success,
    Sync,
)
from effecton.exit import Exit, Failure, Succeeded, unwrap
from effecton.implicit_requirement import ImplicitRequirement, resolve_default
from effecton.std import clock


@final
@dataclass(frozen=True)
class MissingRequirement(Exception):
    """Defect for a requirement requested at runtime without being provided.

    Unreachable through fully typed code. run_sync_exit settles as
    Failure(Die(MissingRequirement(...))); run_sync raises it.
    """

    requirement_type: TypeForm[Any]

    def __str__(self) -> str:
        return f"No implementation provided for requirement {self.requirement_type!r}"


@final
@dataclass(frozen=True)
class AsyncEffectInSyncRun(Exception):
    """Defect for a coroutine effect reached by a synchronous runner.

    run_main and the run_async family can await. run_sync_exit settles as
    Failure(Die(AsyncEffectInSyncRun())); run_sync raises it.
    """

    def __str__(self) -> str:
        return "A coroutine effect cannot run synchronously; run it with run_async"


@final
@dataclass(frozen=True)
class RestoreEnv:
    """Interpreter stack frame delimiting a ProvideRequirement scope."""

    env: dict[TypeForm[Any], Any]


@final
@dataclass(frozen=True)
class OnExitFrame:
    finalizer: Effect[Any, Any, Any]


Frame = FlatMap[Any, Any, Any] | OnFailure[Any, Any, Any] | RestoreEnv | OnExitFrame


def run_sync[A, E: EffectonError](effect: Effect[A, E]) -> A:
    """Interpret an effect and return its value, raising on failure.

    A typed failure raises the error itself, a defect re-raises the
    exception (or UnhandledDefect for a non-exception value) and an
    interruption re-raises the exception that signalled it. Use
    run_sync_exit to receive the Exit instead.
    """
    return unwrap(run_sync_exit(effect))


def run_sync_exit[A, E: EffectonError](effect: Effect[A, E]) -> Exit[A, E]:
    """Interpret an effect and return its Exit.

    Coroutine effects are not awaited: reaching one settles the run as
    Failure(Die(AsyncEffectInSyncRun())), and finalizers still run. The
    Clock is the blocking SyncLive unless the effect provides another.
    """
    stack: list[Frame] = []
    env: dict[TypeForm[Any], Any] = {clock.Protocol: clock.SyncLive()}
    current: Node = effect  # ty: ignore[invalid-assignment]

    while True:
        match current:
            case Success(value):
                while stack:
                    item = stack.pop()

                    match item:
                        case RestoreEnv():
                            env = item.env
                        case OnExitFrame(finalizer):
                            current = finalizer.flat_map(resume(current))  # ty: ignore[invalid-assignment]
                            break
                        case FlatMap():
                            current = run_fn_or_die(item.and_then, value)
                            break
                        case OnFailure():
                            continue
                        case _:
                            assert_never(item)
                else:
                    return Succeeded(value=value)

            case FailCause(cause):
                while stack:
                    item = stack.pop()

                    match item:
                        case RestoreEnv():
                            env = item.env
                        case OnExitFrame(finalizer):
                            current = finalizer.flat_map(resume(current))  # ty: ignore[invalid-assignment]
                            break
                        case FlatMap():
                            continue
                        case OnFailure():
                            if isinstance(cause, Fail):
                                current = run_fn_or_die(item.handler, cause.error)
                                break
                        case _:
                            assert_never(item)
                else:
                    return Failure(cause=cause)

            case FlatMap(first):
                stack.append(current)
                current = first  # ty: ignore[invalid-assignment]

            case OnFailure(first):
                stack.append(current)
                current = first  # ty: ignore[invalid-assignment]

            case Sync(fn):
                try:
                    current = Success(fn())
                except Exception as e:
                    current = FailCause(cause=Die(defect=e))

            case Coroutine():
                current = FailCause(cause=Die(defect=AsyncEffectInSyncRun()))

            case Require(requirement_type):
                if requirement_type in env:
                    current = Success(env[requirement_type])
                else:
                    current = default_or_die(requirement_type)

            case ProvideRequirement(first, requirement_type, requirement_impl):
                stack.append(RestoreEnv(env))
                env = {**env, requirement_type: requirement_impl}
                current = first  # ty: ignore[invalid-assignment]

            case OnExit(first, finalizer):
                stack.append(OnExitFrame(finalizer))
                current = first  # ty: ignore[invalid-assignment]

            case _:
                assert_never(current)


def default_or_die(requirement_type: TypeForm[Any]) -> Node:
    if (
        isinstance(requirement_type, type)
        and issubclass(requirement_type, ImplicitRequirement)
        # Exclude the protocol class itself; its stub default() returns None.
        # Protocol subclasses with a concrete default() are fine (see std.clock).
        and requirement_type is not ImplicitRequirement
    ):
        try:
            return Success(resolve_default(requirement_type))
        except Exception as e:
            return FailCause(cause=Die(defect=e))

    return FailCause(cause=Die(defect=MissingRequirement(requirement_type)))


def run_fn_or_die(f: Callable[[Any], Effect[Any, Any]], value: object) -> Node:
    try:
        return f(value)  # ty: ignore[invalid-return-type]
    except Exception as e:
        return FailCause(cause=Die(defect=e))


# Captures the current outcome by closure.
def resume(outcome: Node) -> Callable[[Any], Effect[Any, Any, Any]]:
    def resume(_: object) -> Effect[Any, Any, Any]:
        return outcome

    return resume
