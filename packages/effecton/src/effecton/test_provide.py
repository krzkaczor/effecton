from dataclasses import dataclass
from typing import Protocol, final, runtime_checkable

import effecton as E


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


@dataclass(frozen=True)
class Db:
    url: str


@dataclass(frozen=True)
class PgDb(Db):
    pass


def test_provide_single_requirement():
    p = E.require(str).map(lambda s: s.upper())

    provided = p.provide(str)("Kris")

    assert E.run_sync(provided) == E.Succeeded("KRIS")


def test_provide_two_requirements_in_a_chain():
    r1 = E.require(str).map(lambda s: s.upper())
    r2 = E.require(int).map(lambda i: i * 10)
    p = r1.flat_map(lambda s: r2.map(lambda i: f"{s}{i}!"))

    provided = p.provide(str)("Kris").provide(int)(5)

    assert E.run_sync(provided) == E.Succeeded("KRIS50!")


def test_provide_three_requirements_in_a_chain():
    r1 = E.require(str).map(lambda s: s.upper())
    r2 = E.require(int).map(lambda i: i * 10)
    r3 = E.require(float).map(lambda f: f / 2)
    p = r1.flat_map(lambda s: r2.flat_map(lambda i: r3.map(lambda f: f"{s}{i}|{f}!")))

    provided = p.provide(str)("Kris").provide(int)(5).provide(float)(1.0)

    assert E.run_sync(provided) == E.Succeeded("KRIS50|0.5!")


def test_provide_order_does_not_matter():
    p = E.require(str).flat_map(lambda s: E.require(int).map(lambda i: (s, i)))

    provided = p.provide(int)(5).provide(str)("Kris")

    assert E.run_sync(provided) == E.Succeeded(("Kris", 5))


def test_provide_is_scoped_to_the_wrapped_effect():
    scoped = E.require(str).provide(str)("inner")
    p = scoped.flat_map(
        lambda first: E.require(str).map(lambda second: (first, second))
    )

    provided = p.provide(str)("outer")

    assert E.run_sync(provided) == E.Succeeded(("inner", "outer"))


def test_innermost_provide_wins_for_the_same_key():
    p = E.require(str).provide(str)("innermost").provide(str)("outermost")

    assert E.run_sync(p) == E.Succeeded("innermost")


def test_inner_provide_shadows_outer_within_its_extent():
    inner = E.require(str).provide(str)("inner")
    p = E.require(str).flat_map(lambda outer: inner.map(lambda i: (outer, i)))

    provided = p.provide(str)("outer")

    assert E.run_sync(provided) == E.Succeeded(("outer", "inner"))


def test_provide_env_unwinds_on_typed_failure():
    failing_scoped = (
        E.require(str)
        .flat_map(lambda _: E.fail(OopsError("boom")))
        .provide(str)("inner")
    )
    p = failing_scoped.catch_all(lambda _: E.require(str))

    provided = p.provide(str)("outer")

    assert E.run_sync(provided) == E.Succeeded("outer")


def test_over_provision_is_a_harmless_no_op():
    p = E.success(42).provide(str)("unused")

    assert E.run_sync(p) == E.Succeeded(42)


def test_provided_effects_are_reusable_values():
    calls: list[str] = []
    p = E.require(str).map(lambda s: (calls.append(s), s)[1]).provide(str)("x")

    assert E.run_sync(p) == E.Succeeded("x")
    assert E.run_sync(p) == E.Succeeded("x")
    assert calls == ["x", "x"]


def test_subclass_implementation_satisfies_the_base_key():
    p = E.require(Db).map(lambda db: db.url)

    provided = p.provide(Db)(PgDb("pg"))

    assert E.run_sync(provided) == E.Succeeded("pg")


def test_requirement_lookup_uses_the_exact_key_type():
    # Runtime counterpart of the KNOWN LIMITATION pinned in
    # test_types_provide.py: providing the base class statically covers
    # a subclass requirement, but the lookup misses at runtime.
    p = E.require(PgDb).provide(Db)(Db("pg"))

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect=E.MissingRequirement(PgDb)))


def test_missing_requirement_dies():
    # Only reachable outside the typed API (pinned as a type error here).
    result = E.run_sync(E.require(str))  # ty: ignore[invalid-argument-type]

    assert result == E.Failure(cause=E.Die(defect=E.MissingRequirement(str)))


@runtime_checkable
class Greeter(Protocol):
    def greet(self) -> str: ...


class LiveGreeter(Greeter):
    def greet(self) -> str:
        return "hi"


def test_protocol_class_as_requirement_key():
    p = E.require(Greeter).flat_map(lambda g: E.sync(g.greet))

    provided = p.provide(Greeter)(LiveGreeter())

    assert E.run_sync(provided) == E.Succeeded("hi")
