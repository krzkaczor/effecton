from typing import Any, Protocol, Self, cast, runtime_checkable

from effecton.effect import Effect, EffectonError, ProvideRequirement, Require


@runtime_checkable
class ImplicitRequirement(Protocol):
    """A requirement that carries its own default value.

    The default is computed once per process and shared by every later
    interpretation, so it must be an immutable value.
    """

    @classmethod
    def default(cls) -> Self: ...


# Implicits are lazily initialized. Once initialized, the default is
# shared across all run_sync executions.
_implicit_defaults: dict[type[ImplicitRequirement], Any] = {}


def resolve_default[S: ImplicitRequirement](requirement_type: type[S]) -> S:
    if requirement_type not in _implicit_defaults:
        _implicit_defaults[requirement_type] = requirement_type.default()
    return cast("S", _implicit_defaults[requirement_type])


def require_implicit[S: ImplicitRequirement](
    requirement_type: type[S],
) -> Effect[S]:
    return cast("Effect[S]", Require(requirement_type=requirement_type))


def provide_implicit[S: ImplicitRequirement, A, E: EffectonError, R](
    effect: Effect[A, E, R], value: S
) -> Effect[A, E, R]:
    return ProvideRequirement(
        first=effect, requirement_type=type(value), requirement_impl=value
    )
