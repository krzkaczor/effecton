import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, final

import pytest

import effecton as E

# Interrupt has no public constructor; the runner tests build the node directly.
from effecton.effect import FailCause


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


async def double(x: int) -> int:
    await asyncio.sleep(0)
    return x * 2


def test_coroutine_success():
    p = E.coroutine(lambda: double(21))

    assert E.run_async_exit(p) == E.Succeeded(42)


def test_run_async_returns_the_value():
    assert E.run_async(E.coroutine(lambda: double(21))) == 42


def test_run_async_raises_the_error():
    error = OopsError("boom")
    p = E.coroutine(lambda: double(1)).flat_map(lambda _: E.fail(error))

    with pytest.raises(OopsError) as info:
        E.run_async(p)

    assert info.value is error


def test_run_async_reraises_an_exception_defect():
    err = ValueError("boom")

    async def bad() -> int:
        raise err

    with pytest.raises(ValueError) as info:
        E.run_async(E.coroutine(bad))

    assert info.value is err


def test_run_async_wraps_a_non_exception_defect():
    with pytest.raises(E.UnhandledDefect) as info:
        E.run_async(E.die("boom"))

    assert info.value.defect == "boom"


def test_run_async_reraises_the_interrupt_exception():
    interrupt = KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt) as info:
        E.run_async(FailCause(cause=E.Interrupt(interrupt)))

    assert info.value is interrupt


def test_run_async_runs_finalizers_before_raising():
    actions: list[str] = []

    async def cleanup() -> None:
        await asyncio.sleep(0)
        actions.append("finalized")

    p = E.fail(OopsError("boom")).on_exit(E.coroutine(cleanup))

    with pytest.raises(OopsError):
        E.run_async(p)

    assert actions == ["finalized"]


def test_pure_sync_program_runs_under_run_async():
    p = E.success(21).map(lambda x: x * 2).on_exit(E.sync(lambda: None))

    assert E.run_async_exit(p) == E.Succeeded(42)


def test_typed_failure_passes_through():
    p = E.coroutine(lambda: double(1)).flat_map(lambda _: E.fail(OopsError("boom")))

    assert E.run_async_exit(p) == E.Failure(cause=E.Fail(OopsError("boom")))


def test_thunk_that_raises_dies():
    err = ValueError("boom")

    def bad_thunk() -> asyncio.Future[int]:
        raise err

    p = E.coroutine(bad_thunk)

    assert E.run_async_exit(p) == E.Failure(cause=E.Die(defect=err))


def test_await_that_raises_dies():
    err = ValueError("boom")

    async def bad() -> int:
        await asyncio.sleep(0)
        raise err

    p = E.coroutine(bad)

    assert E.run_async_exit(p) == E.Failure(cause=E.Die(defect=err))


def test_coroutine_is_lazy():
    calls: list[int] = []

    async def track() -> int:
        calls.append(1)
        return 42

    p = E.coroutine(track)

    assert calls == []
    assert E.run_async_exit(p) == E.Succeeded(42)
    assert calls == [1]


def test_coroutine_effects_are_reusable_values():
    calls: list[int] = []

    async def track() -> int:
        calls.append(1)
        return 42

    p = E.coroutine(track)

    assert E.run_async_exit(p) == E.Succeeded(42)
    assert E.run_async_exit(p) == E.Succeeded(42)
    assert calls == [1, 1]


def test_captured_coroutine_object_dies_on_second_run():
    coro = double(1)
    p = E.coroutine(lambda: coro)

    assert E.run_async_exit(p) == E.Succeeded(2)
    match E.run_async_exit(p):
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

    assert E.run_async_exit(p) == E.Succeeded(None)
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

    assert E.run_async_exit(p) == E.Succeeded(8)
    assert actions == ["acquired", "released:conn"]


def test_scoped_async_context_manager_restores_context():
    value = ContextVar("value", default="before")
    actions: list[str] = []

    @asynccontextmanager
    async def resource() -> AsyncIterator[str]:
        token = value.set("inside")
        try:
            yield "resource"
        finally:
            value.reset(token)
            actions.append("released")

    async def main():
        manager = resource()
        p = E.acquire_and_release(
            E.coroutine(manager.__aenter__),
            lambda _: E.coroutine(lambda: manager.__aexit__(None, None, None)),
        ).scoped()
        result = await E.run_async_task(p)
        return result, value.get()

    result, restored_value = asyncio.run(main())

    assert result == E.Succeeded("resource")
    assert actions == ["released"]
    assert restored_value == "before"


