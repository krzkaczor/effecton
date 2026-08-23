from dataclasses import dataclass

import effecton as E


@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


@dataclass(frozen=True)
class OtherError(E.EffectonError):
    code: int


def test_bare_success():
    assert E.run_sync(E.success(42)) == E.Succeeded(value=42)


def test_bare_fail():
    assert E.run_sync(E.fail(OopsError("boom"))) == E.Failure(
        cause=E.Fail(OopsError("boom"))
    )


def test_bare_die():
    assert E.run_sync(E.die("boom")) == E.Failure(cause=E.Die(defect="boom"))


def test_map():
    assert E.run_sync(E.success(21).map(lambda x: x * 2)) == E.Succeeded(value=42)


def test_map_skipped_on_failure():
    calls: list[int] = []

    def track(x: int) -> int:
        calls.append(x)
        return x

    p = E.fail(OopsError("boom")).map(track)

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OopsError("boom")))
    assert calls == []


def test_die_short_circuits_catch_all():
    calls: list[E.EffectonError] = []

    def handler(e: E.EffectonError) -> E.Effect[int, E.EffectonError]:
        calls.append(e)
        return E.success(0)

    p = E.die("boom").catch_all(handler)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect="boom"))
    assert calls == []


def test_die_short_circuits_flat_map():
    calls: list[int] = []

    def track(x: int) -> E.Effect[int, E.EffectonError]:
        calls.append(x)
        return E.success(x)

    p = E.die("boom").flat_map(track)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect="boom"))
    assert calls == []


def test_catch_all_on_success_is_not_called():
    calls: list[E.EffectonError] = []

    def handler(e: E.EffectonError) -> E.Effect[int, E.EffectonError]:
        calls.append(e)
        return E.success(0)

    p = E.success(42).catch_all(handler)

    assert E.run_sync(p) == E.Succeeded(value=42)
    assert calls == []


def test_catch_all_handler_that_fails():
    p = E.fail(OopsError("boom")).catch_all(lambda _: E.fail(OtherError(1)))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OtherError(1)))


def test_catch_all_rethrow():
    p = E.fail(OopsError("boom")).catch_all(lambda e: E.fail(e))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OopsError("boom")))


def test_nested_catch_all():
    p = (
        E.fail(OopsError("boom"))
        .catch_all(lambda _: E.fail(OtherError(1)))
        .catch_all(lambda e: E.success(e.code))
    )

    assert E.run_sync(p) == E.Succeeded(value=1)


def test_flat_map_after_catch_all():
    p = (
        E.fail(OopsError("boom"))
        .catch_all(lambda _: E.success(1))
        .flat_map(lambda x: E.success(x + 1))
    )

    assert E.run_sync(p) == E.Succeeded(value=2)


def test_catch_all_after_flat_map():
    p = (
        E.success(1)
        .flat_map(lambda _: E.fail(OopsError("boom")))
        .catch_all(lambda e: E.success(e.msg))
    )

    assert E.run_sync(p) == E.Succeeded(value="boom")


def test_flat_map_stack_safety():
    p: E.Effect[int, E.EffectonError] = E.success(0)
    for _ in range(10_000):
        p = p.flat_map(lambda x: E.success(x + 1))

    assert E.run_sync(p) == E.Succeeded(value=10_000)


def test_catch_all_stack_safety():
    p: E.Effect[int, OopsError] = E.fail(OopsError("boom"))
    for _ in range(10_000):
        p = p.catch_all(lambda e: E.fail(e))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OopsError("boom")))


def test_effects_are_reusable_values():
    calls: list[int] = []

    def track(x: int) -> E.Effect[int, E.EffectonError]:
        calls.append(x)
        return E.success(x * 2)

    p = E.success(21).flat_map(track)

    assert E.run_sync(p) == E.Succeeded(value=42)
    assert E.run_sync(p) == E.Succeeded(value=42)
    assert calls == [21, 21]


def test_exception_in_callback_becomes_a_die():
    err = ValueError("boom")

    def boom(x: int) -> E.Effect[int, E.EffectonError]:
        raise err

    p = E.success(1).flat_map(boom)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect=err))


def test_exception_in_catch_all_handler_becomes_a_die():
    err = ValueError("boom")

    def handler(e: OopsError) -> E.Effect[int, E.EffectonError]:
        raise err

    p = E.fail(OopsError("original")).catch_all(handler)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect=err))


