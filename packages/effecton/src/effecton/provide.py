from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Never, cast, final

from typing_extensions import TypeForm

from effecton.effect import Effect, EffectonError, ProvideRequirement

if TYPE_CHECKING:
    from effecton.std.scope import Scope


@final
@dataclass(frozen=True)
class RequirementProvider[R = Never]:
    """Accumulates provided requirements, then discharges them in one apply.

    Type-checker limitations dictate this design: all requirements must
    be provided at once; one-at-a-time provision would need R-union
    subtraction, which inference does not solve reliably (mypy collapsed
    the remainder to object).
    """

    _links: tuple[tuple[TypeForm[Any], Any], ...] = ()

    def and_provide[R2](
        self, requirement_type: TypeForm[R2]
    ) -> ChainedRequirementBinder[R, R2]:
        return ChainedRequirementBinder(requirement_type=requirement_type, _rest=self)

    def and_scoped[A, E: EffectonError](
        self, effect: Effect[A, E, Scope | R]
    ) -> Effect[A, E]:
        """Discharge the chain plus a Scope created fresh per interpretation."""
        from effecton.std.scope import scoped

        return self.apply(scoped(effect))

    def apply[A, E: EffectonError](self, effect: Effect[A, E, R]) -> Effect[A, E]:
        result: Effect[A, E, Any] = effect
        for requirement_type, requirement_impl in self._links:
            result = ProvideRequirement(
                first=result,
                requirement_type=requirement_type,
                requirement_impl=requirement_impl,
            )
        return cast("Effect[A, E]", result)


@final
@dataclass(frozen=True)
class ChainedRequirementBinder[R, R2]:
    requirement_type: TypeForm[R2]
    _rest: RequirementProvider[Any]

    def __call__(self, requirement_impl: R2) -> RequirementProvider[R | R2]:
        return cast(
            "RequirementProvider[R | R2]",
            RequirementProvider(
                _links=(*self._rest._links, (self.requirement_type, requirement_impl))
            ),
        )
