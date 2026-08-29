from dataclasses import dataclass
from typing import Literal, Never, assert_type

import effecton as E


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


needs_three = (
    E.require(Db)
    .flat_map(lambda db: E.require(Logger).map(lambda logger: (db, logger)))
    .flat_map(lambda pair: E.require(Cache).map(lambda cache: (*pair, cache)))
)


# --- scoped: discharges Scope, other requirements pass through ---

_needs_scope = E.add_finalizer(E.success(None)).flat_map(lambda _: parse("1"))
assert_type(_needs_scope, E.Effect[int, ParseError, E.Scope])
assert_type(E.scoped(_needs_scope), E.Effect[int, ParseError])
assert_type(
    E.run_sync(E.scoped(_needs_scope)), E.Succeeded[int] | E.Failure[ParseError]
)

_needs_scope_and_db = _needs_scope.flat_map(lambda n: E.require(Db).map(lambda _: n))
assert_type(_needs_scope_and_db, E.Effect[int, ParseError, E.Scope | Db])
assert_type(E.scoped(_needs_scope_and_db), E.Effect[int, ParseError, Db])

# With more than one requirement left after Scope, scoped() keeps the
# leftover union intact (mypy used to join Db, Logger, Cache to object,
# which forced the retired and_scoped chain for this case).
_needs_scope_and_three = E.add_finalizer(E.success(None)).flat_map(
    lambda _: needs_three
)
assert_type(
    _needs_scope_and_three,
    E.Effect[tuple[Db, Logger, Cache], Never, E.Scope | Db | Logger | Cache],
)
assert_type(
    E.scoped(_needs_scope_and_three),
    E.Effect[tuple[Db, Logger, Cache], Never, Db | Logger | Cache],
)

# --- the .scoped() method composes with .provide() chains ---

# .scoped() anywhere in a provide chain; remaining provides continue.
_runnable_scoped_three = (
    _needs_scope_and_three.provide(Db)(Db("postgres://x"))
    .provide(Logger)(Logger("info"))
    .scoped()
    .provide(Cache)(Cache(1))
)
assert_type(_runnable_scoped_three, E.Effect[tuple[Db, Logger, Cache]])
assert_type(
    E.run_sync(_runnable_scoped_three),
    E.Succeeded[tuple[Db, Logger, Cache]] | E.Failure,
)

# .scoped() as a chain terminal after full provision.
assert_type(
    _needs_scope_and_three.provide(Db)(Db("postgres://x"))
    .provide(Logger)(Logger("info"))
    .provide(Cache)(Cache(1))
    .scoped(),
    E.Effect[tuple[Db, Logger, Cache]],
)

# .scoped() on a Scope-only effect.
assert_type(_needs_scope.scoped(), E.Effect[int, ParseError])

# .scoped() on an effect that never acquired a Scope requirement is a
# well-typed no-op (covariance; the empty runtime scope is harmless), so
# it can uniformly terminate any provide chain.
assert_type(parse("1").scoped(), E.Effect[int, ParseError])


# --- .scoped() method: negative tests ---


# .scoped() leaves non-Scope requirements in place: still unrunnable.
# Type-checked only; never called.
def _method_scoped_leftover_is_not_runnable() -> None:
    E.run_sync(_needs_scope_and_three.provide(Db)(Db("pg")).scoped())  # ty: ignore[invalid-argument-type]


# --- scoped: negative tests ---


# A leftover non-Scope requirement keeps the effect unrunnable.
# Type-checked only; never called.
def _scoped_leftover_requirement_is_not_runnable() -> None:
    E.run_sync(E.scoped(_needs_scope_and_db))  # ty: ignore[invalid-argument-type]


# --- acquire_and_release: the resource's lifetime lives in the Scope channel ---

_resource = E.acquire_and_release(E.success(1), lambda _: E.success(None))
assert_type(_resource, E.Effect[Literal[1], Never, E.Scope])
assert_type(E.scoped(_resource), E.Effect[Literal[1]])

# acquire's typed errors surface in E.
_failing_resource = E.acquire_and_release(parse("1"), lambda _: E.success(None))
assert_type(_failing_resource, E.Effect[int, ParseError, E.Scope])
assert_type(E.scoped(_failing_resource), E.Effect[int, ParseError])

# acquire's own requirements union with Scope; provide + .scoped()
# discharge both.
_db_resource = E.acquire_and_release(E.require(Db), lambda _: E.success(None))
assert_type(_db_resource, E.Effect[Db, Never, Db | E.Scope])
assert_type(
    _db_resource.provide(Db)(Db("postgres://x")).scoped(),
    E.Effect[Db],
)


# --- acquire_and_release: negative tests ---


# Unrunnable until a scope discharges the Scope requirement.
# Type-checked only; never called.
def _unscoped_resource_is_not_runnable() -> None:
    E.run_sync(E.acquire_and_release(E.success(1), lambda _: E.success(None)))  # ty: ignore[invalid-argument-type]


# release cannot have a typed error channel.
E.acquire_and_release(E.success(1), lambda _: E.fail(ParseError("x")))  # ty: ignore[invalid-argument-type]
