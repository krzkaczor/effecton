import asyncio
from dataclasses import dataclass
from typing import final

import pytest

import effecton as E


@final
@dataclass(frozen=True)
class RaceError(E.EffectonError):
    def __str__(self) -> str:
        return "Race failed"


def forever() -> E.Effect[bool]:
    return E.coroutine(lambda: asyncio.Event().wait())


@pytest.mark.parametrize("left_wins", [True, False])
def test_either_branch_can_win(left_wins):
    winner = E.success(42)
    loser = forever()
    program = E.race_first(winner, loser) if left_wins else E.race_first(loser, winner)

    result = E.run_async(program)

    assert result == 42


@pytest.mark.parametrize("left_wins", [True, False])
@E.gen
def test_either_branch_can_win_after_both_suspend(left_wins: bool) -> E.EffectGen[None]:
    left = asyncio.Event()
    right = asyncio.Event()
    program = E.race_first(
        E.coroutine(left.wait).map(lambda _: "left"),
        E.coroutine(right.wait).map(lambda _: "right"),
    )
    fiber = yield from E.fork(program)
    yield from E.yield_now()

    yield from E.sync((left if left_wins else right).set)
    result = yield from fiber.join()

    assert result == ("left" if left_wins else "right")


@pytest.mark.parametrize("left_wins", [True, False])
@pytest.mark.parametrize("outcome", ["failure", "defect", "interruption"])
def test_the_winners_cause_passes_through(left_wins, outcome):
    error = RaceError()
    defect = ValueError("broken")
    interruption = asyncio.CancelledError("stopped")

    def interrupt():
        raise interruption

    match outcome:
        case "failure":
            winner = E.fail(error)
            expected = E.Fail(error)
        case "defect":
            winner = E.die(defect)
            expected = E.Die(defect)
        case _:
            winner = E.sync(interrupt)
            expected = E.Interrupt(interruption)
    program = (
        E.race_first(winner, forever())
        if left_wins
        else E.race_first(forever(), winner)
    )

    result = E.run_async_exit(program)

    assert result == E.Failure[RaceError](expected)


def test_left_wins_when_both_are_complete():
    program = E.race_first(E.fail(RaceError()), E.success(42))

    result = E.run_async_exit(program)

    assert result == E.Failure(E.Fail(RaceError()))


def test_construction_is_lazy_and_every_run_starts_both_branches():
    actions: list[str] = []
    program = E.race_first(
        E.sync(lambda: actions.append("left")),
        E.sync(lambda: actions.append("right")),
    )
    assert actions == []

    E.run_async(program)
    E.run_async(program)

    assert actions == ["left", "right", "left", "right"]


def test_branches_inherit_requirements_and_local_overrides_stay_local():
    actions: list[str] = []
    read = E.require(str).flat_map(lambda value: E.sync(lambda: actions.append(value)))
    program = E.race_first(read.provide(str)("local"), read).flat_map(lambda _: read)

    E.run_async(program.provide(str)("outer"))

    assert actions == ["local", "outer", "outer"]


def test_loser_finalizes_before_the_winner_returns():
    actions: list[str] = []
    loser = forever().on_exit(E.sync(lambda: actions.append("finalized")))
    program = E.race_first(loser, E.success(42)).map(
        lambda value: actions.append(f"returned:{value}")
    )

    E.run_async(program)

    assert actions == ["finalized", "returned:42"]


def test_loser_cleanup_defect_does_not_replace_the_winner():
    loser = forever().on_exit(E.die(ValueError("cleanup")))
    program = E.race_first(loser, E.success(42))

    result = E.run_async_exit(program)

    assert result == E.Succeeded(42)


@pytest.mark.parametrize("branch_scope", [True, False])
def test_resources_are_released_when_their_owning_scope_closes(branch_scope):
    actions: list[str] = []
    loser = E.acquire_and_release(
        E.success("resource"),
        lambda _: E.sync(lambda: actions.append("released")),
    ).flat_map(lambda _: forever())
    program = E.race_first(loser.scoped() if branch_scope else loser, E.success(42))

    at_return = E.run_async(program.map(lambda _: list(actions)).scoped())

    assert at_return == (["released"] if branch_scope else [])
    assert actions == ["released"]


def test_racing_inside_a_finalizer_remains_shielded():
    actions: list[str] = []

    async def main():
        started = asyncio.Event()
        release = asyncio.Event()

        async def finalize():
            started.set()
            await release.wait()
            actions.append("finalized")

        finalizer = E.race_first(E.coroutine(finalize), forever())
        task = asyncio.create_task(
            E.run_async_coroutine(E.success(None).on_exit(finalizer))
        )
        await started.wait()

        task.cancel()
        await E.run_async_coroutine(E.yield_now())
        assert not task.done()
        release.set()
        result = await task

        assert asyncio.all_tasks() == {asyncio.current_task()}
        return result

    result = asyncio.run(main())

    assert isinstance(result, E.Failure)
    assert isinstance(result.cause, E.Interrupt)
    assert actions == ["finalized"]


@pytest.mark.parametrize("cancel_after_winner", [True, False])
def test_repeated_parent_cancellation_waits_for_cleanup(cancel_after_winner):
    actions: list[str] = []

    async def main():
        cleaning = asyncio.Event()
        release = asyncio.Event()

        async def cleanup(name: str):
            cleaning.set()
            await release.wait()
            actions.append(name)

        left = forever().on_exit(E.coroutine(lambda: cleanup("left")))
        right = (
            E.success(42)
            if cancel_after_winner
            else forever().on_exit(E.coroutine(lambda: cleanup("right")))
        )
        task = asyncio.create_task(
            E.run_async_coroutine(E.race_first(left, right)), eager_start=True
        )
        if not cancel_after_winner:
            task.cancel("first")
        await cleaning.wait()
        task.cancel("during cleanup")
        await E.run_async_coroutine(E.yield_now())
        task.cancel("repeated")
        await E.run_async_coroutine(E.yield_now())
        assert not task.done()
        assert actions == []
        release.set()
        result = await task
        assert asyncio.all_tasks() == {asyncio.current_task()}
        return result

    result = asyncio.run(main())

    assert isinstance(result, E.Failure)
    assert isinstance(result.cause, E.Interrupt)
    assert sorted(actions) == (["left"] if cancel_after_winner else ["left", "right"])


@E.gen
def test_completed_race_leaves_no_tasks() -> E.EffectGen[None]:
    yield from E.race_first(forever(), E.success(42))

    tasks = yield from E.sync(asyncio.all_tasks)

    assert tasks == {asyncio.current_task()}


@E.gen
def test_racing_join_does_not_cancel_the_independent_fiber() -> E.EffectGen[None]:
    fiber = yield from E.fork(forever())
    yield from E.yield_now()

    result = yield from E.race_first(fiber.join(), E.success(42))
    pending = yield from fiber.poll()
    yield from fiber.interrupt()

    assert result == 42
    assert pending is None


def test_race_dies_under_run_sync():
    program = E.race_first(E.success(1), E.success(2))

    result = E.run_sync_exit(program)

    assert result == E.Failure(E.Die(E.AsyncEffectInSyncRun()))
