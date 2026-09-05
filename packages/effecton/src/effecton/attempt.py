from collections.abc import Awaitable, Callable

from effecton.effect import Effect, EffectonError, coroutine, fail, success
from effecton.suspend import suspend


@suspend
def attempt[A, E: EffectonError](
    thunk: Callable[[], A], on_error: Callable[[Exception], E]
) -> Effect[A, E]:
    """Run an exception-throwing thunk lazily, with typed failures.

    The thunk runs once per run of the effect, like sync. When it raises,
    on_error maps the exception into the typed error channel — under sync,
    every exception becomes an uncatchable defect. To keep an unexpected
    exception a defect, re-raise it from on_error.
    """
    try:
        return success(thunk())
    except Exception as e:
        return fail(on_error(e))


def attempt_async[A, E: EffectonError](
    thunk: Callable[[], Awaitable[A]], on_error: Callable[[Exception], E]
) -> Effect[A, E]:
    """Await an exception-throwing thunk lazily, with typed failures.

    The async counterpart of attempt: the thunk builds a fresh awaitable
    once per run of the effect, like coroutine, and on_error maps an
    exception raised by the thunk or by the await into the typed error
    channel. Re-raise from on_error to keep an unexpected exception a
    defect. Only run_async can interpret the result.
    """

    async def go() -> Effect[A, E]:
        try:
            return success(await thunk())
        except Exception as e:
            return fail(on_error(e))

    return coroutine(go).flat_map(lambda effect: effect)
