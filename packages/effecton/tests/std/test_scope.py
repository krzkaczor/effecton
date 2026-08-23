from dataclasses import dataclass
from typing import Never

import effecton as E


@dataclass(frozen=True)
class Db:
    url: str


@dataclass(frozen=True)
class BrokenError(E.EffectonError):
    msg: str


def track[T](actions: list[str], event: str, value: T) -> T:
    actions.append(event)
    return value


def test_scoped_happy_path():
    actions: list[str] = []
    program = E.add_finalizer(E.sync(lambda: actions.append("f1"))).flat_map(
        lambda _: E.add_finalizer(E.sync(lambda: actions.append("f2")))
    )

    r = E.run_sync(E.scoped(program))

    assert r == E.Succeeded(None)
    assert actions == ["f2", "f1"]


def test_finalizer_defect_does_not_skip_other_finalizers():
    actions: list[str] = []
    err = ValueError("boom")

    def explode() -> None:
        raise err

    program = (
        E.add_finalizer(E.sync(lambda: actions.append("f1")))
        .flat_map(lambda _: E.add_finalizer(E.sync(explode)))
        .flat_map(lambda _: E.add_finalizer(E.sync(lambda: actions.append("f3"))))
    )

    assert E.run_sync(E.scoped(program)) == E.Failure(cause=E.Die(defect=err))
    assert actions == ["f3", "f1"]


def test_scoped_programs_are_reusable_values():
    actions: list[str] = []
    program = E.add_finalizer(E.sync(lambda: actions.append("f")))
    p: E.Effect[None] = E.scoped(program)

    assert E.run_sync(p) == E.Succeeded(None)
    assert E.run_sync(p) == E.Succeeded(None)
    assert actions == ["f", "f"]


def test_close_is_idempotent():
    actions: list[str] = []
    scope = E.Scope()
    scope.add_finalizer(E.sync(lambda: actions.append("f")))

    close = scope.close()

    assert E.run_sync(close) == E.Succeeded(None)
    assert E.run_sync(close) == E.Succeeded(None)
    assert actions == ["f"]


def test_close_sees_finalizers_added_after_close_was_called():
    actions: list[str] = []
    scope = E.Scope()
    close = scope.close()
    scope.add_finalizer(E.sync(lambda: actions.append("late")))

    assert E.run_sync(close) == E.Succeeded(None)
    assert actions == ["late"]


def test_scoped_passes_other_requirements_through():
    actions: list[str] = []
    program = E.require(Db).flat_map(
        lambda db: E.add_finalizer(E.sync(lambda: actions.append(f"close {db.url}")))
    )
    runnable = (
        E.RequirementProvider().and_provide(Db)(Db("pg")).apply(E.scoped(program))
    )

    assert E.run_sync(runnable) == E.Succeeded(None)
    assert actions == ["close pg"]


def test_and_scoped_provides_scope_alongside_the_chain():
    actions: list[str] = []
    program = E.require(Db).flat_map(
        lambda db: E.add_finalizer(E.sync(lambda: actions.append(f"close {db.url}")))
    )
    p: E.Effect[None] = (
        E.RequirementProvider().and_provide(Db)(Db("pg")).and_scoped(program)
    )

    assert E.run_sync(p) == E.Succeeded(None)
    assert actions == ["close pg"]


def test_and_scoped_programs_are_reusable_values():
    actions: list[str] = []
    program = E.add_finalizer(E.sync(lambda: actions.append("f")))
    p: E.Effect[None] = E.RequirementProvider().and_scoped(program)

    assert E.run_sync(p) == E.Succeeded(None)
    assert E.run_sync(p) == E.Succeeded(None)
    assert actions == ["f", "f"]


def test_acquire_and_release_success():
    actions: list[str] = []
    resource = E.acquire_and_release(
        E.sync(lambda: track(actions, "open", "handle")),
        lambda h: E.sync(lambda: actions.append(f"close {h}")),
    )
    program = resource.flat_map(lambda h: E.sync(lambda: actions.append(f"use {h}")))

    assert E.run_sync(E.scoped(program)) == E.Succeeded(None)
    assert actions == ["open", "use handle", "close handle"]


def test_acquire_and_release_releases_in_lifo_order():
    actions: list[str] = []

    def resource(name: str) -> E.Effect[str, Never, E.Scope]:
        return E.acquire_and_release(
            E.sync(lambda: track(actions, f"open {name}", name)),
            lambda h: E.sync(lambda: actions.append(f"close {h}")),
        )

    program = resource("a").flat_map(lambda _: resource("b"))

    assert E.run_sync(E.scoped(program)) == E.Succeeded("b")
    assert actions == ["open a", "open b", "close b", "close a"]


def test_release_runs_on_typed_failure():
    actions: list[str] = []
    resource = E.acquire_and_release(
        E.sync(lambda: track(actions, "open", "h")),
        lambda _: E.sync(lambda: actions.append("close")),
    )
    program = resource.flat_map(lambda _: E.fail(BrokenError("boom")))

    assert E.run_sync(E.scoped(program)) == E.Failure(cause=E.Fail(BrokenError("boom")))
    assert actions == ["open", "close"]


def test_release_runs_on_defect():
    actions: list[str] = []
    resource = E.acquire_and_release(
        E.sync(lambda: track(actions, "open", "h")),
        lambda _: E.sync(lambda: actions.append("close")),
    )
    program = resource.flat_map(lambda _: E.die("boom"))

    assert E.run_sync(E.scoped(program)) == E.Failure(cause=E.Die(defect="boom"))
    assert actions == ["open", "close"]


def test_failed_acquire_registers_no_release():
    actions: list[str] = []
    resource = E.acquire_and_release(
        E.fail(BrokenError("no resource")),
        lambda _: E.sync(lambda: actions.append("close")),
    )

    assert E.run_sync(E.scoped(resource)) == E.Failure(
        cause=E.Fail(BrokenError("no resource"))
    )
    assert actions == []


def test_acquired_programs_are_reusable_values():
    actions: list[str] = []
    resource = E.acquire_and_release(
        E.sync(lambda: track(actions, "open", "h")),
        lambda _: E.sync(lambda: actions.append("close")),
    )
    p: E.Effect[str] = E.scoped(resource)

    assert E.run_sync(p) == E.Succeeded("h")
    assert E.run_sync(p) == E.Succeeded("h")
    assert actions == ["open", "close", "open", "close"]


def test_raising_release_function_is_a_close_time_defect():
    # suspend defers release(): a raising release function becomes a
    # finalizer defect at close time and cannot skip other finalizers.
    actions: list[str] = []
    err = ValueError("release blew up")

    def bad_release(_: str) -> E.Effect[None]:
        raise err

    program = E.acquire_and_release(
        E.sync(lambda: track(actions, "open a", "a")),
        lambda _: E.sync(lambda: actions.append("close a")),
    ).flat_map(lambda _: E.acquire_and_release(E.sync(lambda: "b"), bad_release))

    assert E.run_sync(E.scoped(program)) == E.Failure(cause=E.Die(defect=err))
    assert actions == ["open a", "close a"]


def test_acquire_with_requirements():
    actions: list[str] = []
    resource = E.acquire_and_release(
        E.require(Db).map(lambda db: track(actions, f"open {db.url}", db.url)),
        lambda url: E.sync(lambda: actions.append(f"close {url}")),
    )
    p: E.Effect[str] = (
        E.RequirementProvider().and_provide(Db)(Db("pg")).and_scoped(resource)
    )

    assert E.run_sync(p) == E.Succeeded("pg")
    assert actions == ["open pg", "close pg"]
