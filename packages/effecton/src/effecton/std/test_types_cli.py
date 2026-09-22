"""Type-level pins for Cli. Nothing here runs: ty checks the function
bodies and pytest never calls them."""

from dataclasses import dataclass
from typing import Annotated, Never, assert_type, final

import effecton as E

Cli = E.Cli


@final
@dataclass(frozen=True)
class AddFailed(E.EffectonError):
    pass


@final
@dataclass(frozen=True)
class StatusFailed(E.EffectonError):
    pass


class Add(Cli.Args):
    package: Annotated[str, Cli.Option(help="Package.")]
    dry_run: bool = False


def run_add(args: Add) -> E.Effect[None, AddFailed, E.FileSystem.Protocol]:
    return E.success(None)


def run_status() -> E.Effect[None, StatusFailed, E.Process.Protocol]:
    return E.success(None)


def _args_are_frozen_keyword_only_dataclasses() -> None:
    args = Add(package="effecton")
    assert_type(args.package, str)
    assert_type(args.dry_run, bool)


def _command_infers_errors_and_requirements_from_the_handler() -> None:
    add = Cli.command("add", args=Add, handler=run_add)
    assert_type(add, Cli.Command[AddFailed, E.FileSystem.Protocol])
    status = Cli.command("status", handler=run_status)
    assert_type(status, Cli.Command[StatusFailed, E.Process.Protocol])
    group = Cli.command("app", help="An app.")
    assert_type(group, Cli.Command[Never, Never])
    quiet = Cli.command("quiet", handler=lambda: E.success(None))
    assert_type(quiet, Cli.Command[Never, Never])


def _with_subcommands_unions_errors_and_requirements() -> None:
    add = Cli.command("add", args=Add, handler=run_add)
    status = Cli.command("status", handler=run_status)
    app = Cli.command("app").with_subcommands(add, status)
    assert_type(
        app,
        Cli.Command[
            AddFailed | StatusFailed, E.FileSystem.Protocol | E.Process.Protocol
        ],
    )


def _run_adds_usage_errors_and_the_process_requirement() -> None:
    add = Cli.command("add", args=Add, handler=run_add)
    app = Cli.command("app").with_subcommands(add)
    assert_type(
        Cli.run(app),
        E.Effect[
            None,
            AddFailed | Cli.UsageError,
            E.FileSystem.Protocol | E.Process.Protocol,
        ],
    )
    runnable = (
        Cli.run(app)
        .provide(E.FileSystem.Protocol)(E.FileSystem.Test())
        .provide(E.Process.Protocol)(E.Process.Test())
    )
    assert_type(runnable, E.Effect[None, AddFailed | Cli.UsageError])


def _catching_usage_error_subtracts_it() -> None:
    add = Cli.command("add", args=Add, handler=run_add)
    app = Cli.command("app").with_subcommands(add)
    caught = Cli.run(app).catch(Cli.UsageError)(lambda e: E.success(None))
    assert_type(
        caught,
        E.Effect[None, AddFailed, E.FileSystem.Protocol | E.Process.Protocol],
    )


def _cli_negative() -> None:
    # A handler must accept the declared Args class.
    def wrong(args: int) -> E.Effect[None]:
        return E.success(None)

    Cli.command("add", args=Add, handler=wrong)  # ty: ignore[invalid-argument-type]

    # A handler must succeed with None.
    Cli.command("add", args=Add, handler=lambda args: E.success(1))  # ty: ignore[invalid-argument-type]

    # Subcommands are commands.
    Cli.command("app").with_subcommands(object())  # ty: ignore[invalid-argument-type]

    # Args instances are frozen.
    Add(package="x").package = "y"  # ty: ignore[invalid-assignment]

    # Only an Args class goes in args=.
    Cli.command("add", args=int, handler=run_add)  # ty: ignore[invalid-argument-type]

    # Command is frozen.
    Cli.command("x").name = "y"  # ty: ignore[invalid-assignment]
