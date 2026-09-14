"""Type-level pins for the Tracer service. Nothing here runs: ty checks the
function bodies and pytest never calls them."""

from dataclasses import dataclass
from typing import Literal, Never, assert_type, final

import effecton as E


@final
@dataclass(frozen=True)
class ParseError(E.EffectonError):
    value: str


@dataclass(frozen=True)
class Db:
    url: str


def parse(text: str) -> E.Effect[int, ParseError]:
    return E.success(len(text))


def _with_span_preserves_all_three_channels() -> None:
    assert_type(E.with_span(E.success(1), "x"), E.Effect[Literal[1]])
    assert_type(
        E.with_span(parse("1"), "x", kind="server", user_id=1),
        E.Effect[int, ParseError],
    )
    assert_type(E.with_span(E.require(Db), "x"), E.Effect[Db, Never, Db])

    # The method form is the same combinator.
    assert_type(parse("1").with_span("x"), E.Effect[int, ParseError])
    assert_type(E.require(Db).with_span("x", kind="client"), E.Effect[Db, Never, Db])


def _accessors_are_implicit_reads_so_r_stays_never() -> None:
    assert_type(E.annotate_current_span(user_id=1), E.Effect[None])
    assert_type(E.current_span(), E.Effect[E.Tracer.Span, E.Tracer.NoCurrentSpan])
    assert_type(E.require_implicit(E.Tracer.Protocol), E.Effect[E.Tracer.Protocol])
    assert_type(E.run_sync(E.current_span().with_span("x")), E.Tracer.Span)

    # NoCurrentSpan is a leaf error, so catch subtracts it completely.
    recovered = E.current_span().catch(E.Tracer.NoCurrentSpan)(
        lambda _: E.success(None)
    )
    assert_type(recovered, E.Effect[E.Tracer.Span | None])


def _provide_any_implementation_overrides_the_default() -> None:
    traced = E.success(1).with_span("x")
    assert_type(
        traced.provide(E.Tracer.Protocol)(E.Tracer.Test()), E.Effect[Literal[1]]
    )
    assert_type(
        traced.provide(E.Tracer.Protocol)(E.Tracer.Live()), E.Effect[Literal[1]]
    )


def _tracer_negative() -> None:
    # The kind is one of the five span kinds and the name is a str.
    E.with_span(E.success(1), "x", kind="bogus")  # ty: ignore[invalid-argument-type]
    E.with_span(E.success(1), 1)  # ty: ignore[invalid-argument-type]

    # The effect comes first, as in annotate_logs.
    E.with_span("x", E.success(1))  # ty: ignore[invalid-argument-type]

    # Only a Tracer implementation can be provided as the Tracer.
    E.success(1).with_span("x").provide(E.Tracer.Protocol)(object())  # ty: ignore[invalid-argument-type]

    # Implementations and the error are leaves: none can be subclassed.
    class CustomLive(E.Tracer.Live):  # ty: ignore[subclass-of-final-class]
        pass

    class CustomTest(E.Tracer.Test):  # ty: ignore[subclass-of-final-class]
        pass

    class CustomSpan(E.Tracer.NativeSpan):  # ty: ignore[subclass-of-final-class]
        pass

    class CustomError(E.Tracer.NoCurrentSpan):  # ty: ignore[subclass-of-final-class]
        pass
