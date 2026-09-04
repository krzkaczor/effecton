from dataclasses import dataclass

import effecton as E


@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


@dataclass(frozen=True)
class BigOopsError(OopsError):
    pass


@dataclass(frozen=True)
class OtherError(E.EffectonError):
    code: int


def test_catch_matching_error_runs_handler():
    p = E.fail(OopsError("boom")).catch(OopsError)(lambda e: E.success(e.msg))

    assert E.run_sync(p) == E.Succeeded(value="boom")


def test_catch_non_matching_error_propagates():
    calls: list[OopsError] = []

    def handler(e: OopsError) -> E.Effect[int]:
        calls.append(e)
        return E.success(0)

    p = E.fail(OtherError(1)).catch(OopsError)(handler)

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OtherError(1)))
    assert calls == []


def test_catch_on_success_is_not_called():
    calls: list[OopsError] = []

    def handler(e: OopsError) -> E.Effect[int]:
        calls.append(e)
        return E.success(0)

    p = E.success(42).catch(OopsError)(handler)

    assert E.run_sync(p) == E.Succeeded(value=42)
    assert calls == []


def test_die_short_circuits_catch():
    calls: list[OopsError] = []

    def handler(e: OopsError) -> E.Effect[int]:
        calls.append(e)
        return E.success(0)

    p = E.die("boom").catch(OopsError)(handler)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect="boom"))
    assert calls == []


def test_catch_matches_subclass_instances():
    p = E.fail(BigOopsError("boom")).catch(OopsError)(lambda e: E.success(e.msg))

    assert E.run_sync(p) == E.Succeeded(value="boom")


def test_catch_does_not_match_base_class_instances():
    p = E.fail(OopsError("boom")).catch(BigOopsError)(lambda _: E.success(0))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OopsError("boom")))


def test_catch_handler_that_fails():
    p = E.fail(OopsError("boom")).catch(OopsError)(lambda _: E.fail(OtherError(1)))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OtherError(1)))


def test_exception_in_catch_handler_becomes_a_die():
    err = ValueError("boom")

    def handler(e: OopsError) -> E.Effect[int]:
        raise err

    p = E.fail(OopsError("original")).catch(OopsError)(handler)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect=err))


def test_chained_catches_handle_a_union():
    def fail_with(n: int) -> E.Effect[int, OopsError | OtherError]:
        return E.fail(OopsError("boom")) if n == 0 else E.fail(OtherError(n))

    def program(n: int) -> E.Effect[int | str]:
        return (
            fail_with(n)
            .catch(OopsError)(lambda e: E.success(e.msg))
            .catch(OtherError)(lambda e: E.success(e.code))
        )

    assert E.run_sync(program(0)) == E.Succeeded(value="boom")
    assert E.run_sync(program(7)) == E.Succeeded(value=7)


def test_catch_composes_over_gen():
    @E.gen
    def program() -> E.EffectGen[int, OopsError]:
        yield from E.fail(OopsError("boom"))
        return 1

    recovered = program().catch(OopsError)(lambda e: E.success(len(e.msg)))

    assert E.run_sync(recovered) == E.Succeeded(value=4)


def test_catch_stack_safety():
    p: E.Effect[int, OopsError] = E.fail(OopsError("boom"))
    for _ in range(10_000):
        p = p.catch(OtherError)(lambda _: E.success(0))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OopsError("boom")))