def test_provide_scope_is_restored_across_await():
    inner = E.coroutine(lambda: double(1)).flat_map(lambda _: E.require(str))
    p = inner.provide(str)("inner").flat_map(
        lambda a: E.require(str).map(lambda b: (a, b))
    )

    provided = p.provide(str)("outer")

    assert E.run_async_exit(provided) == E.Succeeded(("inner", "outer"))


def test_gen_body_yields_coroutine():
    @E.gen
    def program(x: int) -> E.EffectGen[int, OopsError]:
        doubled = yield from E.coroutine(lambda: double(x))

        if doubled > 100:
            yield from E.fail(OopsError("too big"))
        return doubled + 1

    assert E.run_async_exit(program(21)) == E.Succeeded(43)
    assert E.run_async_exit(program(51)) == E.Failure(
        cause=E.Fail(OopsError("too big"))
    )


def test_attempt_async_success():
    p = E.attempt_async(lambda: double(21), lambda e: OopsError(str(e)))

    assert E.run_async_exit(p) == E.Succeeded(42)


def test_attempt_async_maps_expected_exception():
    async def bad() -> int:
        await asyncio.sleep(0)
        raise ValueError("bad value")

    def to_error(e: Exception) -> OopsError:
        if isinstance(e, ValueError):
            return OopsError(str(e))
        raise e

    p = E.attempt_async(bad, to_error)

    assert E.run_async_exit(p) == E.Failure(cause=E.Fail(OopsError("bad value")))


def test_attempt_async_reraised_exception_stays_a_defect():
    err = KeyError("unexpected")

    async def bad() -> int:
        raise err

    def to_error(e: Exception) -> OopsError:
        if isinstance(e, ValueError):
            return OopsError(str(e))
        raise e

    p = E.attempt_async(bad, to_error)

    assert E.run_async_exit(p) == E.Failure(cause=E.Die(defect=err))


def test_attempt_async_is_lazy_and_reusable():
    calls: list[int] = []

    async def track() -> int:
        calls.append(1)
        return 42

    p = E.attempt_async(track, lambda e: OopsError(str(e)))

    assert calls == []
    assert E.run_async_exit(p) == E.Succeeded(42)
    assert E.run_async_exit(p) == E.Succeeded(42)
    assert calls == [1, 1]


def assert_interrupted(exit: E.Exit[Any, Any]) -> None:
    match exit:
        case E.Failure(E.Interrupt(exception)):
            assert isinstance(exception, asyncio.CancelledError)
        case other:
            raise AssertionError(other)


def test_cancellation_runs_finalizers_then_returns_interrupt():
    actions: list[str] = []

    async def forever() -> None:
        await asyncio.Event().wait()

    async def cleanup() -> None:
        await asyncio.sleep(0)
        actions.append("finalized")

    p = E.coroutine(forever).on_exit(E.coroutine(cleanup))

    async def main():
        task = asyncio.create_task(E.run_async_task(p))
        await asyncio.sleep(0)
        task.cancel()
        return await task

    assert_interrupted(asyncio.run(main()))
    assert actions == ["finalized"]


def test_cancellation_preserves_nested_finalizer_continuation():
    actions: list[str] = []

    async def main():
        started = asyncio.Event()

        async def forever() -> None:
            started.set()
            await asyncio.Event().wait()

        cleanup = (
            E.success(None)
            .on_exit(E.sync(lambda: actions.append("inner")))
            .flat_map(lambda _: E.sync(lambda: actions.append("remaining")))
        )
        p = E.coroutine(forever).on_exit(cleanup)
        task = asyncio.create_task(E.run_async_task(p))
        await started.wait()
        task.cancel()
        return await task

    result = asyncio.run(main())

    assert_interrupted(result)
    assert actions == ["inner", "remaining"]


