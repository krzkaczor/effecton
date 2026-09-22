"""The curated shape of the reference page: section order and headings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    """One ``##`` section: the source modules it documents, in order.

    Module paths are relative to the root package (``std.clock``). ``extras``
    name objects that are not exported from the package but are reachable
    through return types, such as the binder returned by ``Effect.provide``.
    """

    title: str
    modules: tuple[str, ...]
    extras: tuple[str, ...] = ()


TOPICS: tuple[Topic, ...] = (
    Topic(
        "Effect",
        ("effect", "provide", "catch"),
        extras=("provide.ProvideBinder", "catch.CatchBinder"),
    ),
    Topic("Constructing effects", ("gen", "suspend", "attempt")),
    Topic("Running effects", ("run_sync", "run_async", "run_main", "exit")),
    Topic("Requirements", ("implicit_requirement",)),
    Topic("Scope", ("std.scope",)),
    Topic("Fibers", ("std.fiber", "std.race")),
    Topic(
        "Timing",
        ("std.timeout", "std.retry", "std.schedule", "std.duration"),
        extras=("std.timeout.Timeout", "std.duration.Parts"),
    ),
    Topic("Logging", ("std.logger", "std.pretty_logger")),
    Topic("Path", ("std.path",)),
    Topic("Schema", ("std.schema",)),
    Topic("Cli", ("std.cli",)),
    Topic("Clock", ("std.clock",)),
    Topic("Random", ("std.random",)),
    Topic("FileSystem", ("std.file_system",)),
    Topic("HttpClient", ("std.http_client",)),
    Topic("Process", ("std.process",)),
    Topic("Tracer", ("std.tracer",)),
)
