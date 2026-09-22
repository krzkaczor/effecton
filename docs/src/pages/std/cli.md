---
title: Cli
description: Declare a command's arguments as an annotated class, parse argv through E.Schema, and run the handler as one effect.
---

# Cli

`E.Cli` replaces typer. A command's arguments are a `Cli.Args` class: a frozen, keyword-only dataclass whose annotations are the decoded types and whose `Annotated` metadata describes the command line. The handler receives the decoded instance and returns an effect. `Cli.run(app)` is itself an effect: it reads the arguments through `E.Process`, prints `--help` and `--version`, and fails with a typed usage error that exits with status 2 under `E.run_main`.

```python
from typing import Annotated, Literal

import effecton as E

Cli = E.Cli
S = E.Schema


class Add(Cli.Args):
    package: Annotated[str, Cli.Option(help="Package the change belongs to.")]
    bump: Annotated[Literal["major", "minor", "patch"], Cli.Option(help="Bump level.")]
    message: Annotated[
        str,
        Cli.Option(
            help="Changelog entry.",
            schema=S.String.check(
                S.filter(
                    lambda m: m.strip() != "", message="expected a non-empty message"
                )
            ),
        ),
    ]
    dry_run: Annotated[
        bool, Cli.Option(short="-n", help="Print instead of writing.")
    ] = False


def run_add(args: Add) -> E.Effect[None]:
    return E.sync(lambda: print(f"{args.package}: {args.bump}"))


def run_status() -> E.Effect[None]:
    return E.sync(lambda: print("No unreleased changesets found."))


# ---cut---
add = Cli.command("add", args=Add, handler=run_add, help="Create a changeset.")
status = Cli.command("status", handler=run_status, help="Show pending changesets.")
app = Cli.command("changeset", help="Changesets for this repo.").with_subcommands(
    add, status
)

program = Cli.run(app)
#  ^?
```

## Arguments

A field is an option (`--package VALUE`) unless its metadata is `Cli.Argument`, which makes it positional. The codec that turns the text into the field's value is inferred from the annotation: `str`, `int`, `float`, `E.Path`, `datetime`, `date` and `Literal[...]` of strings; `bool` is a flag that defaults to `False`; `T | None` is optional with a `None` default; `tuple[T, ...]` collects every occurrence. Any `S.Schema[T, str]` goes in `schema=`, refinements included. Option names default to `--field-name`, arguments to `FIELD_NAME`; `name=`, `short="-x"` and `metavar=` override them. Defaults are plain values, and an instance can be built directly in tests: `Add(package="effecton", bump="patch", message="Fix")`.

## Commands

`Cli.command(name, args=Add, handler=run_add, help=...)` pairs an `Args` class with a handler `Callable[[Add], Effect[None, E, R]]`; without `args=` the handler takes no parameters; without a handler the command is a parent for `with_subcommands(...)`. `E` and `R` are the union across every handler, so the services are provided once, at the root:

```python
import effecton as E

Cli = E.Cli


def run_status() -> E.Effect[None, E.FileSystem.FileNotFound, E.FileSystem.Protocol]:
    return E.success(None)


app = Cli.command("changeset").with_subcommands(
    Cli.command("status", handler=run_status)
)


# ---cut---
def run() -> None:
    E.run_main(
        Cli.run(app)
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
    )
```

`--version` on the root prints the installed version of the distribution that owns the module where the root command was defined, the same way Click's `version_option` finds it, so nothing reads `pyproject.toml` at runtime.

## Usage errors

Parsing fails with `Cli.UsageError`, one error class for every parsing problem, so `effect.catch(Cli.UsageError)(handler)` catches them all. It carries `exit_code = 2` and a `reason` naming what went wrong: `UnknownOption`, `UnknownCommand`, `MissingCommand`, `MissingOptionValue`, `UnexpectedOptionValue`, `UnexpectedArgument` or `InvalidArguments`. `__str__` renders the usage line, a `Try 'changeset add --help' for help.` hint and the reason. `InvalidArguments` holds every schema issue at once:

```
Usage: changeset add [OPTIONS]
Try 'changeset add --help' for help.

Missing option '--package'.
Invalid value for '--bump': expected 'major' | 'minor' | 'patch', got 'big'
```

## Testing

Pin the arguments with `E.Process.Test(arguments=(...))` and run the command with `E.run_sync`, providing `Test` services for everything else; assert on `capsys` for printed output and on the `Exit` for failures.

```python
import effecton as E

Cli = E.Cli


def run_status() -> E.Effect[None]:
    return E.sync(lambda: print("ok"))


app = Cli.command("changeset").with_subcommands(
    Cli.command("status", handler=run_status)
)


# ---cut---
def test_status_runs():
    program = Cli.run(app).provide(E.Process.Protocol)(
        E.Process.Test(arguments=("status",))
    )

    exit = E.run_sync_exit(program)

    assert exit == E.Succeeded(None)
```
