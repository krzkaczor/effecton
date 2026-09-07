import asyncio
import signal
import threading
import traceback
from types import FrameType
from typing import assert_never

from effecton.effect import Die, Effect, EffectonError, Fail, Interrupt
from effecton.exit import Failure, Succeeded
from effecton.run_async import run_async_coroutine
from effecton.run_sync import run_sync
from effecton.std.logger import log_error


def run_main[A, E: EffectonError](effect: Effect[A, E]) -> A:
    """Run a main program, returning its value or reporting and exiting.

    Owns a fresh asyncio loop and temporarily handles SIGINT and SIGTERM;
    call only from the main thread, outside an existing event loop. Signals
    cooperatively cancel the program and wait for its finalizers, without
    a cleanup timeout. Blocking synchronous work can delay cancellation.

    Unhandled failures use the default effecton logger, independently of
    program-local logging requirements. Errors and defects exit with their
    integer ``exit_code`` attribute in 0..255, or 1. Interruptions are quiet: SIGTERM
    exits with 143, other interruptions with 130. An explicit SystemExit
    retains its code. Successful integers are values, not exit codes.
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("run_main must be called from the main thread")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("run_main cannot be called from a running event loop")

    first_signal: int | None = None
    previous_handlers = {}
    try:
        with asyncio.Runner() as runner:
            loop = runner.get_loop()
            task = loop.create_task(run_async_coroutine(effect))

            def interrupt(signum: int, frame: FrameType | None) -> None:
                nonlocal first_signal
                if first_signal is None:
                    first_signal = signum
                loop.call_soon_threadsafe(task.cancel)

            for signum in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[signum] = signal.signal(signum, interrupt)
            try:
                outcome = runner.run(task)
            except asyncio.CancelledError, KeyboardInterrupt:
                # Cancellation may arrive before the interpreter starts.
                raise SystemExit(128 + first_signal if first_signal else 130) from None
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

    if first_signal is not None:
        raise SystemExit(128 + first_signal)

    match outcome:
        case Succeeded(value):
            return value
        case Failure(cause):
            match cause:
                case Fail(error):
                    failure = error
                    message = str(error)
                case Die(defect):
                    failure = defect
                    if isinstance(defect, BaseException):
                        description = str(defect)
                        summary = type(defect).__name__
                        if description:
                            summary += f": {description}"
                        trace = "".join(traceback.format_exception(defect)).rstrip()
                        message = f"Defect occurred: {summary}\n{trace}"
                    else:
                        message = f"Unhandled defect: {defect!r}"
                case Interrupt(exception):
                    if isinstance(exception, SystemExit):
                        raise exception
                    raise SystemExit(130)
                case _:
                    assert_never(cause)
            code = getattr(failure, "exit_code", 1)
            run_sync(log_error(message))
            raise SystemExit(
                code
                if isinstance(code, int)
                and not isinstance(code, bool)
                and 0 <= code <= 255
                else 1
            )
        case _:
            assert_never(outcome)