def test_cancellation_skips_catch_all():
    calls: list[E.EffectonError] = []

    async def forever() -> None:
        await asyncio.Event().wait()

    def handler(e: E.EffectonError) -> E.Effect[None]:
        calls.append(e)
        return E.success(None)

    p = E.coroutine(forever).catch_all(handler)

    async def main():
        task = asyncio.create_task(E.run_async_task(p))
        await asyncio.sleep(0)
        task.cancel()
        return await task

    assert_interrupted(asyncio.run(main()))
    assert calls == []


def test_timeout_around_run_async_releases_scope_and_returns_interrupt():
    actions: list[str] = []

    async def forever() -> None:
        await asyncio.Event().wait()

    conn = E.acquire_and_release(
        E.sync(lambda: actions.append("acquired")),
        lambda _: E.sync(lambda: actions.append("released")),
    )
    p = conn.flat_map(lambda _: E.coroutine(forever)).scoped()

    async def main():
        async with asyncio.timeout(0.01):
            return await E.run_async_task(p)

    assert_interrupted(asyncio.run(main()))
    assert actions == ["acquired", "released"]


def test_cancellation_during_release_lets_the_release_finish():
    actions: list[str] = []
    release_may_finish = asyncio.Event()

    async def release(conn: str) -> None:
        actions.append(f"release-start:{conn}")
        await release_may_finish.wait()
        actions.append(f"release-done:{conn}")

    conn = E.acquire_and_release(
        E.success("conn"), lambda c: E.coroutine(lambda: release(c))
    )
    p = conn.scoped()

    async def main():
        task = asyncio.create_task(E.run_async_task(p))
        while not actions:
            await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()  # a repeated cancellation must not abort it either
        await asyncio.sleep(0)
        release_may_finish.set()
        return await task

    # The wrapped effect had already succeeded; the interruption still wins.
    assert_interrupted(asyncio.run(main()))
    assert actions == ["release-start:conn", "release-done:conn"]


def test_interrupt_wins_over_a_finalizer_defect():
    async def forever() -> None:
        await asyncio.Event().wait()

    async def bad_cleanup() -> None:
        raise ValueError("cleanup failed")

    p = E.coroutine(forever).on_exit(E.coroutine(bad_cleanup))

    async def main():
        task = asyncio.create_task(E.run_async_task(p))
        await asyncio.sleep(0)
        task.cancel()
        return await task

    assert_interrupted(asyncio.run(main()))


def test_cancellation_raised_by_sync_thunk_runs_finalizers_then_returns_interrupt():
    actions: list[str] = []

    conn = E.acquire_and_release(
        E.sync(lambda: actions.append("acquired")),
        lambda _: E.sync(lambda: actions.append("released")),
    )

    async def main():
        cancelled_future = asyncio.get_running_loop().create_future()
        cancelled_future.cancel()
        p = conn.flat_map(lambda _: E.sync(cancelled_future.result)).scoped()

        return await E.run_async_task(p)

    assert_interrupted(asyncio.run(main()))
    assert actions == ["acquired", "released"]


def test_cancellation_raised_by_callback_runs_finalizers_then_returns_interrupt():
    actions: list[str] = []

    def boom(_: int) -> E.Effect[int]:
        raise asyncio.CancelledError

    p = E.success(1).flat_map(boom).on_exit(E.sync(lambda: actions.append("finalized")))

    assert_interrupted(E.run_async_exit(p))
    assert actions == ["finalized"]


def test_finalizer_defect_still_replaces_the_exit():
    err = ValueError("cleanup failed")

    async def bad_cleanup() -> None:
        raise err

    p = E.success(1).on_exit(E.coroutine(bad_cleanup))

    assert E.run_async_exit(p) == E.Failure(cause=E.Die(defect=err))


def test_nested_finalizers_run_inner_to_outer_across_awaits():
    actions: list[str] = []

    async def step(name: str) -> None:
        await asyncio.sleep(0)
        actions.append(name)

    p = (
        E.success(1)
        .on_exit(E.coroutine(lambda: step("inner")))
        .on_exit(E.coroutine(lambda: step("outer")))
    )

    assert E.run_async_exit(p) == E.Succeeded(1)
    assert actions == ["inner", "outer"]
