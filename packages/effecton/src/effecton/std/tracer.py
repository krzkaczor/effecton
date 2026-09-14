"""Tracer service: Protocol plus a Live tracer and a recording Test one.

A span marks one named, timed unit of a program. with_span opens a span
around an effect, makes it the parent of every span opened inside, and
ends it with the effect's Exit once the effect settles, on success,
failure, defect and interruption alike. Timestamps come from the Clock
and ids from the Random service, so the Test clock pins durations and
the test_random fixture makes ids reproducible.

The Protocol is an implicit requirement: programs open spans without
declaring anything in R. Live is the default; its spans live only as
long as the program holds them, so tracing costs nothing until a tracer
that exports them is provided. Tests override it with
.provide(Protocol)(Test()), which records every span it opens in spans.
An OpenTelemetry tracer would be another implementation of the Protocol
whose span() returns spans backed by the SDK; the ids are already the
hex forms the W3C traceparent header carries.

The accessors live here as _with_span, _annotate_current_span and
_current_span and are exported only as E.with_span,
E.annotate_current_span and E.current_span, like E.now for the Clock.
"""

import typing
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, final, runtime_checkable

from effecton.effect import (
    Effect,
    EffectonError,
    ProvideRequirement,
    fail,
    success,
    sync,
)
from effecton.exit import Exit
from effecton.gen import EffectGen, gen
from effecton.implicit_requirement import ImplicitRequirement, require_implicit
from effecton.std.clock import _now
from effecton.std.random import _random

type SpanKind = Literal["internal", "server", "client", "producer", "consumer"]


def _with_span[A, E: EffectonError, R](
    effect: Effect[A, E, R],
    name: str,
    *,
    kind: SpanKind = "internal",
    **attributes: object,
) -> Effect[A, E, R]:
    """Open a span around effect and end it with the effect's Exit.

    The span is a child of the current span, if any, and is the current
    span inside effect. It ends on success, failure, defect and
    interruption alike.
    """

    @gen
    def traced() -> EffectGen[A, E, R]:
        tracer = yield from require_implicit(Protocol)
        parent = yield from require_implicit(ParentSpan)

        start_time = yield from _now()
        span = yield from tracer.span(
            name,
            parent=parent.span,
            start_time=start_time,
            kind=kind,
            attributes=attributes,
        )
        # The end time is read inside the finalizer, so an interrupted
        # effect still stamps its span: finalizers are shielded.
        return (
            yield from ProvideRequirement[A, E, R](
                first=effect,
                requirement_type=ParentSpan,
                requirement_impl=ParentSpan(span),
            ).on_exit(
                lambda exit: _now().flat_map(lambda end_time: span.end(end_time, exit))
            )
        )

    return traced()


@gen
def _annotate_current_span(**attributes: object) -> EffectGen[None]:
    """Add attributes to the current span; a no-op outside any span."""
    parent = yield from require_implicit(ParentSpan)

    if parent.span is None:
        return None
    for key, value in attributes.items():
        yield from parent.span.attribute(key, value)
    return None


def _current_span() -> Effect[Span, NoCurrentSpan]:
    """The innermost open span, failing with NoCurrentSpan outside any."""

    def unwrap(parent: ParentSpan) -> Effect[Span, NoCurrentSpan]:
        if parent.span is None:
            return fail(NoCurrentSpan())
        return success(parent.span)

    return require_implicit(ParentSpan).flat_map(unwrap)


@final
@dataclass(frozen=True)
class NoCurrentSpan(EffectonError):
    def __str__(self) -> str:
        return "No span is current; wrap the effect in with_span"


@final
@dataclass(frozen=True)
class Started:
    start_time: datetime


@final
@dataclass(frozen=True)
class Ended:
    start_time: datetime
    end_time: datetime
    exit: Exit[Any, Any]


type SpanStatus = Started | Ended


@runtime_checkable
class Span(typing.Protocol):
    """One named, timed unit of a program, as the Tracer represents it.

    Ids are lowercase hex: 32 characters for the trace, 16 for the span.
    Spans in one tree share the trace id and chain through parent.
    """

    name: str
    trace_id: str
    span_id: str
    parent: Span | None
    kind: SpanKind
    status: SpanStatus
    attributes: Mapping[str, object]

    def end(self, end_time: datetime, exit: Exit[Any, Any]) -> Effect[None]: ...

    def attribute(self, key: str, value: object) -> Effect[None]: ...


@final
@dataclass(eq=False)
class NativeSpan(Span):
    """The in-memory span both bundled tracers open; compares by identity."""

    name: str
    trace_id: str
    span_id: str
    parent: Span | None
    kind: SpanKind
    status: SpanStatus
    attributes: Mapping[str, object]

    def end(self, end_time: datetime, exit: Exit[Any, Any]) -> Effect[None]:
        def go() -> None:
            # Only the first end counts; a span cannot be reopened.
            if isinstance(self.status, Started):
                self.status = Ended(self.status.start_time, end_time, exit)

        return sync(go)

    def attribute(self, key: str, value: object) -> Effect[None]:
        def go() -> None:
            self.attributes = {**self.attributes, key: value}

        return sync(go)


@final
@dataclass(frozen=True)
class ParentSpan(ImplicitRequirement):
    """The span new spans are opened under; None outside any span."""

    span: Span | None

    @classmethod
    def default(cls) -> ParentSpan:
        return ParentSpan(None)


@runtime_checkable
class Protocol(ImplicitRequirement, typing.Protocol):
    def span(
        self,
        name: str,
        *,
        parent: Span | None,
        start_time: datetime,
        kind: SpanKind,
        attributes: Mapping[str, object],
    ) -> Effect[Span]:
        """Open a span; with_span ends it once the wrapped effect settles."""
        ...

    @classmethod
    def default(cls) -> Protocol:
        return Live()


@final
@dataclass(frozen=True)
class Live(Protocol):
    """Opens in-memory spans that nothing collects."""

    def span(
        self,
        name: str,
        *,
        parent: Span | None,
        start_time: datetime,
        kind: SpanKind,
        attributes: Mapping[str, object],
    ) -> Effect[Span]:
        return _new_span(
            name, parent=parent, start_time=start_time, kind=kind, attributes=attributes
        )


@final
@dataclass
class Test(Protocol):
    """Opens the same in-memory spans and records each one in spans."""

    spans: list[Span] = field(default_factory=list, compare=False)

    def span(
        self,
        name: str,
        *,
        parent: Span | None,
        start_time: datetime,
        kind: SpanKind,
        attributes: Mapping[str, object],
    ) -> Effect[Span]:
        def record(span: Span) -> Span:
            self.spans.append(span)
            return span

        return _new_span(
            name, parent=parent, start_time=start_time, kind=kind, attributes=attributes
        ).map(record)


_SPAN_ID_MAX = 2**64 - 1
_TRACE_ID_MAX = 2**128 - 1


@gen
def _new_span(
    name: str,
    *,
    parent: Span | None,
    start_time: datetime,
    kind: SpanKind,
    attributes: Mapping[str, object],
) -> EffectGen[Span]:
    rng = yield from _random()

    span_id = yield from rng.randint(0, _SPAN_ID_MAX)
    if parent is None:
        trace = yield from rng.randint(0, _TRACE_ID_MAX)
        trace_id = f"{trace:032x}"
    else:
        trace_id = parent.trace_id
    return NativeSpan(
        name=name,
        trace_id=trace_id,
        span_id=f"{span_id:016x}",
        parent=parent,
        kind=kind,
        status=Started(start_time),
        attributes=dict(attributes),
    )
