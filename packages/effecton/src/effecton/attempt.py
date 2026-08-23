from collections.abc import Callable

from effecton.effect import Effect, EffectonError, fail, success
from effecton.suspend import suspend


def attempt[A, E: EffectonError](
    thunk: Callable[[], A], on_error: Callable[[Exception], E]
) -> Effect[A, E]:
    """Run an exception-throwing thunk lazily, with typed failures.

    The thunk runs once per run of the effect, like sync. When it raises,
    on_error maps the exception into the typed error channel — under sync,
    every exception becomes an uncatchable defect. To keep an unexpected
    exception a defect, re-raise it from on_error.
    """

    def go() -> Effect[A, E]:
        try:
            return success(thunk())
        except Exception as e:
            return fail(on_error(e))

    return suspend(go)
