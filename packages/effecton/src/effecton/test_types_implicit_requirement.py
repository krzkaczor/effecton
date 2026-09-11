"""Type-level pins for implicit requirements. Nothing here runs: ty checks
the function bodies and pytest never calls them."""

from dataclasses import dataclass
from typing import Literal, Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class Greeting(E.ImplicitRequirement):
    text: str

    @classmethod
    def default(cls) -> Greeting:
        return Greeting("hello")


@dataclass(frozen=True)
class Db:
    url: str


def _require_implicit_keeps_r_never_so_the_effect_is_runnable_bare() -> None:
    assert_type(E.require_implicit(Greeting), E.Effect[Greeting])
    assert_type(
        E.run_sync_exit(E.require_implicit(Greeting)), E.Succeeded[Greeting] | E.Failure
    )

    # Mixing with a plain requirement: only the plain one enters R.
    mixed = E.require_implicit(Greeting).flat_map(
        lambda g: E.require(Db).map(lambda db: (g, db))
    )
    assert_type(mixed, E.Effect[tuple[Greeting, Db], Never, Db])

    # An implicit finalizer adds nothing to R; a plain one still does. This
    # pins why require_implicit is a separate function: overloads on require
    # resolved through the implicit branch here and silently dropped Db.
    assert_type(
        E.success(1).on_exit(E.require_implicit(Greeting)), E.Effect[Literal[1]]
    )
    assert_type(E.success(1).on_exit(E.require(Db)), E.Effect[Literal[1], Never, Db])


def _require_implicit_negative() -> None:
    # A class without a default() classmethod is not an implicit requirement.
    E.require_implicit(Db)  # ty: ignore[invalid-argument-type]

    # Explicitly extending the protocol makes a missing default() a static
    # error at the point of use: the class stays abstract until implemented.
    # ty does not flag instantiation of a class with abstract members yet;
    # this line starts failing under a stricter ty, which is the signal to
    # restore the negative assertion (mypy flagged it as [abstract]).
    class MissingDefault(E.ImplicitRequirement):
        pass

    MissingDefault()

    # Plain require on an implicit class still demands provision; the
    # default fallback is opt-in through require_implicit.
    E.run_sync_exit(E.require(Greeting))  # ty: ignore[invalid-argument-type]


def _provide_implicit_preserves_all_three_channels() -> None:
    mixed = E.require_implicit(Greeting).flat_map(
        lambda g: E.require(Db).map(lambda db: (g, db))
    )
    assert_type(
        E.provide_implicit(E.require_implicit(Greeting), Greeting("hi")),
        E.Effect[Greeting],
    )
    assert_type(
        E.provide_implicit(mixed, Greeting("hi")),
        E.Effect[tuple[Greeting, Db], Never, Db],
    )

    # Only implicit-requirement values can be provided this way.
    E.provide_implicit(E.success(1), Db("pg"))  # ty: ignore[invalid-argument-type]

    # Implicit overrides ride along with plain provisions: the Greeting
    # provision is an over-provision no-op in R (implicit requirements never
    # enter it) but still overrides the default at runtime.
    runnable = mixed.provide(Db)(Db("postgres://x")).provide(Greeting)(
        Greeting("provided")
    )
    assert_type(runnable, E.Effect[tuple[Greeting, Db]])
