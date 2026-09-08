import asyncio
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


@E.gen
def test_join_returns_the_value() -> E.EffectGen[None]:
    fiber = yield from E.fork(E.success(21).map(lambda x: x * 2))

    result = yield from fiber.join()

    assert result == 42


@E.gen
def test_join_fails_with_the_fibers_error() -> E.EffectGen[None]:
    fiber = yield from E.fork(E.fail(OopsError("boom")))

    result = yield from fiber.join().catch_all(lambda e: E.success(f"caught:{e.msg}"))

    assert result == "caught:boom"


@E.gen
def test_wait_returns_the_exit() -> E.EffectGen[None]:
    err = ValueError("boom")
    fiber = yield from E.fork(E.die(err))

    result = yield from fiber.wait()

    assert result == E.Failure(cause=E.Die(defect=err))


@E.gen
def test_poll_peeks_without_waiting() -> E.EffectGen[None]:
    gate = asyncio.Event()
    fiber = yield from E.fork(E.coroutine(gate.wait))
    yield from E.yield_now()  # let the fiber start

    running = yield from fiber.poll()
    yield from E.sync(gate.set)
    yield from fiber.wait()
    settled = yield from fiber.poll()

    assert running is None
    assert settled == E.Succeeded(True)


@E.gen
def test_interrupt_runs_finalizers_and_settles_as_interrupt() -> E.EffectGen[None]:
    actions: list[str] = []
    forever = E.coroutine(asyncio.Event().wait).on_exit(
        E.sync(lambda: actions.append("finalized"))
    )
    fiber = yield from E.fork(forever)
    yield from E.yield_now()  # let the fiber start

    result = yield from fiber.interrupt()

    assert actions == ["finalized"]
    match result:
        case E.Failure(E.Interrupt(exception)):
            assert isinstance(exception, asyncio.CancelledError)
        case other:
            raise AssertionError(other)


@E.gen
def test_interrupt_before_the_first_step_does_not_interrupt_the_parent() -> E.EffectGen[
    None
]:
    fiber = yield from E.fork(E.success(1))

    result = yield from fiber.interrupt()
    after = yield from E.success("parent continues")

    assert after == "parent continues"
    match result:
        case E.Failure(E.Interrupt(exception)):
            assert isinstance(exception, asyncio.CancelledError)
        case other:
            raise AssertionError(other)


def test_fork_dies_under_run_sync():
    p = E.fork(E.success(1))

    assert E.run_sync_exit(p) == E.Failure(cause=E.Die(defect=E.AsyncEffectInSyncRun()))
