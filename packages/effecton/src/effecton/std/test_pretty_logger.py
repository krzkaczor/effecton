import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import final

import effecton as E


@final
@dataclass(frozen=True)
class InstallFailed(E.EffectonError):
    url: str
    status_code: int


@contextmanager
def captured_pretty_records() -> Iterator[list[logging.LogRecord]]:
    """Collect records off the non-propagating "effecton.pretty" logger.

    caplog can't see them because its handler sits on the root logger,
    so the capturing handler goes directly on the pretty logger.
    """
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Capture(level=1)
    target = logging.getLogger("effecton.pretty")
    target.addHandler(handler)
    try:
        yield records
    finally:
        target.removeHandler(handler)


def test_emits_on_the_pretty_logger_with_annotations():
    with captured_pretty_records() as records:
        E.run_sync(E.annotate_logs(E.log_info("hello", 42), user_id=1))

    [record] = records
    assert record.name == "effecton.pretty"
    assert record.levelno == logging.INFO
    assert record.getMessage() == "hello 42"
    assert record.__dict__["effecton_annotations"] == {"user_id": 1}


def test_maps_trace_to_level_5():
    program = E.provide_implicit(E.log_trace("deep"), E.MinimumLogLevel(E.LogLevel.ALL))

    with captured_pretty_records() as records:
        E.run_sync(program)

    [record] = records
    assert record.levelno == 5
    assert record.levelname == "TRACE"


def test_maps_fatal_to_critical():
    with captured_pretty_records() as records:
        E.run_sync(E.log_fatal("boom"))

    [record] = records
    assert record.levelno == logging.CRITICAL


# Verify by eye that the pretty_logger output looks readable: it prints
# straight to stderr, so `uv run pytest` shows it (-s is in addopts).
def test_looks_good():
    error = InstallFailed(url="https://example.com/SKILL.md", status_code=503)
    failure = E.run_sync(E.die(ZeroDivisionError("boom")))
    assert isinstance(failure, E.Failure)

    @E.gen
    def do_log() -> E.EffectGen[None]:
        yield from E.log_trace("interpreter detail")
        yield from E.log_debug("resolving requirement")
        yield from E.log_info("payload:", {"test": 5})
        yield from E.log_info(
            "fetched manifest:",
            {
                "name": "my-skill",
                "description": "Install skills from GitHub with one command",
                "allowed_tools": ["Bash", "Read", "Write", "Edit"],
                "metadata": {"version": "1.2.0", "author": "octo", "stars": 4821},
                "files": [
                    "SKILL.md",
                    "references/usage.md",
                    "references/troubleshooting.md",
                ],
            },
        )
        yield from E.log_debug("error type:", InstallFailed)
        yield from E.log_warning("skill dir already exists")
        yield from E.log_error("install failed:", error)
        yield from E.log_error("as a cause:", E.Fail(error=error))
        yield from E.log_fatal("program died:", failure.cause)
        yield from E.annotate_logs(E.log_fatal("giving up"), user_id=1, request="r-42")

    # pretty_logger is the default CurrentLoggers, so only the level
    # needs providing.
    program = E.provide_implicit(do_log(), E.MinimumLogLevel(E.LogLevel.ALL))

    E.run_sync(program)
