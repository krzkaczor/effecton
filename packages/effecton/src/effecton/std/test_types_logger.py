from dataclasses import dataclass
from typing import Literal, Never, assert_type

import effecton as E


@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


@dataclass(frozen=True)
class Db:
    url: str


# --- log effects require nothing: R is Never, runnable bare ---

assert_type(E.log_info("x"), E.Effect[None])
assert_type(E.log("x", 1, True), E.Effect[None])
assert_type(E.run_sync(E.log("x")), E.Succeeded[None] | E.Failure)

# Mixing a log with a plain requirement leaves only the plain one in R.
_mixed = E.log_info("hi").flat_map(lambda _: E.require(Db))
assert_type(_mixed, E.Effect[Db, Never, Db])

# --- annotate_logs preserves all three channels ---

_effectful = E.require(Db).flat_map(
    lambda db: E.fail(ParseError(db.url)) if db.url else E.success(1)
)
assert_type(
    E.annotate_logs(_effectful, user_id=1),
    E.Effect[Literal[1], ParseError, Db],
)
assert_type(E.annotate_logs(E.log_info("x"), a="b"), E.Effect[None])

# --- Severity excludes the ALL/NONE threshold sentinels ---

# A message cannot be logged at the sentinels...
E.CurrentLogLevel(E.LogLevel.ALL)  # ty: ignore[invalid-argument-type]
E.CurrentLogLevel(E.LogLevel.NONE)  # ty: ignore[invalid-argument-type]

# ...but the minimum threshold accepts them.
assert_type(E.MinimumLogLevel(E.LogLevel.ALL), E.MinimumLogLevel)
assert_type(E.MinimumLogLevel(E.LogLevel.NONE), E.MinimumLogLevel)