def test_exception_die_is_not_caught_by_downstream_catch_all():
    err = ValueError("boom")
    calls: list[E.EffectonError] = []

    def boom(x: int) -> E.Effect[int, E.EffectonError]:
        raise err

    def handler(e: E.EffectonError) -> E.Effect[int, E.EffectonError]:
        calls.append(e)
        return E.success(0)

    p = E.success(1).flat_map(boom).catch_all(handler)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect=err))
    assert calls == []


def test_require_and_provide_requirement():
    p = E.require(str).map(lambda s: s.upper())

    provided = E.RequirementProvider().and_provide(str)("Kris").apply(p)

    assert E.run_sync(provided) == E.Succeeded("KRIS")


def test_two_requirements_provided_in_one_chain():
    r1 = E.require(str).map(lambda s: s.upper())
    r2 = E.require(int).map(lambda i: i * 10)

    p = r1.flat_map(lambda s: r2.map(lambda i: f"{s}{i}!"))

    provided = (
        E.RequirementProvider().and_provide(str)("Kris").and_provide(int)(5).apply(p)
    )

    assert E.run_sync(provided) == E.Succeeded("KRIS50!")


def test_three_requirements_provided_in_one_chain():
    r1 = E.require(str).map(lambda s: s.upper())
    r2 = E.require(int).map(lambda i: i * 10)
    r3 = E.require(float).map(lambda f: f / 2)

    p = r1.flat_map(lambda s: r2.flat_map(lambda i: r3.map(lambda f: f"{s}{i}|{f}!")))

    provided = (
        E.RequirementProvider()
        .and_provide(str)("Kris")
        .and_provide(int)(5)
        .and_provide(float)(1.0)
        .apply(p)
    )

    assert E.run_sync(provided) == E.Succeeded("KRIS50|0.5!")


def test_provide_is_scoped_to_the_applied_effect():
    scoped = E.RequirementProvider().and_provide(str)("inner").apply(E.require(str))
    p = scoped.flat_map(
        lambda first: E.require(str).map(lambda second: (first, second))
    )

    provided = E.RequirementProvider().and_provide(str)("outer").apply(p)

    assert E.run_sync(provided) == E.Succeeded(("inner", "outer"))


def test_inner_provide_shadows_outer_within_scope():
    inner = E.RequirementProvider().and_provide(str)("inner").apply(E.require(str))
    p = E.require(str).flat_map(lambda outer: inner.map(lambda i: (outer, i)))

    provided = E.RequirementProvider().and_provide(str)("outer").apply(p)

    assert E.run_sync(provided) == E.Succeeded(("outer", "inner"))


def test_provide_scope_unwinds_on_typed_failure():
    failing_scoped = (
        E.RequirementProvider()
        .and_provide(str)("inner")
        .apply(E.require(str).flat_map(lambda _: E.fail(OopsError("boom"))))
    )
    p = failing_scoped.catch_all(lambda _: E.require(str))

    provided = E.RequirementProvider().and_provide(str)("outer").apply(p)

    assert E.run_sync(provided) == E.Succeeded("outer")


def test_missing_requirement_dies():
    # Only reachable outside the typed API (pinned as a type error here).
    result = E.run_sync(E.require(str))  # ty: ignore[invalid-argument-type]

    assert result == E.Failure(cause=E.Die(defect=E.MissingRequirement(str)))


def test_sync_success():
    p = E.sync(lambda: 42)

    assert E.run_sync(p) == E.Succeeded(42)


def test_sync_dies():
    err = Exception("Boom!")

    def sync_fn_that_throws():
        raise err

    p = E.sync(sync_fn_that_throws)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect=err))


def test_sync_is_lazy():
    calls: list[int] = []

    def track() -> int:
        calls.append(1)
        return 42

    p = E.sync(track)

    assert calls == []
    assert E.run_sync(p) == E.Succeeded(42)
    assert calls == [1]


def test_sync_effects_are_reusable_values():
    calls: list[int] = []

    def track() -> int:
        calls.append(1)
        return 42

    p = E.sync(track)

    assert E.run_sync(p) == E.Succeeded(42)
    assert E.run_sync(p) == E.Succeeded(42)
    assert calls == [1, 1]


def test_sync_composes_with_flat_map():
    p = (
        E.sync(lambda: 21)
        .flat_map(lambda x: E.sync(lambda: x * 2))
        .map(lambda x: x + 1)
    )

    assert E.run_sync(p) == E.Succeeded(43)


