from dataclasses import dataclass
from typing import Literal, Never, Protocol, assert_type, final, runtime_checkable

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


needs_two = E.require(Db).flat_map(
    lambda db: E.require(Logger).map(lambda logger: (db, logger))
)
needs_three = needs_two.flat_map(
    lambda pair: E.require(Cache).map(lambda cache: (*pair, cache))
)

# --- provide: subtracts one requirement from R per call ---

# Providing the only requirement yields a runnable effect (R = Never).
runnable_one = E.require(Db).provide(Db)(Db("postgres://x"))
assert_type(runnable_one, E.Effect[Db])
assert_type(E.run_sync(runnable_one), E.Succeeded[Db] | E.Failure)

# Partial provision is a real subtraction: the remainder stays in R and
# the half-provided effect is an ordinary value.
partially_provided = needs_two.provide(Db)(Db("postgres://x"))
assert_type(partially_provided, E.Effect[tuple[Db, Logger], Never, Logger])
runnable_two = partially_provided.provide(Logger)(Logger("info"))
assert_type(runnable_two, E.Effect[tuple[Db, Logger]])

# A chain subtracts one member at a time down to Never, in any order.
runnable_three = (
    needs_three.provide(Db)(Db("postgres://x"))
    .provide(Logger)(Logger("info"))
    .provide(Cache)(Cache(1))
)
assert_type(runnable_three, E.Effect[tuple[Db, Logger, Cache]])
assert_type(
    E.run_sync(runnable_three), E.Succeeded[tuple[Db, Logger, Cache]] | E.Failure
)
reordered = (
    needs_three.provide(Cache)(Cache(1))
    .provide(Db)(Db("postgres://x"))
    .provide(Logger)(Logger("info"))
)
assert_type(reordered, E.Effect[tuple[Db, Logger, Cache]])

# The value and error channels ride through provide untouched.
failing = E.require(Db).flat_map(
    lambda db: E.fail(ParseError(db.url)) if db.url else E.success(1)
)
assert_type(failing.provide(Db)(Db("pg")), E.Effect[Literal[1], ParseError])

# Subtracting a non-Scope member leaves Scope in place for scoped().
scope_and_db = E.add_finalizer(E.success(None)).flat_map(lambda _: E.require(Db))
assert_type(scope_and_db, E.Effect[Db, Never, E.Scope | Db])
assert_type(scope_and_db.provide(Db)(Db("pg")), E.Effect[Db, Never, E.Scope])

# --- provide: over-provision is a well-typed no-op ---

# R's covariance means an absent member subtracts nothing, so it cannot
# be rejected (that would need type negation) and R stays unchanged.
assert_type(
    runnable_three.provide(Db)(Db("postgres://x")), E.Effect[tuple[Db, Logger, Cache]]
)
assert_type(E.require(Db).provide(Cache)(Cache(1)), E.Effect[Db, Never, Db])

# Providing the same requirement twice: the second call is a no-op in R.
assert_type(
    E.require(Db).provide(Db)(Db("first")).provide(Db)(Db("second")),
    E.Effect[Db],
)

# --- provide: protocol classes work as requirement keys ---


@runtime_checkable
class Greeter(Protocol):
    def greet(self) -> str: ...


class LiveGreeter(Greeter):
    def greet(self) -> str:
        return "hi"


assert_type(E.require(Greeter).provide(Greeter)(LiveGreeter()), E.Effect[Greeter])

# --- provide: negative tests ---


# An effect with unmet requirements is not runnable, including a
# partially provided one.
# Type-checked only; never called.
def _unprovided_is_not_runnable() -> None:
    E.run_sync(needs_three)  # ty: ignore[invalid-argument-type]
    E.run_sync(partially_provided)  # ty: ignore[invalid-argument-type]


# The implementation must match the bound requirement type: provide is
# curried so the key type is pinned before the implementation is seen.
E.require(Db).provide(Db)(Logger("info"))  # ty: ignore[invalid-argument-type]
E.require(Db).provide(Db)("postgres://x")  # ty: ignore[invalid-argument-type]
needs_two.provide(Db)(Db("postgres://x")).provide(Logger)(
    Cache(1)  # ty: ignore[invalid-argument-type]
)


@dataclass(frozen=True)
class PgDb(Db):
    pass


# A subclass implementation satisfies the bound key; the key type wins.
assert_type(E.require(Db).provide(Db)(PgDb("pg")), E.Effect[Db])


# --- KNOWN LIMITATION: requirement lookup uses the exact type at
# runtime, but R's covariance lets a provided supertype cover a subtype
# requirement statically. The type checker accepts the following program
# (PgDb is assignable to Db), yet running it dies with MissingRequirement(PgDb):
# the env holds the Db key and require(PgDb) looks up PgDb. Use exact
# types as requirement keys.
# Type-checked only; never called.
def _supertype_provision_typechecks_but_dies() -> None:
    assert_type(
        E.require(PgDb).provide(Db)(Db("postgres://x")),
        E.Effect[PgDb],
    )
