"""Fibers: run an effect concurrently and settle on it later.

fork starts an effect as a concurrent run and returns a Fiber handle;
join gives the fiber's value (failing as it failed), wait gives its
Exit, poll peeks without waiting and interrupt cancels it and waits.
yield_now lets other fibers run before continuing.

This is the asyncio-backed form: a forked effect runs as a task under
run_async_coroutine, so fork is async only (a coroutine effect that dies
with AsyncEffectInSyncRun under run_sync) and the forked run starts with
a fresh environment, so provide what it needs. An interrupt is an
asyncio cancellation: the fiber runs its finalizers and settles as
Failure(Interrupt(CancelledError())).
"""

import asyncio
from dataclasses import dataclass
from typing import final

from effecton.effect import (
    Effect,
    EffectonError,
    FailCause,
    Interrupt,
    coroutine,
    success,
    sync,
)
from effecton.exit import Exit, Failure, Succeeded
from effecton.run_async import run_async_coroutine


def fork[A, E: EffectonError](effect: Effect[A, E]) -> Effect[Fiber[A, E]]:
    """Start effect as a concurrent run and return its Fiber.

    The fiber starts on the next turn of the loop; yielding to the loop,
    for example through a Test clock move, lets it reach its first
    suspension before the caller continues.
    """

    async def start() -> Fiber[A, E]:
        return Fiber(asyncio.create_task(run_async_coroutine(effect)))

    return coroutine(start)


def yield_now() -> Effect[None]:
    """Let every other runnable fiber take a turn before continuing."""
    return coroutine(lambda: asyncio.sleep(0))


@final
@dataclass(frozen=True)
class Fiber[A, E: EffectonError]:
    task: asyncio.Task[Exit[A, E]]

    def join(self) -> Effect[A, E]:
        """The fiber's value, failing with the fiber's own cause."""

        def settle(exit: Exit[A, E]) -> Effect[A, E]:
            match exit:
                case Succeeded(value):
                    return success(value)
                case Failure(cause):
                    return FailCause(cause=cause)

        return self.wait().flat_map(settle)

    def wait(self) -> Effect[Exit[A, E]]:
        """The fiber's Exit once it settles; never fails itself."""

        async def settle() -> Exit[A, E]:
            # asyncio.wait, unlike awaiting the task, does not re-raise the
            # fiber's own cancellation into the waiting run.
            await asyncio.wait([self.task])
            return self._exit()

        return coroutine(settle)

    def poll(self) -> Effect[Exit[A, E] | None]:
        """The fiber's Exit if it has settled, else None, without waiting."""
        return sync(lambda: self._exit() if self.task.done() else None)

    def interrupt(self) -> Effect[Exit[A, E]]:
        """Cancel the fiber, let its finalizers run and return its Exit."""
        return sync(self.task.cancel).flat_map(lambda _: self.wait())

    def _exit(self) -> Exit[A, E]:
        # A fiber cancelled before its first step never ran the
        # interpreter, so its task is cancelled instead of holding an Exit.
        if self.task.cancelled():
            return Failure(cause=Interrupt(exception=asyncio.CancelledError()))
        return self.task.result()
