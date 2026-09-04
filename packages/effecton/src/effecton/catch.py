from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Never, TypeVar, final

from effecton.effect import Effect, EffectonError, OnFailure, fail

# Old-style TypeVars declare the variance ty cannot infer across the
# Effect ↔ CatchBinder reference cycle; see the ty inference notes in
# AGENTS.md.
A = TypeVar("A", covariant=True)
E = TypeVar("E", bound=EffectonError, covariant=True)
R = TypeVar("R", covariant=True)
T = TypeVar("T", bound=EffectonError)


@final
@dataclass(frozen=True)
class CatchBinder(Generic[A, E, R, T]):  # noqa: UP046
    """One step of ``effect.catch(T)(handler)``: T is bound, handler pending.

    Catch particular error E, return new Effect.
    """

    effect: Effect[A, E, R]
    error_type: type[T]

    def __call__[A2, B, E3: EffectonError, R2, R3, E2: EffectonError = Never](
        self: CatchBinder[A2, T | E2, R2, T],
        handler: Callable[[T], Effect[B, E3, R3]],
    ) -> Effect[A2 | B, E2 | E3, R2 | R3]:
        error_type = self.error_type

        return OnFailure[A2 | B, E2 | E3, R2 | R3](
            self.effect,
            lambda e: handler(e) if isinstance(e, error_type) else fail(e),
        )
