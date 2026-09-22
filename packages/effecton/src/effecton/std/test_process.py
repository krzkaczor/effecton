import os
import sys

import effecton as E


def test_live_reads_the_working_and_home_directories():
    process = E.Process.Live()

    cwd = E.run_sync(process.cwd())
    home = E.run_sync(process.home())

    assert cwd == E.Path(os.getcwd())
    assert home == E.Path(os.path.expanduser("~"))


def test_live_runs_under_the_async_runner_too():
    result = E.run_async(E.Process.Live().cwd())

    assert result == E.Path(os.getcwd())


def test_test_returns_the_configured_directories():
    process = E.Process.Test(
        current_directory=E.Path("/repo"), home_directory=E.Path("/home/me")
    )

    cwd = E.run_sync(process.cwd())
    home = E.run_sync(process.home())

    assert (cwd, home) == (E.Path("/repo"), E.Path("/home/me"))


def test_test_defaults_to_the_root_and_a_home_directory():
    process = E.Process.Test()

    assert E.run_sync(process.cwd()) == E.Path("/")
    assert E.run_sync(process.home()) == E.Path("/home")


def test_provided_as_a_requirement():
    program = E.require(E.Process.Protocol).flat_map(lambda p: p.cwd())

    result = E.run_sync(
        program.provide(E.Process.Protocol)(
            E.Process.Test(current_directory=E.Path("/repo"))
        )
    )

    assert result == E.Path("/repo")


def test_live_reads_the_command_line_arguments(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "add", "--package", "effecton"])

    result = E.run_sync(E.Process.Live().argv())

    assert result == ("add", "--package", "effecton")


def test_test_returns_the_configured_arguments():
    process = E.Process.Test(arguments=("status",))

    result = E.run_sync(process.argv())

    assert result == ("status",)


def test_test_defaults_to_no_arguments():
    assert E.run_sync(E.Process.Test().argv()) == ()
