from dataclasses import dataclass
from typing import Never

import effecton as E


@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


# --- thunk form ---


def test_suspend_success():
    assert E.run_sync(E.suspend(lambda: E.success(42))) == E.Succeeded(value=42)


def test_suspend_is_lazy():
    calls: list[int] = []

    def build() -> E.Effect[int]:
        calls.append(1)
        return E.success(42)

    p = E.suspend(build)

    assert calls == []
    assert E.run_sync(p) == E.Succeeded(42)
    assert calls == [1]


def test_suspend_propagates_failure():
    p = E.suspend(lambda: E.fail(OopsError("boom")))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OopsError("boom")))


def test_suspend_dies_when_thunk_raises():
    err = ValueError("boom")

    def explode() -> E.Effect[int]:
        raise err

    assert E.run_sync(E.suspend(explode)) == E.Failure(cause=E.Die(defect=err))


def test_suspend_effects_are_reusable_values():
    calls: list[int] = []

    def build() -> E.Effect[int]:
        calls.append(1)
        return E.success(len(calls))

    p = E.suspend(build)

    assert E.run_sync(p) == E.Succeeded(1)
    assert E.run_sync(p) == E.Succeeded(2)
    assert calls == [1, 1]


def test_suspend_composes_with_flat_map():
    p = E.suspend(lambda: E.success(20)).flat_map(lambda x: E.success(x + 22))

    assert E.run_sync(p) == E.Succeeded(42)


def test_suspend_recursion_is_stack_safe():
    def countdown(n: int) -> E.Effect[int]:
        if n == 0:
            return E.success(0)
        return E.suspend(lambda: countdown(n - 1)).map(lambda x: x + 1)

    assert E.run_sync(countdown(10_000)) == E.Succeeded(10_000)


# --- decorator form ---


def test_decorated_call_does_not_run_body():
    calls: list[int] = []

    @E.suspend
    def compute(x: int) -> E.Effect[int]:
        calls.append(x)
        return E.success(x * 2)

    p = compute(21)

    assert calls == []
    assert E.run_sync(p) == E.Succeeded(42)
    assert calls == [21]


def test_decorated_function_forwards_args_and_kwargs():
    @E.suspend
    def combine(a: str, b: str, sep: str = " ") -> E.Effect[str]:
        return E.success(f"{a}{sep}{b}")

    assert E.run_sync(combine("a", "b")) == E.Succeeded("a b")
    assert E.run_sync(combine("a", "b", sep="-")) == E.Succeeded("a-b")


def test_decorator_works_on_instance_methods():
    calls: list[int] = []

    class Service:
        @E.suspend
        def get(self, x: int) -> E.Effect[int]:
            calls.append(x)
            return E.success(x + 1)

    p = Service().get(1)

    assert calls == []
    assert E.run_sync(p) == E.Succeeded(2)
    assert calls == [1]


def test_zero_arg_function_resolves_to_the_thunk_form():
    calls: list[int] = []

    @E.suspend
    def config() -> E.Effect[int]:
        calls.append(1)
        return E.success(42)

    assert calls == []
    assert E.run_sync(config) == E.Succeeded(42)
    assert calls == [1]


def test_decorated_function_propagates_failure():
    @E.suspend
    def reject(msg: str) -> E.Effect[Never, OopsError]:
        return E.fail(OopsError(msg))

    assert E.run_sync(reject("boom")) == E.Failure(cause=E.Fail(OopsError("boom")))


def test_decorated_function_dies_when_body_raises():
    err = ValueError("boom")

    @E.suspend
    def explode(_x: int) -> E.Effect[int]:
        raise err

    assert E.run_sync(explode(1)) == E.Failure(cause=E.Die(defect=err))


def test_decorated_effects_are_reusable():
    calls: list[int] = []

    @E.suspend
    def track(x: int) -> E.Effect[int]:
        calls.append(x)
        return E.success(x)

    p = track(7)

    assert E.run_sync(p) == E.Succeeded(7)
    assert E.run_sync(p) == E.Succeeded(7)
    assert calls == [7, 7]


def test_decorator_preserves_function_metadata():
    @E.suspend
    def fetch_user(user_id: int) -> E.Effect[int]:
        return E.success(user_id)

    assert fetch_user.__name__ == "fetch_user"
