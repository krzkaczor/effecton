from typing import Any, assert_never

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
from effecton.run_sync import (
    Frame,
    OnExitFrame,
    RestoreEnv,
    default_or_die,
    resume,
    run_fn_or_die,
)


async def run_async[A, E: EffectonError](effect: Effect[A, E]) -> Exit[A, E]:
    """Interpret an effect, awaiting every coroutine effect it reaches.

    Only the thunks handed to ``coroutine`` are awaited, so any event loop
    works. A cancellation (any BaseException raised by an await) unwinds
    the effect as a defect so finalizers run, and is then re-raised
    instead of being returned as an Exit.
    """
    stack: list[Frame] = []
    env: dict[TypeForm[Any], Any] = {}
    cancelled: BaseException | None = None
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
                    if cancelled is not None:
                        raise cancelled
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
                    if cancelled is not None:
                        raise cancelled
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

            case Coroutine(fn):
                try:
                    current = Success(await fn())
                except Exception as e:
                    current = FailCause(cause=Die(defect=e))
                except BaseException as e:  # is some kinda of cancellation error
                    if cancelled is None:
                        cancelled = e
                    current = FailCause(cause=Die(defect=e))

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
