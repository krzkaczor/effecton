import asyncio
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


async def double(x: int) -> int:
    await asyncio.sleep(0)
    return x * 2


def test_coroutine_success():
    p = E.coroutine(lambda: double(21))

    assert asyncio.run(E.run_async(p)) == E.Succeeded(42)


def test_pure_sync_program_runs_under_run_async():
    p = E.success(21).map(lambda x: x * 2).on_exit(E.sync(lambda: None))

    assert asyncio.run(E.run_async(p)) == E.Succeeded(42)


def test_typed_failure_passes_through():
    p = E.coroutine(lambda: double(1)).flat_map(lambda _: E.fail(OopsError("boom")))

    assert asyncio.run(E.run_async(p)) == E.Failure(cause=E.Fail(OopsError("boom")))


def test_thunk_that_raises_dies():
    err = ValueError("boom")

    def bad_thunk() -> asyncio.Future[int]:
        raise err

    p = E.coroutine(bad_thunk)

    assert asyncio.run(E.run_async(p)) == E.Failure(cause=E.Die(defect=err))


def test_await_that_raises_dies():
    err = ValueError("boom")

    async def bad() -> int:
        await asyncio.sleep(0)
        raise err

    p = E.coroutine(bad)

    assert asyncio.run(E.run_async(p)) == E.Failure(cause=E.Die(defect=err))


def test_coroutine_is_lazy():
    calls: list[int] = []

    async def track() -> int:
        calls.append(1)
        return 42

    p = E.coroutine(track)

    assert calls == []
    assert asyncio.run(E.run_async(p)) == E.Succeeded(42)
    assert calls == [1]


def test_coroutine_effects_are_reusable_values():
    calls: list[int] = []

    async def track() -> int:
        calls.append(1)
        return 42

    p = E.coroutine(track)

    assert asyncio.run(E.run_async(p)) == E.Succeeded(42)
    assert asyncio.run(E.run_async(p)) == E.Succeeded(42)
    assert calls == [1, 1]


def test_captured_coroutine_object_dies_on_second_run():
    coro = double(1)
    p = E.coroutine(lambda: coro)

    assert asyncio.run(E.run_async(p)) == E.Succeeded(2)
    match asyncio.run(E.run_async(p)):
        case E.Failure(E.Die(defect)):
            assert isinstance(defect, RuntimeError)
        case other:
            raise AssertionError(other)


def test_finalizers_run_across_await_points():
    actions: list[str] = []

    async def step(name: str) -> None:
        await asyncio.sleep(0)
        actions.append(name)

    p = (
        E.coroutine(lambda: step("first"))
        .flat_map(lambda _: E.coroutine(lambda: step("second")))
        .on_exit(E.coroutine(lambda: step("finalized")))
    )

    assert asyncio.run(E.run_async(p)) == E.Succeeded(None)
    assert actions == ["first", "second", "finalized"]


def test_scope_releases_across_await_points():
    actions: list[str] = []

    async def acquire() -> str:
        await asyncio.sleep(0)
        actions.append("acquired")
        return "conn"

    async def release(conn: str) -> None:
        await asyncio.sleep(0)
        actions.append(f"released:{conn}")

    conn = E.acquire_and_release(
        E.coroutine(acquire), lambda c: E.coroutine(lambda: release(c))
    )
    p = conn.flat_map(lambda c: E.coroutine(lambda: double(len(c)))).scoped()

    assert asyncio.run(E.run_async(p)) == E.Succeeded(8)
    assert actions == ["acquired", "released:conn"]


def test_provide_scope_is_restored_across_await():
    inner = E.coroutine(lambda: double(1)).flat_map(lambda _: E.require(str))
    p = inner.provide(str)("inner").flat_map(
        lambda a: E.require(str).map(lambda b: (a, b))
    )

    provided = p.provide(str)("outer")

    assert asyncio.run(E.run_async(provided)) == E.Succeeded(("inner", "outer"))


def test_gen_body_yields_coroutine():
    @E.gen
    def program(x: int) -> E.EffectGen[int, OopsError]:
        doubled = yield from E.coroutine(lambda: double(x))

        if doubled > 100:
            yield from E.fail(OopsError("too big"))
        return doubled + 1

    assert asyncio.run(E.run_async(program(21))) == E.Succeeded(43)
    assert asyncio.run(E.run_async(program(51))) == E.Failure(
        cause=E.Fail(OopsError("too big"))
    )


def test_attempt_async_success():
    p = E.attempt_async(lambda: double(21), lambda e: OopsError(str(e)))

    assert asyncio.run(E.run_async(p)) == E.Succeeded(42)


def test_attempt_async_maps_expected_exception():
    async def bad() -> int:
        await asyncio.sleep(0)
        raise ValueError("bad value")

    def to_error(e: Exception) -> OopsError:
        if isinstance(e, ValueError):
            return OopsError(str(e))
        raise e

    p = E.attempt_async(bad, to_error)

    assert asyncio.run(E.run_async(p)) == E.Failure(
        cause=E.Fail(OopsError("bad value"))
    )


def test_attempt_async_reraised_exception_stays_a_defect():
    err = KeyError("unexpected")

    async def bad() -> int:
        raise err

    def to_error(e: Exception) -> OopsError:
        if isinstance(e, ValueError):
            return OopsError(str(e))
        raise e

    p = E.attempt_async(bad, to_error)

    assert asyncio.run(E.run_async(p)) == E.Failure(cause=E.Die(defect=err))


def test_attempt_async_is_lazy_and_reusable():
    calls: list[int] = []

    async def track() -> int:
        calls.append(1)
        return 42

    p = E.attempt_async(track, lambda e: OopsError(str(e)))

    assert calls == []
    assert asyncio.run(E.run_async(p)) == E.Succeeded(42)
    assert asyncio.run(E.run_async(p)) == E.Succeeded(42)
    assert calls == [1, 1]


def test_cancellation_runs_finalizers_then_reraises():
    actions: list[str] = []

    async def forever() -> None:
        await asyncio.Event().wait()

    async def cleanup() -> None:
        await asyncio.sleep(0)
        actions.append("finalized")

    p = E.coroutine(forever).on_exit(E.coroutine(cleanup))

    async def main() -> None:
        task = asyncio.create_task(E.run_async(p))
        await asyncio.sleep(0)
        task.cancel()
        await task

    try:
        asyncio.run(main())
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("cancellation was swallowed")
    assert actions == ["finalized"]


def test_cancellation_skips_catch_all():
    calls: list[E.EffectonError] = []

    async def forever() -> None:
        await asyncio.Event().wait()

    def handler(e: E.EffectonError) -> E.Effect[None]:
        calls.append(e)
        return E.success(None)

    p = E.coroutine(forever).catch_all(handler)

    async def main() -> None:
        task = asyncio.create_task(E.run_async(p))
        await asyncio.sleep(0)
        task.cancel()
        await task

    try:
        asyncio.run(main())
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("cancellation was swallowed")
    assert calls == []


def test_timeout_around_run_async_releases_scope():
    actions: list[str] = []

    async def forever() -> None:
        await asyncio.Event().wait()

    conn = E.acquire_and_release(
        E.sync(lambda: actions.append("acquired")),
        lambda _: E.sync(lambda: actions.append("released")),
    )
    p = conn.flat_map(lambda _: E.coroutine(forever)).scoped()

    async def main() -> None:
        async with asyncio.timeout(0.01):
            await E.run_async(p)

    try:
        asyncio.run(main())
    except TimeoutError:
        pass
    else:
        raise AssertionError("timeout did not fire")
    assert actions == ["acquired", "released"]
