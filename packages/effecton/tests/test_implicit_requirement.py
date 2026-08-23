from dataclasses import dataclass
from typing import Any, cast, final

import effecton as E


@final
@dataclass(frozen=True)
class Greeting(E.ImplicitRequirement):
    text: str

    @classmethod
    def default(cls) -> Greeting:
        return Greeting("hello")


def test_falls_back_to_default_when_nothing_is_provided():
    assert E.run_sync(E.require_implicit(Greeting)) == E.Succeeded(
        value=Greeting("hello")
    )


def test_default_is_memoized_across_runs():
    calls = []

    @final
    @dataclass(frozen=True)
    class Counted(E.ImplicitRequirement):
        n: int

        @classmethod
        def default(cls) -> Counted:
            calls.append(1)
            return Counted(0)

    assert E.run_sync(E.require_implicit(Counted)) == E.Succeeded(value=Counted(0))
    assert E.run_sync(E.require_implicit(Counted)) == E.Succeeded(value=Counted(0))

    assert len(calls) == 1


def test_provide_implicit_overrides_the_default():
    program = E.provide_implicit(E.require_implicit(Greeting), Greeting("hi"))

    assert E.run_sync(program) == E.Succeeded(value=Greeting("hi"))


def test_override_is_scoped_to_the_wrapped_effect():
    overridden = E.provide_implicit(E.require_implicit(Greeting), Greeting("hi"))
    after = overridden.flat_map(
        lambda first: E.require_implicit(Greeting).map(lambda second: (first, second))
    )

    assert E.run_sync(after) == E.Succeeded(value=(Greeting("hi"), Greeting("hello")))


def test_nested_overrides_shadow():
    inner = E.provide_implicit(E.require_implicit(Greeting), Greeting("inner"))
    outer = E.provide_implicit(
        inner.flat_map(
            lambda i: E.require_implicit(Greeting).map(lambda o: (i, o)),
        ),
        Greeting("outer"),
    )

    assert E.run_sync(outer) == E.Succeeded(
        value=(Greeting("inner"), Greeting("outer"))
    )


def test_override_via_requirement_provider():
    program = (
        E.RequirementProvider()
        .and_provide(Greeting)(Greeting("provided"))
        .apply(E.require_implicit(Greeting))
    )

    assert E.run_sync(program) == E.Succeeded(value=Greeting("provided"))


def test_raising_default_is_a_defect():
    boom = ValueError("boom")

    @final
    @dataclass(frozen=True)
    class Broken(E.ImplicitRequirement):
        @classmethod
        def default(cls) -> Broken:
            raise boom

    assert E.run_sync(E.require_implicit(Broken)) == E.Failure(cause=E.Die(defect=boom))


def test_requiring_the_protocol_itself_is_a_missing_requirement():
    # The protocol class structurally matches itself, but its stub
    # default() returns None; the interpreter refuses it instead of
    # caching garbage.
    protocol_as_key = cast(Any, E.ImplicitRequirement)
    assert E.run_sync(E.require(protocol_as_key)) == E.Failure(
        cause=E.Die(defect=E.MissingRequirement(E.ImplicitRequirement))
    )


def test_plain_missing_requirement_still_dies():
    @dataclass(frozen=True)
    class Db:
        url: str

    assert E.run_sync(cast(Any, E.require(Db))) == E.Failure(
        cause=E.Die(defect=E.MissingRequirement(Db))
    )
