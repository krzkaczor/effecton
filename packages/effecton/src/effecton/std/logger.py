import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, assert_never, final

from effecton.effect import Effect, EffectonError, ProvideRequirement
from effecton.gen import EffectGen, gen
from effecton.implicit_requirement import ImplicitRequirement, require_implicit


@final
class LogLevel(Enum):
    ALL = "all"
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"
    NONE = "none"


type Severity = Literal[
    LogLevel.TRACE,
    LogLevel.DEBUG,
    LogLevel.INFO,
    LogLevel.WARN,
    LogLevel.ERROR,
    LogLevel.FATAL,
]
"""Levels a message can be logged at.

Excludes the ALL and NONE sentinels, which are only meaningful as a
MinimumLogLevel threshold: ALL passes everything, NONE silences everything.
"""


def log_level_order(level: LogLevel) -> int:
    """Position in the severity ordering; only relative order matters."""
    match level:
        case LogLevel.ALL:
            return 0
        case LogLevel.TRACE:
            return 1
        case LogLevel.DEBUG:
            return 2
        case LogLevel.INFO:
            return 3
        case LogLevel.WARN:
            return 4
        case LogLevel.ERROR:
            return 5
        case LogLevel.FATAL:
            return 6
        case LogLevel.NONE:
            return 7
        case _:
            assert_never(level)


@final
@dataclass(frozen=True)
class LogData:
    message: tuple[object, ...]
    log_level: Severity
    date: datetime
    annotations: Mapping[str, object]


@final
@dataclass(frozen=True)
class EffectonLogger:
    log: Callable[[LogData], None]


_TRACE_LEVEL = 5
logging.addLevelName(_TRACE_LEVEL, "TRACE")


def _to_python_logger_level(level: Severity) -> int:
    match level:
        case LogLevel.TRACE:
            return _TRACE_LEVEL
        case LogLevel.DEBUG:
            return logging.DEBUG
        case LogLevel.INFO:
            return logging.INFO
        case LogLevel.WARN:
            return logging.WARNING
        case LogLevel.ERROR:
            return logging.ERROR
        case LogLevel.FATAL:
            return logging.CRITICAL
        case _:
            assert_never(level)


@final
@dataclass(frozen=True)
class CurrentLoggers(ImplicitRequirement):
    loggers: tuple[EffectonLogger, ...]

    @classmethod
    def default(cls) -> CurrentLoggers:
        from effecton.std.pretty_logger import pretty_logger

        return CurrentLoggers((pretty_logger,))


@final
@dataclass(frozen=True)
class MinimumLogLevel(ImplicitRequirement):
    level: LogLevel

    @classmethod
    def default(cls) -> MinimumLogLevel:
        return MinimumLogLevel(LogLevel.INFO)


@final
@dataclass(frozen=True)
class CurrentLogLevel(ImplicitRequirement):
    """The level a bare log(...) call logs at."""

    level: Severity

    @classmethod
    def default(cls) -> CurrentLogLevel:
        return CurrentLogLevel(LogLevel.INFO)


@final
@dataclass(frozen=True)
class CurrentLogAnnotations(ImplicitRequirement):
    annotations: Mapping[str, object]

    @classmethod
    def default(cls) -> CurrentLogAnnotations:
        return CurrentLogAnnotations({})


@gen
def _log_with_level(
    level: Severity | None, message: tuple[object, ...]
) -> EffectGen[None]:
    minimum = yield from require_implicit(MinimumLogLevel)
    log_level = (
        level
        if level is not None
        else (yield from require_implicit(CurrentLogLevel)).level
    )

    if log_level_order(log_level) < log_level_order(minimum.level):
        return None

    loggers = yield from require_implicit(CurrentLoggers)
    annotations = yield from require_implicit(CurrentLogAnnotations)

    date = datetime.now()
    for logger in loggers.loggers:
        logger.log(
            LogData(
                message=message,
                log_level=log_level,
                date=date,
                annotations=annotations.annotations,
            )
        )
    return None


def log(*message: object) -> Effect[None]:
    return _log_with_level(None, message)


def log_trace(*message: object) -> Effect[None]:
    return _log_with_level(LogLevel.TRACE, message)


def log_debug(*message: object) -> Effect[None]:
    return _log_with_level(LogLevel.DEBUG, message)


def log_info(*message: object) -> Effect[None]:
    return _log_with_level(LogLevel.INFO, message)


def log_warning(*message: object) -> Effect[None]:
    return _log_with_level(LogLevel.WARN, message)


def log_error(*message: object) -> Effect[None]:
    return _log_with_level(LogLevel.ERROR, message)


def log_fatal(*message: object) -> Effect[None]:
    return _log_with_level(LogLevel.FATAL, message)


def annotate_logs[A, E: EffectonError, R](
    effect: Effect[A, E, R], **annotations: object
) -> Effect[A, E, R]:
    """Merge annotations into every log call inside the wrapped effect."""
    return require_implicit(CurrentLogAnnotations).flat_map(
        lambda current: ProvideRequirement(
            first=effect,
            requirement_type=CurrentLogAnnotations,
            requirement_impl=CurrentLogAnnotations(
                {**current.annotations, **annotations}
            ),
        )
    )
