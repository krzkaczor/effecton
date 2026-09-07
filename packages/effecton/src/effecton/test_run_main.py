import asyncio
import logging
import selectors
import signal
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import ClassVar, final

import pytest

import effecton as E


@final
@dataclass(frozen=True)
class InvalidInput(E.EffectonError):
    message: str = "invalid input"

    def __str__(self) -> str:
        return self.message


@final
@dataclass(frozen=True)
class UsageError(E.EffectonError):
    exit_code: ClassVar[int] = 2

    def __str__(self) -> str:
        return "invalid usage"


@pytest.fixture
def reports():
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Capture()
    logger = logging.getLogger("effecton.pretty")
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_success_returns_value_after_cleanup(asynchronous, reports):
    actions = []

    async def value():
        await asyncio.sleep(0)
        return 42

    async def cleanup():
        await asyncio.sleep(0)
        actions.append("closed")

    program = (E.coroutine(value) if asynchronous else E.success(42)).on_exit(
        E.coroutine(cleanup)
    )

    result = E.run_main(program)

    assert result == 42
    assert actions == ["closed"]
    assert reports == []


def test_failure_reports_after_finalizers_and_loop_close(reports):
    loops = []

    @final
    @dataclass(frozen=True)
    class AfterCleanup(E.EffectonError):
        def __str__(self) -> str:
            assert len(loops) == 1
            assert loops[0].is_closed()
            return "invalid input"

    async def cleanup():
        await asyncio.sleep(0)
        loops.append(asyncio.get_running_loop())

    program = E.fail(AfterCleanup()).on_exit(E.coroutine(cleanup))

    with pytest.raises(SystemExit) as info:
        E.run_main(program)

    assert info.value.code == 1
    assert len(loops) == 1
    assert loops[0].is_closed()
    [report] = reports
    assert report.levelno == logging.ERROR
    assert report.getMessage() == "invalid input"


def test_failure_uses_default_logging_settings(reports):
    local_reports = []
    program = E.provide_implicit(
        E.provide_implicit(
            E.annotate_logs(E.fail(InvalidInput()), local=True),
            E.CurrentLoggers((E.EffectonLogger(local_reports.append),)),
        ),
        E.MinimumLogLevel(E.LogLevel.NONE),
    )

    with pytest.raises(SystemExit):
        E.run_main(program)

    assert local_reports == []
    [report] = reports
    assert report.getMessage() == "invalid input"
    assert report.__dict__["effecton_annotations"] == {}


def test_exception_defect_includes_original_traceback_and_chain(reports):
    def crash():
        try:
            raise ValueError("original")
        except ValueError as error:
            raise RuntimeError("outer") from error

    with pytest.raises(SystemExit) as info:
        E.run_main(E.sync(crash))

    assert info.value.code == 1
    [report] = reports
    message = report.getMessage()
    assert message.startswith(
        "Defect occurred: RuntimeError: outer\nTraceback (most recent call last):"
    )
    assert "in crash" in message
    assert "ValueError: original" in message
    assert "direct cause" in message
    assert "RuntimeError: outer" in message


@pytest.mark.parametrize("defect", ["boom", {"reason": "boom"}, None])
def test_non_exception_defect(reports, defect):
    with pytest.raises(SystemExit) as info:
        E.run_main(E.die(defect))

    assert info.value.code == 1
    [report] = reports
    assert report.getMessage() == f"Unhandled defect: {defect!r}"


@pytest.mark.parametrize("as_defect", [False, True])
def test_custom_error_exit_code(reports, as_defect):
    error = UsageError()
    program = E.die(error) if as_defect else E.fail(error)

    with pytest.raises(SystemExit) as info:
        E.run_main(program)

    assert info.value.code == 2
    assert len(reports) == 1


@pytest.mark.parametrize(
    "code, expected", [(7, 7), (0, 0), (True, 1), ("2", 1), (None, 1), (2.5, 1)]
)
def test_defect_exit_code_attribute(reports, code, expected):
    @dataclass
    class Defect:
        exit_code: object

    with pytest.raises(SystemExit) as info:
        E.run_main(E.die(Defect(code)))

    assert info.value.code == expected
    assert len(reports) == 1


@pytest.mark.parametrize(
    "exception",
    [
        KeyboardInterrupt(),
        asyncio.CancelledError(),
        SystemExit(7),
        SystemExit(None),
        SystemExit("stop"),
    ],
)
def test_interruptions_are_quiet_and_finalize(reports, exception):
    actions = []

    def interrupt():
        raise exception

    async def cleanup():
        await asyncio.sleep(0)
        actions.append("closed")

    with pytest.raises(SystemExit) as info:
        E.run_main(E.sync(interrupt).on_exit(E.coroutine(cleanup)))

    if isinstance(exception, SystemExit):
        assert info.value is exception
    else:
        assert info.value.code == 130
    assert actions == ["closed"]
    assert reports == []


@pytest.mark.parametrize("fails", [False, True])
def test_restores_signal_handlers(fails):
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    if fails:
        with pytest.raises(SystemExit):
            E.run_main(E.fail(InvalidInput()))
    else:
        E.run_main(E.success(None))

    assert {sig: signal.getsignal(sig) for sig in before} == before


def test_rejects_running_loop_before_execution():
    actions = []

    async def main():
        with pytest.raises(RuntimeError, match="running event loop"):
            E.run_main(E.sync(lambda: actions.append("ran")))

    asyncio.run(main())

    assert actions == []


def test_rejects_worker_thread_before_execution():
    actions = []

    with ThreadPoolExecutor() as executor:
        future = executor.submit(E.run_main, E.sync(lambda: actions.append("ran")))
        with pytest.raises(RuntimeError, match="main thread"):
            future.result(timeout=5)

    assert actions == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process signal delivery")
@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("phase", ["body", "cleanup", "repeat"])
def test_process_signals_wait_for_cleanup(signum, phase):
    script = textwrap.dedent("""
        import asyncio
        import effecton as E
        import sys

        async def body():
            print("ready", flush=True)
            await asyncio.Event().wait()

        async def cleanup():
            print("cleaning", flush=True)
            await asyncio.to_thread(input)
            await asyncio.sleep(0.05)
            print("cleaned", flush=True)

        program = E.success(None) if sys.argv[1] == "cleanup" else E.coroutine(body)
        E.run_main(program.on_exit(E.coroutine(cleanup)))
    """)

    with subprocess.Popen(
        [sys.executable, "-c", script, phase],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        stdout = process.stdout
        assert stdout is not None

        def expect_line(expected):
            with selectors.DefaultSelector() as selector:
                selector.register(stdout, selectors.EVENT_READ)
                assert selector.select(timeout=10), f"Timed out waiting for {expected}"
            assert stdout.readline().strip() == expected

        try:
            if phase != "cleanup":
                expect_line("ready")
                process.send_signal(signum)
            expect_line("cleaning")
            if phase == "cleanup":
                process.send_signal(signum)
            elif phase == "repeat":
                process.send_signal(
                    signal.SIGTERM if signum == signal.SIGINT else signal.SIGINT
                )
            output, errors = process.communicate(input="finish\n", timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    assert process.returncode == 128 + signum
    assert output == "cleaned\n"
    assert errors == ""
