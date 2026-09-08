"""pytest plugin that runs test functions written as effects.

Registered through the pytest11 entry point, so it loads wherever
effecton is installed. A test that returns an Effect, typically a
@E.gen generator function, is interpreted with run_async_exit and a
failure raises its cause, so pytest reports a typed error, a defect or
an interruption like any exception. A test that requests the test_clock
fixture has that clock provided to its effect, so E.now(), E.sleep()
and the clock's movers all see the same clock.
"""

import inspect
import warnings
from typing import Any, cast

import pytest

from effecton.effect import Effect
from effecton.exit import unwrap
from effecton.run_async import run_async_exit
from effecton.std import clock


@pytest.fixture
def test_clock() -> clock.Test:
    """A Test clock at the Unix epoch, provided to the test's effect."""
    return clock.Test()


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    function = pyfuncitem.obj
    if inspect.iscoroutinefunction(function):
        return None

    arguments = {
        name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames
    }
    result = function(**arguments)
    if isinstance(result, Effect):
        effect = cast("Effect[Any, Any]", result)
        if "test_clock" in arguments:
            provided = cast("clock.Test", arguments["test_clock"])
            effect = effect.provide(clock.Protocol)(provided)
        unwrap(run_async_exit(effect))
    elif result is not None:
        warnings.warn(
            pytest.PytestReturnNotNoneWarning(
                f"Test functions should return None, "
                f"but {pyfuncitem.nodeid} returned {type(result)!r}"
            ),
            stacklevel=2,
        )
    return True
