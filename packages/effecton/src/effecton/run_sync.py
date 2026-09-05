from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, assert_never, final

from typing_extensions import TypeForm

from effecton.effect import (
    Coroutine,
    Die,
    Effect,
    EffectonError,
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
from effecton.exit import Exit, Failure, Succeeded
from effecton.implicit_requirement import ImplicitRequirement, resolve_default


@final
@dataclass(frozen=True)
class MissingRequirement:
    """Defect raised when an unprovided requirement is requested at runtime.

    Unreachable through fully typed code.
    """

    requirement_type: TypeForm[Any]


@final
@dataclass(frozen=True)
class AsyncEffectInSyncRun:
    """Defect raised when run_sync reaches a coroutine effect.

    Only run_async can await; run this effect with run_async instead.
    """


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


def run_sync[A, E: EffectonError](effect: Effect[A, E]) -> Exit[A, E]:
    stack: list[Frame] = []
    env: dict[TypeForm[Any], Any] = {}
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
                            if not isinstance(cause, Die):
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
        # Exclude the protocol class itself
        and not getattr(requirement_type, "_is_protocol", False)
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
