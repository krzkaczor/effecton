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
    Fail,
    FailCause,
    FlatMap,
    Interrupt,
    Node,
    OnExit,
    OnFailure,
    ProvideRequirement,
    Require,
    Success,
    Sync,
)
from effecton.exit import Exit, Failure, Succeeded, unwrap
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


def run_async[A, E: EffectonError](effect: Effect[A, E]) -> A:
    """Run an effect on a fresh asyncio loop and return its value.

    Owns the event loop through asyncio.run, so it cannot be called from
    a running loop; use run_async_coroutine there. A typed failure raises the
    error itself, a defect re-raises the exception (or UnhandledDefect
    for a non-exception value) and an interruption re-raises the
    exception that signalled it. Use run_async_exit to receive the Exit
    instead.
    """
    return unwrap(run_async_exit(effect))


def run_async_exit[A, E: EffectonError](effect: Effect[A, E]) -> Exit[A, E]:
    """Run an effect on a fresh asyncio loop and return its Exit.

    Owns the event loop through asyncio.run, so it cannot be called from
    a running loop; use run_async_coroutine there.
    """
    return asyncio.run(run_async_coroutine(effect))


async def run_async_coroutine[A, E: EffectonError](effect: Effect[A, E]) -> Exit[A, E]:
    """Interpret an effect under asyncio, awaiting every coroutine effect.

    This is the coroutine form for a caller that already owns a loop:
    pass it to asyncio.run, create_task or await it directly.

    A cancellation, or any other BaseException raised by an await, a
    thunk or a callback, unwinds the effect with an Interrupt cause so
    finalizers run, and the run settles as Failure(Interrupt(exception)).
    The cancellation is consumed: a caller whose task should stop
    re-raises the carried exception. Finalizers are shielded: a
    cancellation that arrives while one is awaiting is remembered, the
    finalizer runs to completion, and the interruption is applied once
    it settles.
    """
    stack: list[Frame | Finalizing] = []
    env: dict[TypeForm[Any], Any] = {}
    cancelled: BaseException | None = None
    finalizing = 0
    current: Node = effect  # ty: ignore[invalid-assignment]

    def unwind(e: BaseException) -> Node:
        nonlocal cancelled
        if isinstance(e, Exception):
            return FailCause(cause=Die(defect=e))
        if cancelled is None:
            cancelled = e
        return FailCause(cause=Interrupt(exception=e))

    def guarded[**P](f: Callable[P, Node], *args: P.args, **kwargs: P.kwargs) -> Node:
        try:
            return f(*args, **kwargs)
        except BaseException as e:
            return unwind(e)

    async def awaited(fn: Callable[[], Awaitable[Any]]) -> Node:
        try:
            return Success(await fn())
        except BaseException as e:
            return unwind(e)

    async def awaited_uninterruptibly(fn: Callable[[], Awaitable[Any]]) -> Node:
        async def run() -> Any:  # noqa: ANN401
            return await fn()

        # The finalizer runs as its own task so a cancellation of this
        # task lands on the shield instead of aborting it. It shares this
        # task's Context rather than a copy, so context variables it sets
        # or resets behave as if it ran inline.
        task = asyncio.current_task()
        inner = asyncio.get_running_loop().create_task(
            run(), context=task.get_context() if task is not None else None
        )

        # Remember the cancellation and keep waiting for the finalizer.
        while not inner.done():
            try:
                await asyncio.shield(inner)
            except BaseException as e:
                unwind(e)
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
                            current = _interrupted(cancelled, finalizing) or outcome
                            break
                        case FlatMap():
                            current = guarded(run_fn_or_die, item.and_then, value)
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
                            stack.append(Finalizing(outcome=current))
                            finalizing += 1
                            current = finalizer  # ty: ignore[invalid-assignment]
                            break
                        case Finalizing():
                            # The finalizer died; its defect replaces the
                            # outcome it was finalizing.
                            finalizing -= 1
                            interrupted = _interrupted(cancelled, finalizing)
                            if interrupted is not None:
                                current = interrupted
                                break
                        case FlatMap():
                            continue
                        case OnFailure():
                            if isinstance(cause, Fail):
                                current = guarded(
                                    run_fn_or_die, item.handler, cause.error
                                )
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


def _interrupted(cancelled: BaseException | None, finalizing: int) -> Node | None:
    """The node to resume with once the outermost finalizer settles.

    Interruption is sticky: a cancellation noted while finalizers ran is
    applied as soon as the run becomes interruptible again, overriding a
    resumed success or a finalizer defect. Inside a nested finalizer it
    is deferred, so the enclosing finalizer runs to completion.
    """
    if cancelled is None or finalizing > 0:
        return None
    return FailCause(cause=Interrupt(exception=cancelled))
