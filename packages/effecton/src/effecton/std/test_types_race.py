from dataclasses import dataclass
from typing import Literal, Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class LeftError(E.EffectonError):
    def __str__(self) -> str:
        return "Left failed"


@final
@dataclass(frozen=True)
class RightError(E.EffectonError):
    def __str__(self) -> str:
        return "Right failed"


assert_type(E.race_first(E.success(1), E.success("x")), E.Effect[Literal[1, "x"]])
assert_type(
    E.race_first(E.fail(LeftError()), E.fail(RightError())),
    E.Effect[Never, LeftError | RightError],
)
assert_type(
    E.race_first(E.require(str), E.require(int)), E.Effect[str | int, Never, str | int]
)


def check_combined(
    left: E.Effect[int, LeftError, str], right: E.Effect[bytes, RightError, float]
):
    raced = E.race_first(left, right)
    assert_type(raced, E.Effect[int | bytes, LeftError | RightError, str | float])
    assert_type(
        raced.catch(LeftError)(lambda _: E.success(0)),
        E.Effect[int | bytes, RightError, str | float],
    )
    assert_type(
        raced.provide(str)("provided").provide(float)(1.0),
        E.Effect[int | bytes, LeftError | RightError],
    )
    E.run_async(raced)  # ty: ignore[invalid-argument-type]
    E.run_async(raced.provide(str)("provided"))  # ty: ignore[invalid-argument-type]


E.race_first(1, E.success(2))  # ty: ignore[invalid-argument-type]
E.race_first(E.success(1), lambda: E.success(2))  # ty: ignore[invalid-argument-type]