def test_sync_die_short_circuits_catch_all():
    err = ValueError("boom")
    calls: list[E.EffectonError] = []

    def sync_fn_that_throws() -> int:
        raise err

    def handler(e: E.EffectonError) -> E.Effect[int, E.EffectonError]:
        calls.append(e)
        return E.success(0)

    p = E.sync(sync_fn_that_throws).catch_all(handler)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect=err))
    assert calls == []


def test_sync_skipped_on_failure():
    calls: list[int] = []

    def track() -> int:
        calls.append(1)
        return 42

    p = E.fail(OopsError("boom")).flat_map(lambda _: E.sync(track))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OopsError("boom")))
    assert calls == []


def test_on_exit():
    actions: list[str] = []

    def connect_db() -> E.Effect[str]:
        actions.append("connected")
        conn = "db-conn"

        return E.success(conn).on_exit(E.sync(lambda: disconnect_db(conn)))

    def disconnect_db(c) -> str:
        assert c == "db-conn"
        actions.append("disconnected")

        return "disconnect"

    p = E.sync(connect_db).flat_map(lambda x: x)

    assert E.run_sync(p) == E.Succeeded("db-conn")
    assert actions == ["connected", "disconnected"]


def test_on_exit_runs_on_typed_failure():
    actions: list[str] = []

    p = E.fail(OopsError("boom")).on_exit(E.sync(lambda: actions.append("finalized")))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OopsError("boom")))
    assert actions == ["finalized"]


def test_on_exit_runs_on_defect():
    actions: list[str] = []

    p = E.die("boom").on_exit(E.sync(lambda: actions.append("finalized")))

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect="boom"))
    assert actions == ["finalized"]


def test_nested_finalizers_run_inner_to_outer():
    actions: list[str] = []

    p = (
        E.success(1)
        .on_exit(E.sync(lambda: actions.append("inner")))
        .on_exit(E.sync(lambda: actions.append("outer")))
    )

    assert E.run_sync(p) == E.Succeeded(1)
    assert actions == ["inner", "outer"]


def test_finalizer_runs_before_outer_catch_all():
    actions: list[str] = []

    def handler(e: OopsError) -> E.Effect[int]:
        actions.append(f"handled:{e.msg}")
        return E.success(0)

    p = (
        E.fail(OopsError("boom"))
        .on_exit(E.sync(lambda: actions.append("finalized")))
        .catch_all(handler)
    )

    assert E.run_sync(p) == E.Succeeded(0)
    assert actions == ["finalized", "handled:boom"]


def test_finalizer_defect_replaces_the_exit():
    # Pins current semantics: a finalizer defect replaces the original
    # exit; causes are not combined.
    err = ValueError("cleanup failed")

    def bad_cleanup() -> None:
        raise err

    on_success = E.success(1).on_exit(E.sync(bad_cleanup))
    assert E.run_sync(on_success) == E.Failure(cause=E.Die(defect=err))

    on_failure = E.fail(OopsError("boom")).on_exit(E.sync(bad_cleanup))
    assert E.run_sync(on_failure) == E.Failure(cause=E.Die(defect=err))


def test_on_exit_effects_are_reusable_values():
    actions: list[str] = []

    p = E.success(1).on_exit(E.sync(lambda: actions.append("finalized")))

    assert E.run_sync(p) == E.Succeeded(1)
    assert E.run_sync(p) == E.Succeeded(1)
    assert actions == ["finalized", "finalized"]


def test_on_exit_stack_safety():
    p: E.Effect[int] = E.success(0)
    for _ in range(10_000):
        p = p.on_exit(E.sync(lambda: None))

    assert E.run_sync(p) == E.Succeeded(0)


def test_finalizer_requirements_are_provided():
    actions: list[str] = []

    fin = E.require(str).map(lambda s: actions.append(f"closed:{s}"))
    p = E.success(1).on_exit(fin)

    provided = E.RequirementProvider().and_provide(str)("conn").apply(p)

    assert E.run_sync(provided) == E.Succeeded(1)
    assert actions == ["closed:conn"]


def test_finalizer_runs_within_its_provide_scope():
    actions: list[str] = []

    fin = E.require(str).map(lambda s: actions.append(s))
    inner = (
        E.RequirementProvider()
        .and_provide(str)("inner")
        .apply(E.success(1).on_exit(fin))
    )
    p = inner.flat_map(lambda x: E.require(str).map(lambda s: (x, s)))

    provided = E.RequirementProvider().and_provide(str)("outer").apply(p)

    assert E.run_sync(provided) == E.Succeeded((1, "outer"))
    assert actions == ["inner"]
