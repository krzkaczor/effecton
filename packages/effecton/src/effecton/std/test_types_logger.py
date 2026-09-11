"""Type-level pins for the Logger service. Nothing here runs: ty checks the
function bodies and pytest never calls them."""

from dataclasses import dataclass
from typing import Literal, Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


@dataclass(frozen=True)
class Db:
    url: str


def _log_effects_require_nothing_so_r_is_never() -> None:
    assert_type(E.log_info("x"), E.Effect[None])
    assert_type(E.log("x", 1, True), E.Effect[None])
    assert_type(E.run_sync_exit(E.log("x")), E.Succeeded[None] | E.Failure)

    # Mixing a log with a plain requirement leaves only the plain one in R.
    mixed = E.log_info("hi").flat_map(lambda _: E.require(Db))
    assert_type(mixed, E.Effect[Db, Never, Db])


def _annotate_logs_preserves_all_three_channels() -> None:
    effectful = E.require(Db).flat_map(
        lambda db: E.fail(ParseError(db.url)) if db.url else E.success(1)
    )
    assert_type(
        E.annotate_logs(effectful, user_id=1),
        E.Effect[Literal[1], ParseError, Db],
    )
    assert_type(E.annotate_logs(E.log_info("x"), a="b"), E.Effect[None])


def _severity_excludes_the_all_and_none_threshold_sentinels() -> None:
    # A message cannot be logged at the sentinels...
    E.CurrentLogLevel(E.LogLevel.ALL)  # ty: ignore[invalid-argument-type]
    E.CurrentLogLevel(E.LogLevel.NONE)  # ty: ignore[invalid-argument-type]

    # ...but the minimum threshold accepts them.
    assert_type(E.MinimumLogLevel(E.LogLevel.ALL), E.MinimumLogLevel)
    assert_type(E.MinimumLogLevel(E.LogLevel.NONE), E.MinimumLogLevel)
