from effecton.effect import Die, Effect, EffectonError, FailCause, Node, Success
from effecton.exit import Exit
from effecton.run_sync import interpret


async def run_async[A, E: EffectonError](effect: Effect[A, E]) -> Exit[A, E]:
    """Interpret an effect, awaiting every coroutine effect it reaches.

    Only the thunks handed to ``coroutine`` are awaited, so any event loop
    works. A cancellation (any BaseException raised by an await) unwinds
    the effect as a defect so finalizers run, and is then re-raised
    instead of being returned as an Exit.
    """
    steps = interpret(effect)
    cancelled: BaseException | None = None

    try:
        fn = next(steps)
        while True:
            try:
                outcome: Node = Success(await fn())
            except Exception as e:
                outcome = FailCause(cause=Die(defect=e))
            except BaseException as e:
                if cancelled is None:
                    cancelled = e
                outcome = FailCause(cause=Die(defect=e))
            fn = steps.send(outcome)
    except StopIteration as e:
        if cancelled is not None:
            raise cancelled from None
        return e.value
