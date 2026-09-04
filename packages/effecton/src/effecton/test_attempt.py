from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


def test_attempt_success():
    p = E.attempt(lambda: 42, lambda e: OopsError(str(e)))

    assert E.run_sync(p) == E.Succeeded(value=42)


def test_attempt_exception_becomes_a_typed_failure():
    def boom() -> int:
        raise ValueError("boom")

    p = E.attempt(boom, lambda e: OopsError(str(e)))

    assert E.run_sync(p) == E.Failure(cause=E.Fail(OopsError("boom")))


def test_attempt_failure_is_catchable():
    def boom() -> int:
        raise ValueError("boom")

    p = E.attempt(boom, lambda e: OopsError(str(e))).catch_all(
        lambda e: E.success(len(e.msg))
    )

    assert E.run_sync(p) == E.Succeeded(value=4)


def test_attempt_is_lazy_and_reusable():
    calls: list[int] = []

    def track() -> int:
        calls.append(1)
        return len(calls)

    p = E.attempt(track, lambda e: OopsError(str(e)))

    assert calls == []  # Construction runs nothing.
    assert E.run_sync(p) == E.Succeeded(value=1)
    assert E.run_sync(p) == E.Succeeded(value=2)
    assert calls == [1, 1]


def test_attempt_reraise_in_on_error_keeps_a_defect():
    # The escape hatch for unexpected exceptions: re-raising instead of
    # converting lets the exception die as it would under sync.
    err = KeyError("unexpected")

    def boom() -> int:
        raise err

    def only_value_errors(e: Exception) -> OopsError:
        if isinstance(e, ValueError):
            return OopsError(str(e))
        raise e

    p = E.attempt(boom, only_value_errors)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect=err))


def test_attempt_exception_in_on_error_becomes_a_die():
    err = RuntimeError("handler broke")

    def boom() -> int:
        raise ValueError("boom")

    def broken_handler(e: Exception) -> OopsError:
        raise err

    p = E.attempt(boom, broken_handler)

    assert E.run_sync(p) == E.Failure(cause=E.Die(defect=err))
