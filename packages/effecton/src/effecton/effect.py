from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Never, final

from typing_extensions import TypeForm

if TYPE_CHECKING:
    from effecton.provide import ProvideBinder
    from effecton.std.scope import Scope


@dataclass(frozen=True)
class EffectonError(Exception):
    def __str__(self) -> str:
        # The dataclass __init__ never fills Exception.args, so the
        # inherited __str__ renders every error as an empty string.
        return repr(self)


@final
@dataclass(frozen=True)
class Fail[E: EffectonError]:
    error: E


@final
@dataclass(frozen=True)
class Die:
    defect: Any


type Cause[E: EffectonError] = Fail[E] | Die


class Effect[A, E: EffectonError = Never, R = Never]:
    def flat_map[B, E2: EffectonError, R2](
        self, f: Callable[[A], Effect[B, E2, R2]]
    ) -> Effect[B, E | E2, R | R2]:
        return FlatMap(self, f)

    def map[B](self, f: Callable[[A], B]) -> Effect[B, E, R]:
        return self.flat_map(lambda a: Success(f(a)))

    def catch_all[B, E2: EffectonError, R2](
        self, f: Callable[[E], Effect[B, E2, R2]]
    ) -> Effect[A | B, E2, R | R2]:
        return OnFailure[A | B, E2, R | R2](self, f)

    def on_exit[R2](self, finalizer: Effect[Any, Never, R2]) -> Effect[A, E, R | R2]:
        return OnExit(self, finalizer)

    def provide[T](self, requirement_type: TypeForm[T]) -> ProvideBinder[A, E, R, T]:
        from effecton.provide import ProvideBinder

        return ProvideBinder(effect=self, requirement_type=requirement_type)

    def scoped[A2, E2: EffectonError, R2 = Never](
        self: Effect[A2, E2, Scope | R2],
    ) -> Effect[A2, E2, R2]:
        from effecton.std.scope import scoped

        return scoped(self)

    def __iter__(self) -> Generator[Effect[A, E, R], Any, A]:
        """Make ``x = yield from effect`` infer ``x`` as A inside @gen.

        A bare ``yield`` types as the generator's single send type (Any).
        ``yield from`` takes this method's return type parameter instead,
        so the value the interpreter sends back is typed per expression.
        """
        return (yield self)


@final
@dataclass(frozen=True)
class Success[A](Effect[A]):
    value: A
    kind: Literal["success"] = "success"


@final
@dataclass(frozen=True)
class Sync[A](Effect[A]):
    fn: Callable[[], A]
    kind: Literal["sync"] = "sync"


@final
@dataclass(frozen=True)
class FailCause[E: EffectonError](Effect[Never, E]):
    cause: Cause[E]
    kind: Literal["fail"] = "fail"


@final
@dataclass(frozen=True)
class FlatMap[B, E: EffectonError, R](Effect[B, E, R]):
    first: Effect[Any, Any, Any]
    and_then: Callable[[Any], Effect[B, E, R]]
    kind: Literal["flat_map"] = "flat_map"


@final
@dataclass(frozen=True)
class OnFailure[A, E: EffectonError, R](Effect[A, E, R]):
    first: Effect[A, Any, Any]
    handler: Callable[[Any], Effect[A, E, R]]
    kind: Literal["on_failure"] = "on_failure"


@final
@dataclass(frozen=True)
class Require[R](Effect[R, Never, R]):
    requirement_type: TypeForm[R]
    kind: Literal["require"] = "require"


@final
@dataclass(frozen=True)
class ProvideRequirement[A, E: EffectonError, R](Effect[A, E, R]):
    first: Effect[A, E, Any]
    requirement_type: TypeForm[Any]
    requirement_impl: Any
    kind: Literal["provide_requirement"] = "provide_requirement"


@final
@dataclass(frozen=True)
class OnExit[A, E: EffectonError, R](Effect[A, E, R]):
    first: Effect[Any, Any, Any]
    finalizer: Effect[Any, Any, Any]
    kind: Literal["on_exit"] = "on_exit"


Node = (
    Success[Any]
    | Sync[Any]
    | FailCause[Any]
    | FlatMap[Any, Any, Any]
    | OnFailure[Any, Any, Any]
    | Require[Any]
    | ProvideRequirement[Any, Any, Any]
    | OnExit[Any, Any, Any]
)


def success[A](value: A) -> Effect[A]:
    return Success(value)


def sync[A](fn: Callable[[], A]) -> Effect[A]:
    return Sync(fn)


def fail[E: EffectonError](error: E) -> Effect[Never, E]:
    return FailCause(cause=Fail(error=error))


def die(defect: Any) -> Effect[Never]:  # noqa: ANN401
    return FailCause(cause=Die(defect=defect))


def require[R](requirement_type: TypeForm[R]) -> Effect[R, Never, R]:
    return Require(requirement_type=requirement_type)
