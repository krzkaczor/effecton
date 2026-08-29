from dataclasses import dataclass
from typing import Generic, Never, TypeVar, final

from typing_extensions import TypeForm

from effecton.effect import Effect, EffectonError, ProvideRequirement

# Old-style TypeVars declare the variance ty cannot infer across the
# Effect ↔ ProvideBinder reference cycle; see the ty inference notes in
# AGENTS.md.
A = TypeVar("A", covariant=True)
E = TypeVar("E", bound=EffectonError, covariant=True)
R = TypeVar("R", covariant=True)
T = TypeVar("T")


@final
@dataclass(frozen=True)
class ProvideBinder(Generic[A, E, R, T]):  # noqa: UP046
    """One step of ``effect.provide(T)(impl)``: T is bound, impl pending.

    Calling it subtracts T from the effect's R and returns the effect
    with the remaining requirements.
    """

    effect: Effect[A, E, R]
    requirement_type: TypeForm[T]

    def __call__[A2, E2: EffectonError, R2 = Never](
        self: ProvideBinder[A2, E2, T | R2, T], impl: T
    ) -> Effect[A2, E2, R2]:
        return ProvideRequirement(
            first=self.effect,
            requirement_type=self.requirement_type,
            requirement_impl=impl,
        )
