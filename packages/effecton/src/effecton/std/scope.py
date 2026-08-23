from collections.abc import Callable
from dataclasses import dataclass, field
from functools import reduce
from typing import Any, Never, final

from effecton.effect import Effect, EffectonError, ProvideRequirement, require, success
from effecton.suspend import suspend


@final
@dataclass(frozen=True)
class Scope:
    _finalizers: list[Effect[Any]] = field(default_factory=list)

    def add_finalizer(self, finalizer: Effect[Any]) -> None:
        self._finalizers.append(finalizer)

    @suspend
    def close(self) -> Effect[None]:
        # Draining makes a second close a no-op; folding with on_exit
        # keeps a dying finalizer from skipping earlier-registered ones.
        finalizers = list(self._finalizers)
        self._finalizers.clear()
        return reduce(
            lambda acc, f: acc.on_exit(f),
            reversed(finalizers),
            success(None),
        )


def add_finalizer(finalizer: Effect[Any]) -> Effect[None, Never, Scope]:
    return require(Scope).map(lambda s: s.add_finalizer(finalizer))


@suspend
def scoped[A, E: EffectonError, R = Never](
    effect: Effect[A, E, Scope | R],
) -> Effect[A, E, R]:
    scope = Scope()

    return ProvideRequirement(
        first=effect, requirement_type=Scope, requirement_impl=scope
    ).on_exit(scope.close())


def acquire_and_release[A, E: EffectonError, R](
    acquire: Effect[A, E, R], release: Callable[[A], Effect[Any]]
) -> Effect[A, E, R | Scope]:
    """Acquire a resource whose release the enclosing scope guarantees.

    The release is registered only after acquire succeeds; a failed or
    dying acquire registers nothing. suspend defers the release effect's
    construction, so a release function that raises does so at close time
    as a finalizer defect that cannot skip other finalizers.
    """
    return acquire.flat_map(
        lambda a: add_finalizer(suspend(lambda: release(a))).map(lambda _: a)
    )
