from dataclasses import dataclass
from typing import Any, Literal, Never, assert_never, final

from effecton.effect import Cause, Die, EffectonError, Fail, Interrupt


@final
@dataclass(frozen=True)
class Succeeded[A]:
    value: A
    kind: Literal["succeeded"] = "succeeded"


@final
@dataclass(frozen=True)
class Failure[E: EffectonError = Never]:
    cause: Cause[E]
    kind: Literal["failure"] = "failure"


type Exit[A, E: EffectonError = Never] = Succeeded[A] | Failure[E]


@final
@dataclass(frozen=True)
class UnhandledDefect(Exception):
    """Raised by a throwing runner for a defect that is not an exception.

    Exception defects are re-raised as they are; any other value, such
    as the argument of ``die("boom")``, is wrapped here so it can still
    propagate through Python's exception machinery.
    """

    defect: Any

    def __str__(self) -> str:
        return f"Unhandled defect: {self.defect!r}"


def unwrap[A, E: EffectonError](exit: Exit[A, E]) -> A:
    """Return the value of a successful Exit, or raise its cause.

    A typed failure raises the error itself, a defect re-raises the
    exception (or UnhandledDefect for a non-exception value) and an
    interruption re-raises the exception that signalled it.
    """
    match exit:
        case Succeeded(value):
            return value
        case Failure(cause):
            match cause:
                case Fail(error):
                    raise error
                case Die(defect):
                    if isinstance(defect, BaseException):
                        raise defect
                    raise UnhandledDefect(defect)
                case Interrupt(exception):
                    raise exception
                case _:
                    assert_never(cause)
        case _:
            assert_never(exit)
