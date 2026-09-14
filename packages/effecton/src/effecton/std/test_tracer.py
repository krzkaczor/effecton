import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import final

import effecton as E

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@final
@dataclass(frozen=True)
class OopsError(E.EffectonError):
    msg: str


def run_traced[A, E_: E.EffectonError](
    effect: E.Effect[A, E_],
) -> tuple[E.Tracer.Test, E.Exit[A, E_]]:
    """Run under a recording tracer and a Test clock stuck at the epoch."""
    tracer = E.Tracer.Test()
    provided = effect.provide(E.Tracer.Protocol)(tracer).provide(E.Clock.Protocol)(
        E.Clock.Test()
    )
    return tracer, E.run_sync_exit(provided)


def test_with_span_records_name_kind_and_attributes():
    program = E.with_span(E.success(42), "work", kind="client", user_id=1)

    tracer, result = run_traced(program)

    assert result == E.Succeeded(42)
    [span] = tracer.spans
    assert (span.name, span.kind, span.attributes) == ("work", "client", {"user_id": 1})


def test_kind_defaults_to_internal():
    tracer, _ = run_traced(E.success(1).with_span("work"))

    [span] = tracer.spans
    assert span.kind == "internal"


def test_nested_spans_share_the_trace_and_chain_parents():
    inner = E.success(1).with_span("inner")
    program = inner.flat_map(lambda _: inner).with_span("outer")

    tracer, _ = run_traced(program)

    outer, first, second = tracer.spans
    assert [s.name for s in tracer.spans] == ["outer", "inner", "inner"]
    assert outer.parent is None
    assert first.parent is outer
    assert second.parent is outer
    assert first.trace_id == second.trace_id == outer.trace_id
    assert len({outer.span_id, first.span_id, second.span_id}) == 3
    assert len(outer.trace_id) == 32
    assert len(outer.span_id) == 16


def test_root_spans_start_distinct_traces():
    program = (
        E.success(1).with_span("a").flat_map(lambda _: E.success(2).with_span("b"))
    )

    tracer, _ = run_traced(program)

    a, b = tracer.spans
    assert a.trace_id != b.trace_id


def test_span_ends_with_the_success_exit():
    tracer, _ = run_traced(E.success(42).with_span("work"))

    [span] = tracer.spans
    assert span.status == E.Tracer.Ended(EPOCH, EPOCH, E.Succeeded(42))


def test_span_ends_with_the_typed_failure_and_leaves_the_exit_alone():
    error = OopsError("boom")

    tracer, result = run_traced(E.fail(error).with_span("work"))

    [span] = tracer.spans
    assert result == E.Failure(cause=E.Fail(error))
    assert span.status == E.Tracer.Ended(EPOCH, EPOCH, E.Failure(cause=E.Fail(error)))


def test_span_ends_with_the_defect():
    defect = ValueError("boom")

    tracer, result = run_traced(E.die(defect).with_span("work"))

    [span] = tracer.spans
    assert result == E.Failure(cause=E.Die(defect))
    assert span.status == E.Tracer.Ended(EPOCH, EPOCH, E.Failure(cause=E.Die(defect)))


@E.gen
def test_span_ends_with_the_interrupt_when_the_fiber_is_interrupted(
    test_tracer: E.Tracer.Test,
) -> E.EffectGen[None]:
    forever = E.coroutine(asyncio.Event().wait).with_span("work")
    fiber = yield from E.fork(forever.provide(E.Tracer.Protocol)(test_tracer))
    yield from E.yield_now()  # let the fiber open its span and park

    outcome = yield from fiber.interrupt()

    [span] = test_tracer.spans
    match (outcome, span.status):
        case (
            E.Failure(E.Interrupt(exception)),
            E.Tracer.Ended(exit=E.Failure(E.Interrupt(recorded))),
        ):
            assert isinstance(exception, asyncio.CancelledError)
            assert recorded is exception
        case other:
            raise AssertionError(other)


