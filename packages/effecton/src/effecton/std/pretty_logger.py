import logging
import sys
from collections.abc import Mapping
from datetime import datetime
from pprint import pformat
from typing import assert_never, final

from effecton.std.logger import (
    EffectonLogger,
    LogData,
    LogLevel,
    Severity,
    _to_python_logger_level,
)

_ANSI_RESET = "\x1b[0m"
_ANSI_DIM = "\x1b[2m"


def _severity_ansi(level: Severity) -> str:
    match level:
        case LogLevel.TRACE:
            return "\x1b[90m"
        case LogLevel.DEBUG:
            return "\x1b[34m"
        case LogLevel.INFO:
            return "\x1b[32m"
        case LogLevel.WARN:
            return "\x1b[33m"
        case LogLevel.ERROR:
            return "\x1b[31m"
        case LogLevel.FATAL:
            return "\x1b[41;97m"
        case _:
            assert_never(level)


def _severity_for_levelno(levelno: int) -> Severity:
    """Nearest effecton severity for a stdlib level.

    The inverse of _to_python_logger_level.
    """
    if levelno >= logging.CRITICAL:
        return LogLevel.FATAL
    if levelno >= logging.ERROR:
        return LogLevel.ERROR
    if levelno >= logging.WARNING:
        return LogLevel.WARN
    if levelno >= logging.INFO:
        return LogLevel.INFO
    if levelno >= logging.DEBUG:
        return LogLevel.DEBUG
    return LogLevel.TRACE


@final
class PrettyFormatter(logging.Formatter):
    """Formats records as ``[HH:MM:SS.mmm] LEVEL message``.

    Levels render in effecton's severity vocabulary (WARN, FATAL) with a
    color per level; colors=None detects whether stderr is a terminal.
    effecton annotations travel on the record as the effecton_annotations
    attribute (through ``extra``) and each renders as one indented
    ``key: value`` line.
    """

    def __init__(self, *, colors: bool | None = None) -> None:
        super().__init__()
        self._colors = colors

    def format(self, record: logging.LogRecord) -> str:
        use_color = sys.stderr.isatty() if self._colors is None else self._colors

        def paint(code: str, text: str) -> str:
            return f"{code}{text}{_ANSI_RESET}" if use_color else text

        severity = _severity_for_levelno(record.levelno)
        date = datetime.fromtimestamp(record.created)
        stamp = f"{date:%H:%M:%S}.{int(record.msecs):03d}"
        header = (
            f"{paint(_ANSI_DIM, f'[{stamp}]')} "
            f"{paint(_severity_ansi(severity), severity.name)}"
        )
        first, *rest = record.getMessage().split("\n")
        lines = [f"{header} {first}"]
        lines += [f"  {line}" for line in rest]
        annotations = record.__dict__.get("effecton_annotations")
        if isinstance(annotations, Mapping):
            lines += [
                f"  {paint(_ANSI_DIM, f'{key}:')} {value}"
                for key, value in annotations.items()
            ]
        if record.exc_info:
            lines.append(self.formatException(record.exc_info))
        return "\n".join(lines)


_pretty_python_logger = logging.getLogger("effecton.pretty")
# effecton owns filtering, so this logger must pass everything.
_pretty_python_logger.setLevel(1)
_pretty_python_logger.propagate = False
_pretty_handler = logging.StreamHandler()
_pretty_handler.setFormatter(PrettyFormatter())
_pretty_python_logger.addHandler(_pretty_handler)


def _pretty_log(options: LogData) -> None:
    text = " ".join(
        part if isinstance(part, str) else pformat(part, width=80, sort_dicts=False)
        for part in options.message
    )
    _pretty_python_logger.log(
        _to_python_logger_level(options.log_level),
        text,
        extra={"effecton_annotations": options.annotations},
    )


pretty_logger = EffectonLogger(log=_pretty_log)
