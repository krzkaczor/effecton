from dataclasses import dataclass
from typing import Never, final

import effecton as E


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


@dataclass(frozen=True)
class Db:
    answer: int


# Programs use ``yield from``: through Effect.__iter__ the sent-back
# value is typed as the effect's A per expression, with no annotations.


def test_basic_sequence():
    @E.gen
    def program() -> E.EffectGen[int]:
        x = yield from E.success(20)
        y = yield from E.success(22)
        return x + y

    assert E.run_sync(program()) == E.Succeeded(value=42)


def test_parameterized_program():
    @E.gen
    def program(base: int) -> E.EffectGen[int]:
        x = yield from E.success(base)
        return x * 2

    assert E.run_sync(program(21)) == E.Succeeded(value=42)


def test_failure_short_circuits():
    reached: list[str] = []

    @E.gen
    def program() -> E.EffectGen[int, OopsError]:
        yield from E.success(1)
        yield from E.fail(OopsError("boom"))
        reached.append("after failing yield")
        return 0

    assert E.run_sync(program()) == E.Failure(cause=E.Fail(OopsError("boom")))
    assert reached == []


def test_try_except_does_not_catch_effect_failure():
    # Effect failure abandons the generator instead of raising into it;
    # recovery belongs to catch_all.
    caught: list[str] = []

    @E.gen
    def program() -> E.EffectGen[int, OopsError]:
        try:
            yield from E.fail(OopsError("boom"))
        except Exception:
            caught.append("caught")
        return 0

    assert E.run_sync(program()) == E.Failure(cause=E.Fail(OopsError("boom")))
    assert caught == []


def test_catch_all_composes_over_gen():
    @E.gen
    def program() -> E.EffectGen[int, OopsError]:
        yield from E.fail(OopsError("boom"))
        return 0

    recovered = program().catch_all(lambda e: E.success(len(e.msg)))

    assert E.run_sync(recovered) == E.Succeeded(value=4)


def test_requirements_inside_gen():
    @E.gen
    def program() -> E.EffectGen[int, Never, Db]:
        db = yield from E.require(Db)

        x = yield from E.success(2)
        return db.answer * x

    provided = program().provide(Db)(Db(answer=21))

    assert E.run_sync(provided) == E.Succeeded(value=42)


def test_gen_effects_are_reusable():
    runs: list[int] = []

    @E.gen
    def program() -> E.EffectGen[int]:
        runs.append(1)
        x = yield from E.success(21)
        return x * 2

    p = program()

    assert E.run_sync(p) == E.Succeeded(value=42)
    assert E.run_sync(p) == E.Succeeded(value=42)
    assert runs == [1, 1]


def test_exception_in_generator_body_becomes_a_die():
    err = ValueError("boom")

    @E.gen
    def program() -> E.EffectGen[int]:
        yield from E.success(1)
        raise err

    assert E.run_sync(program()) == E.Failure(cause=E.Die(defect=err))


def test_gen_stack_safety():
    # Each yield from adds an Effect.__iter__ frame; the trampoline must
    # stay flat regardless.
    @E.gen
    def program() -> E.EffectGen[int]:
        total = 0
        for _ in range(10_000):
            total += yield from E.success(1)
        return total

    assert E.run_sync(program()) == E.Succeeded(value=10_000)


def test_fall_off_end_returns_none():
    @E.gen
    def program() -> E.EffectGen[None]:
        yield from E.success(1)

    assert E.run_sync(program()) == E.Succeeded(value=None)


# --- bare yield: works, but the sent value types as Any, so an
# annotation on it is trusted rather than checked ---


def test_bare_yield_still_works():
    @E.gen
    def program() -> E.EffectGen[int, Never, Db]:
        db: Db = yield E.require(Db)

        x: int = yield E.success(2)
        return db.answer * x

    provided = program().provide(Db)(Db(answer=21))

    assert E.run_sync(provided) == E.Succeeded(value=42)


def test_bare_yield_stack_safety():
    @E.gen
    def program() -> E.EffectGen[int]:
        total = 0
        for _ in range(10_000):
            total += yield E.success(1)
        return total

    assert E.run_sync(program()) == E.Succeeded(value=10_000)