@E.gen
def test_span_times_come_from_the_clock(
    test_clock: E.Clock.Test, test_tracer: E.Tracer.Test
) -> E.EffectGen[None]:
    nap = (
        E.sleep(timedelta(minutes=5))
        .with_span("nap")
        .provide(E.Clock.Protocol)(test_clock)
        .provide(E.Tracer.Protocol)(test_tracer)
    )
    fiber = yield from E.fork(nap)

    yield from test_clock.adjust(timedelta(minutes=5))
    yield from fiber.join()

    [span] = test_tracer.spans
    assert span.status == E.Tracer.Ended(
        EPOCH, EPOCH + timedelta(minutes=5), E.Succeeded(None)
    )


def test_annotate_current_span_adds_attributes_and_later_keys_win():
    program = (
        E.annotate_current_span(user="a", request=1)
        .flat_map(lambda _: E.annotate_current_span(user="b"))
        .with_span("work", request=0)
    )

    tracer, _ = run_traced(program)

    [span] = tracer.spans
    assert span.attributes == {"request": 1, "user": "b"}


def test_annotate_current_span_outside_a_span_is_a_noop():
    tracer, result = run_traced(E.annotate_current_span(a=1))

    assert result == E.Succeeded(None)
    assert tracer.spans == []


def test_current_span_returns_the_innermost_span():
    program = E.current_span().with_span("inner").with_span("outer")

    tracer, result = run_traced(program)

    _, inner = tracer.spans
    assert result == E.Succeeded(inner)
    assert inner.name == "inner"


def test_current_span_fails_outside_a_span():
    result = E.run_sync_exit(E.current_span())

    assert result == E.Failure(cause=E.Fail(E.Tracer.NoCurrentSpan()))
    assert str(E.Tracer.NoCurrentSpan()) == (
        "No span is current; wrap the effect in with_span"
    )


def test_the_outer_span_is_current_again_after_the_inner_settles():
    program = (
        E.success(None)
        .with_span("inner")
        .flat_map(lambda _: E.current_span())
        .with_span("outer")
    )

    tracer, result = run_traced(program)

    outer, _ = tracer.spans
    assert result == E.Succeeded(outer)


def test_a_function_opens_a_span_per_call():
    def double(x: int) -> E.Effect[int]:
        return E.with_span(E.success(x * 2), "double")

    tracer, result = run_traced(double(1).flat_map(double))

    assert result == E.Succeeded(4)
    assert [span.name for span in tracer.spans] == ["double", "double"]


def test_span_effects_are_reusable_values():
    tracer = E.Tracer.Test()
    program = E.success(1).with_span("work").provide(E.Tracer.Protocol)(tracer)

    E.run_sync(program)
    E.run_sync(program)

    first, second = tracer.spans
    assert first is not second


def test_live_is_the_default():
    service = E.run_sync(E.require_implicit(E.Tracer.Protocol))

    assert isinstance(service, E.Tracer.Live)
    assert E.Tracer.Protocol.default() == E.Tracer.Live()


def test_live_opens_spans_that_only_the_program_holds():
    span = E.run_sync(E.current_span().with_span("work"))

    assert isinstance(span, E.Tracer.NativeSpan)
    assert isinstance(span.status, E.Tracer.Ended)
    assert span.status.exit == E.Succeeded(span)


def test_ending_a_span_twice_keeps_the_first_end():
    span = E.run_sync(E.current_span().with_span("work"))
    ended = span.status

    E.run_sync(span.end(EPOCH + timedelta(days=1), E.Succeeded(0)))

    assert span.status == ended


def test_ids_are_drawn_through_random():
    def ids(seed: int) -> list[tuple[str, str]]:
        tracer = E.Tracer.Test()
        program = (
            E.success(1)
            .with_span("inner")
            .with_span("outer")
            .provide(E.Tracer.Protocol)(tracer)
            .provide(E.Random.Protocol)(E.Random.Test(seed))
        )
        E.run_sync(program)
        return [(span.trace_id, span.span_id) for span in tracer.spans]

    assert ids(1) == ids(1)
    assert ids(1) != ids(2)


@E.gen
def test_the_test_tracer_fixture_is_provided(
    test_tracer: E.Tracer.Test,
) -> E.EffectGen[None]:
    tracer = yield from E.require_implicit(E.Tracer.Protocol)

    yield from E.success(1).with_span("work")

    assert tracer is test_tracer
    assert [span.name for span in test_tracer.spans] == ["work"]
