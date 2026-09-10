"""Timeouts compose race_first with Clock sleep and a typed failure."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
from typing import Any, final, overload

from effecton.effect import Effect, EffectonError, fail
from effecton.std.clock import _sleep
from effecton.std.race import race_first


def timeout(duration: timedelta) -> Timeout:
    """Bind the deadline; apply the result to an effect or a function."""
    return Timeout(duration=duration)


@final
@dataclass(frozen=True)
class TimeoutException(EffectonError):
    duration: timedelta

    def __str__(self) -> str:
        return f"Timed out after {self.duration}"


@final
@dataclass(frozen=True)
class Timeout:
    """One step of ``timeout(duration)(...)``: the deadline is bound."""

    duration: timedelta

    @overload
    def __call__[A, E: EffectonError, R](
        self, effect: Effect[A, E, R]
    ) -> Effect[A, E | TimeoutException, R]: ...

    @overload
    def __call__[**P, A, E: EffectonError, R](
        self, f: Callable[P, Effect[A, E, R]]
    ) -> Callable[P, Effect[A, E | TimeoutException, R]]: ...

    def __call__(
        self, target: Effect[Any, Any, Any] | Callable[..., Effect[Any, Any, Any]]
    ) -> Any:
        if isinstance(target, Effect):
            return self._apply(target)

        @wraps(target)
        def wrapper(*args: object, **kwargs: object) -> Effect[Any, Any, Any]:
            return self._apply(target(*args, **kwargs))

        return wrapper

    def _apply[A, E: EffectonError, R](
        self, effect: Effect[A, E, R]
    ) -> Effect[A, E | TimeoutException, R]:
        duration = self.duration

        return race_first(
            effect,
            _sleep(duration).flat_map(lambda _: fail(TimeoutException(duration))),
        )
