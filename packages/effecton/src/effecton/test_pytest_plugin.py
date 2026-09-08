import textwrap

import pytest

PLUGIN_TESTS = textwrap.dedent("""
    from dataclasses import dataclass
    from datetime import UTC, datetime, timedelta
    from typing import final

    import effecton as E


    @final
    @dataclass(frozen=True)
    class BoomError(E.EffectonError):
        msg: str


    @E.gen
    def test_passing_effect() -> E.EffectGen[None]:
        x = yield from E.success(1)
        assert x == 1


    @E.gen
    def test_failing_assertion() -> E.EffectGen[None]:
        x = yield from E.success(1)
        assert x == 2


    @E.gen
    def test_typed_failure() -> E.EffectGen[None, BoomError]:
        yield from E.fail(BoomError("boom"))


    @E.gen
    def test_clock_is_provided(test_clock: E.Clock.Test) -> E.EffectGen[None]:
        yield from test_clock.adjust(timedelta(minutes=5))

        now = yield from E.now()

        assert now == datetime(1970, 1, 1, 0, 5, tzinfo=UTC)


    def test_plain_test_still_runs():
        assert True
""")


def test_effect_tests_are_run_and_reported(pytester: pytest.Pytester):
    pytester.makepyfile(PLUGIN_TESTS)

    result = pytester.runpytest("-p", "no:cacheprovider")

    result.assert_outcomes(passed=3, failed=2)
    result.stdout.fnmatch_lines(["*test_failing_assertion*", "*assert 1 == 2*"])
    result.stdout.fnmatch_lines(["*test_typed_failure*", "*BoomError*boom*"])
