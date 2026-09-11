"""Type-level pins for Scope. Nothing here runs: ty checks the function
bodies and pytest never calls them."""

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


@dataclass(frozen=True)
class Logger:
    level: str


@dataclass(frozen=True)
class Cache:
    size: int


def parse(s: str) -> E.Effect[int, ParseError]:
    try:
        return E.success(int(s))
    except ValueError:
        return E.fail(ParseError(s))


def _scoped_discharges_scope_and_other_requirements_pass_through() -> None:
    needs_scope = E.add_finalizer(E.success(None)).flat_map(lambda _: parse("1"))
    assert_type(needs_scope, E.Effect[int, ParseError, E.Scope])
    assert_type(E.scoped(needs_scope), E.Effect[int, ParseError])
    assert_type(
        E.run_sync_exit(E.scoped(needs_scope)), E.Succeeded[int] | E.Failure[ParseError]
    )

    needs_scope_and_db = needs_scope.flat_map(lambda n: E.require(Db).map(lambda _: n))
    assert_type(needs_scope_and_db, E.Effect[int, ParseError, E.Scope | Db])
    assert_type(E.scoped(needs_scope_and_db), E.Effect[int, ParseError, Db])

    # A leftover non-Scope requirement keeps the effect unrunnable.
    E.run_sync_exit(E.scoped(needs_scope_and_db))  # ty: ignore[invalid-argument-type]

    # With more than one requirement left after Scope, scoped() keeps the
    # leftover union intact (mypy used to join Db, Logger, Cache to object,
    # which forced the retired and_scoped chain for this case).
    needs_three = (
        E.require(Db)
        .flat_map(lambda db: E.require(Logger).map(lambda logger: (db, logger)))
        .flat_map(lambda pair: E.require(Cache).map(lambda cache: (*pair, cache)))
    )
    needs_scope_and_three = E.add_finalizer(E.success(None)).flat_map(
        lambda _: needs_three
    )
    assert_type(
        needs_scope_and_three,
        E.Effect[tuple[Db, Logger, Cache], Never, E.Scope | Db | Logger | Cache],
    )
    assert_type(
        E.scoped(needs_scope_and_three),
        E.Effect[tuple[Db, Logger, Cache], Never, Db | Logger | Cache],
    )


def _scoped_method_composes_with_provide_chains() -> None:
    needs_scope = E.add_finalizer(E.success(None)).flat_map(lambda _: parse("1"))
    needs_three = (
        E.require(Db)
        .flat_map(lambda db: E.require(Logger).map(lambda logger: (db, logger)))
        .flat_map(lambda pair: E.require(Cache).map(lambda cache: (*pair, cache)))
    )
    needs_scope_and_three = E.add_finalizer(E.success(None)).flat_map(
        lambda _: needs_three
    )

    # .scoped() anywhere in a provide chain; remaining provides continue.
    runnable_scoped_three = (
        needs_scope_and_three.provide(Db)(Db("postgres://x"))
        .provide(Logger)(Logger("info"))
        .scoped()
        .provide(Cache)(Cache(1))
    )
    assert_type(runnable_scoped_three, E.Effect[tuple[Db, Logger, Cache]])
    assert_type(
        E.run_sync_exit(runnable_scoped_three),
        E.Succeeded[tuple[Db, Logger, Cache]] | E.Failure,
    )

    # .scoped() as a chain terminal after full provision.
    assert_type(
        needs_scope_and_three.provide(Db)(Db("postgres://x"))
        .provide(Logger)(Logger("info"))
        .provide(Cache)(Cache(1))
        .scoped(),
        E.Effect[tuple[Db, Logger, Cache]],
    )

    # .scoped() on a Scope-only effect.
    assert_type(needs_scope.scoped(), E.Effect[int, ParseError])

    # .scoped() on an effect that never acquired a Scope requirement is a
    # well-typed no-op (covariance; the empty runtime scope is harmless), so
    # it can uniformly terminate any provide chain.
    assert_type(parse("1").scoped(), E.Effect[int, ParseError])

    # .scoped() leaves non-Scope requirements in place: still unrunnable.
    E.run_sync_exit(needs_scope_and_three.provide(Db)(Db("pg")).scoped())  # ty: ignore[invalid-argument-type]


def _acquire_and_release_lifetime_lives_in_the_scope_channel() -> None:
    resource = E.acquire_and_release(E.success(1), lambda _: E.success(None))
    assert_type(resource, E.Effect[Literal[1], Never, E.Scope])
    assert_type(E.scoped(resource), E.Effect[Literal[1]])

    # acquire's typed errors surface in E.
    failing_resource = E.acquire_and_release(parse("1"), lambda _: E.success(None))
    assert_type(failing_resource, E.Effect[int, ParseError, E.Scope])
    assert_type(E.scoped(failing_resource), E.Effect[int, ParseError])

    # acquire's own requirements union with Scope; provide + .scoped()
    # discharge both.
    db_resource = E.acquire_and_release(E.require(Db), lambda _: E.success(None))
    assert_type(db_resource, E.Effect[Db, Never, Db | E.Scope])
    assert_type(
        db_resource.provide(Db)(Db("postgres://x")).scoped(),
        E.Effect[Db],
    )


def _acquire_and_release_negative() -> None:
    # Unrunnable until a scope discharges the Scope requirement.
    E.run_sync_exit(E.acquire_and_release(E.success(1), lambda _: E.success(None)))  # ty: ignore[invalid-argument-type]

    # release cannot have a typed error channel.
    E.acquire_and_release(E.success(1), lambda _: E.fail(ParseError("x")))  # ty: ignore[invalid-argument-type]
