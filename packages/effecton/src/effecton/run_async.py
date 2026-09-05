import asyncio
from collections.abc import Awaitable, Callable
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
from effecton.run_sync import (
    Frame,
    OnExitFrame,
    RestoreEnv,
    default_or_die,
    run_fn_or_die,
)


@final
@dataclass(frozen=True)
class Finalizing:
    """Interpreter stack frame delimiting a running finalizer.

    Holds the outcome the finalizer interrupts, to resume once it settles.
    While one is on the stack, awaits are shielded from cancellation.
    """

    outcome: Node


async def run_async[A, E: EffectonError](effect: Effect[A, E]) -> Exit[A, E]:
    """Interpret an effect under asyncio, awaiting every coroutine effect.

    A cancellation, or any other BaseException raised by an await, a
    thunk or a callback, unwinds the effect as a defect so finalizers
    run, and is then re-raised instead of being returned as an Exit.
    Finalizers are shielded: a cancellation that arrives while one is
    awaiting is remembered and the finalizer runs to completion.
    """
    stack: list[Frame | Finalizing] = []
    env: dict[TypeForm[Any], Any] = {}
    cancelled: BaseException | None = None
    finalizing = 0
    current: Node = effect  # ty: ignore[invalid-assignment]

    def die(e: BaseException) -> Node:
        nonlocal cancelled
        if not isinstance(e, Exception) and cancelled is None:
            cancelled = e
        return FailCause(cause=Die(defect=e))

    def guarded[**P](f: Callable[P, Node], *args: P.args, **kwargs: P.kwargs) -> Node:
        try:
            return f(*args, **kwargs)
        except BaseException as e:
            return die(e)

    async def awaited(fn: Callable[[], Awaitable[Any]]) -> Node:
        try:
            return Success(await fn())
        except BaseException as e:
            return die(e)

    async def awaited_uninterruptibly(fn: Callable[[], Awaitable[Any]]) -> Node:
        try:
            inner = asyncio.ensure_future(fn())
        except BaseException as e:
            return die(e)

        # A cancellation of this task lands on the shield while the
        # finalizer keeps running; remember it and keep waiting.
        while not inner.done():
            try:
                await asyncio.shield(inner)
            except BaseException as e:
                die(e)
        return guarded(lambda: Success(inner.result()))

    while True:
        match current:
            case Success(value):
                while stack:
                    item = stack.pop()

                    match item:
                        case RestoreEnv():
                            env = item.env
                        case OnExitFrame(finalizer):
                            stack.append(Finalizing(outcome=current))
                            finalizing += 1
                            current = finalizer  # ty: ignore[invalid-assignment]
                            break
                        case Finalizing(outcome):
                            finalizing -= 1
                            current = outcome
                            break
                        case FlatMap():
                            current = guarded(run_fn_or_die, item.and_then, value)
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
                            stack.append(Finalizing(outcome=current))
                            finalizing += 1
                            current = finalizer  # ty: ignore[invalid-assignment]
                            break
                        case Finalizing():
                            # The finalizer died; its defect replaces the
                            # outcome it was finalizing.
                            finalizing -= 1
                            continue
                        case FlatMap():
                            continue
                        case OnFailure():
                            if not isinstance(cause, Die):
                                current = guarded(
                                    run_fn_or_die, item.handler, cause.error
                                )
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
                current = guarded(lambda: Success(fn()))

            case Coroutine(fn):
                current = await (
                    awaited_uninterruptibly(fn) if finalizing else awaited(fn)
                )

            case Require(requirement_type):
                if requirement_type in env:
                    current = Success(env[requirement_type])
                else:
                    current = guarded(lambda: default_or_die(requirement_type))

            case ProvideRequirement(first, requirement_type, requirement_impl):
                stack.append(RestoreEnv(env))
                env = {**env, requirement_type: requirement_impl}
                current = first  # ty: ignore[invalid-assignment]

            case OnExit(first, finalizer):
                stack.append(OnExitFrame(finalizer))
                current = first  # ty: ignore[invalid-assignment]

            case _:
                assert_never(current)
