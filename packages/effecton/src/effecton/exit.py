from dataclasses import dataclass
from typing import Literal, Never, final

from effecton.effect import Cause, EffectonError


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
