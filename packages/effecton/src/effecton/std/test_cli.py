import dataclasses
import importlib.metadata
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, final

import pytest

import effecton as E

Cli = E.Cli
S = E.Schema

type Bump = Literal["major", "minor", "patch"]


class Add(Cli.Args):
    package: Annotated[str, Cli.Option(help="Package the change belongs to.")]
    bump: Annotated[Bump, Cli.Option(help="major, minor, or patch.")]
    message: Annotated[
        str,
        Cli.Option(
            help="Changelog entry for the change.",
            schema=S.String.check(
                S.filter(
                    lambda m: m.strip() != "", message="expected a non-empty message"
                )
            ),
        ),
    ]
    dry_run: Annotated[
        bool, Cli.Option(short="-n", help="Print the changeset instead of writing it.")
    ] = False


class Notes(Cli.Args):
    package: Annotated[str, Cli.Argument(help="Package to print notes for.")]


class Every(Cli.Args):
    text: str
    count: int
    ratio: float
    where: E.Path
    at: datetime
    day: date
    level: Literal["low", "high"]
    port: int | None = None
    tags: tuple[int, ...] = ()
    verbose: bool = False


def test_args_is_a_frozen_keyword_only_dataclass():
    args = Add(package="effecton", bump="patch", message="Fix it")

    with pytest.raises(dataclasses.FrozenInstanceError):
        args.package = "other"  # ty: ignore[invalid-assignment]

    assert args.dry_run is False


def test_args_decodes_the_raw_argv_dict_through_text_codecs():
    raw = {
        "--text": "a",
        "--count": "3",
        "--ratio": "0.5",
        "--where": "docs",
        "--at": "2026-09-22T10:00:00",
        "--day": "2026-09-22",
        "--level": "high",
        "--port": "80",
        "--tags": ["1", "2"],
        "--verbose": True,
    }

    result = E.run_sync(S.decode(Every.__cli_schema__)(raw))

    assert result == Every(
        text="a",
        count=3,
        ratio=0.5,
        where=E.Path("docs"),
        at=datetime(2026, 9, 22, 10),
        day=date(2026, 9, 22),
        level="high",
        port=80,
        tags=(1, 2),
        verbose=True,
    )


def test_absent_keys_take_their_defaults():
    raw = {
        "--text": "a",
        "--count": "3",
        "--ratio": "0.5",
        "--where": "docs",
        "--at": "2026-09-22T10:00:00",
        "--day": "2026-09-22",
        "--level": "high",
    }

    result = E.run_sync(S.decode(Every.__cli_schema__)(raw))

    assert (result.port, result.tags, result.verbose) == (None, (), False)


def test_params_carry_display_names_metavars_and_shapes():
    params = {p.field: p for p in Every.__cli_params__}

    assert params["text"].key == "--text"
    assert params["text"].metavar == "TEXT"
    assert params["count"].metavar == "INTEGER"
    assert params["ratio"].metavar == "FLOAT"
    assert params["where"].metavar == "PATH"
    assert params["at"].metavar == "DATETIME"
    assert params["day"].metavar == "DATE"
    assert params["level"].metavar == "[low|high]"
    assert params["port"].metavar == "INTEGER"
    assert params["tags"].repeated is True
    assert params["verbose"].flag is True
    assert params["verbose"].metavar is None
    add = {p.field: p for p in Add.__cli_params__}
    assert add["message"].metavar == "TEXT"
    assert add["dry_run"].short == "-n"
    assert add["package"].required is True
    assert add["dry_run"].required is False
    notes = Notes.__cli_params__[0]
    assert (notes.key, notes.positional) == ("PACKAGE", True)


def test_default_text_is_the_encoded_default():
    class Defaults(Cli.Args):
        out: E.Path = E.Path("docs/api.md")
        tags: tuple[int, ...] = (1, 2)
        port: int | None = None
        verbose: bool = False
        empty: tuple[str, ...] = ()

    params = {p.field: p for p in Defaults.__cli_params__}

    assert params["out"].default_text == "docs/api.md"
    assert params["tags"].default_text == "1, 2"
    assert params["port"].default_text is None
    assert params["verbose"].default_text is None
    assert params["empty"].default_text is None


def test_explicit_names_override_the_defaults():
    class Named(Cli.Args):
        package: Annotated[str, Cli.Option(name="--pkg", short="-p", metavar="NAME")]
        target: Annotated[str, Cli.Argument(name="DEST")]

    params = {p.field: p for p in Named.__cli_params__}

    assert (params["package"].key, params["package"].metavar) == ("--pkg", "NAME")
    assert params["target"].key == "DEST"


@pytest.mark.parametrize(
    ("define", "message"),
    [
        (
            lambda: type("Bad", (Cli.Args,), {"__annotations__": {"amount": Decimal}}),
            "Bad.amount: no text codec can be inferred for <class 'decimal.Decimal'>; "
            "pass one with Cli.Option(schema=...)",
        ),
        (
            lambda: type("Bad", (Cli.Args,), {"__annotations__": {"n": Literal[1, 2]}}),
            "Bad.n: no text codec can be inferred for typing.Literal[1, 2]; "
            "pass one with Cli.Option(schema=...)",
        ),
        (
            lambda: type("Bad", (Cli.Args,), {"__annotations__": {"f": bool | None}}),
            "Bad.f: no text codec can be inferred for <class 'bool'>; "
            "pass one with Cli.Option(schema=...)",
        ),
        (
            lambda: type(
                "Bad", (Cli.Args,), {"__annotations__": {"f": tuple[bool, ...]}}
            ),
            "Bad.f: no text codec can be inferred for <class 'bool'>; "
            "pass one with Cli.Option(schema=...)",
        ),
        (
            lambda: type("Bad", (Cli.Args,), {"__annotations__": {"dry_run": bool}}),
            "Bad.dry_run: a flag's default must be False",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {"__annotations__": {"dry_run": bool}, "dry_run": True},
            ),
            "Bad.dry_run: a flag's default must be False",
        ),
        (
            lambda: type("Bad", (Cli.Args,), {"__annotations__": {"port": int | None}}),
            "Bad.port: an optional field's default must be None",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {"__annotations__": {"verbose": Annotated[bool, Cli.Argument()]}},
            ),
            "Bad.verbose: Cli.Argument cannot be a flag",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {
                    "__annotations__": {
                        "verbose": Annotated[bool, Cli.Option(metavar="X")]
                    },
                    "verbose": False,
                },
            ),
            "Bad.verbose: a flag takes no metavar",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {
                    "__annotations__": {
                        "verbose": Annotated[bool, Cli.Option(schema=S.String)]
                    },
                    "verbose": False,
                },
            ),
            "Bad.verbose: a flag takes no schema",
        ),
        (
            lambda: type("Bad", (Cli.Args,), {"__annotations__": {"help": str}}),
            "Bad.help: the option name '--help' is reserved",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {
                    "__annotations__": {
                        "v": Annotated[str, Cli.Option(name="--version")]
                    }
                },
            ),
            "Bad.v: the option name '--version' is reserved",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {"__annotations__": {"target": Annotated[str, Cli.Argument(name="")]}},
            ),
            "Bad.target: Argument name must not be empty",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {"__annotations__": {"bump": Annotated[str, Cli.Option(name="-b")]}},
            ),
            "Bad.bump: Option name '-b' must start with '--'",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {"__annotations__": {"bump": Annotated[str, Cli.Option(short="b")]}},
            ),
            "Bad.bump: short flag 'b' must be '-' followed by one character",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {
                    "__annotations__": {
                        "package": str,
                        "pkg": Annotated[str, Cli.Option(name="--package")],
                    }
                },
            ),
            "Bad: fields 'package' and 'pkg' share the wire key '--package'",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {
                    "__annotations__": {
                        "a": Annotated[str, Cli.Option(short="-x")],
                        "b": Annotated[str, Cli.Option(short="-x")],
                    }
                },
            ),
            "Bad: fields 'a' and 'b' share the wire key '-x'",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {
                    "__annotations__": {
                        "files": Annotated[tuple[str, ...], Cli.Argument()],
                        "rest": Annotated[str, Cli.Argument()],
                    }
                },
            ),
            "Bad: argument 'rest' cannot follow the variadic argument 'files'",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {
                    "__annotations__": {
                        "package": Annotated[str, Cli.Argument()],
                        "name": Annotated[str, Cli.Argument()],
                    },
                    "package": "effecton",
                },
            ),
            "Bad: argument 'name' cannot follow the optional argument 'package'",
        ),
        (
            lambda: type(
                "Bad",
                (Cli.Args,),
                {
                    "__annotations__": {
                        "message": Annotated[
                            str,
                            Cli.Option(
                                schema=S.String.check(
                                    S.filter(lambda m: m != "", message="expected text")
                                )
                            ),
                        ]
                    },
                    "message": "",
                },
            ),
            "Bad.message: the default '' does not satisfy its schema: "
            "expected text, got ''",
        ),
    ],
)
def test_definition_time_errors(define, message):
    with pytest.raises(TypeError) as info:
        define()

    assert str(info.value) == message


def test_command_exposes_its_name_and_help():
    add = Cli.command(
        "add", args=Add, handler=lambda args: E.success(None), help="Add."
    )

    assert (add.name, add.help) == ("add", "Add.")


def test_with_subcommands_rejects_a_command_with_a_handler():
    leaf = Cli.command("leaf", handler=lambda: E.success(None))

    with pytest.raises(TypeError) as info:
        leaf.with_subcommands(Cli.command("x"))

    assert str(info.value) == "leaf: a command has either a handler or subcommands"


def test_with_subcommands_can_only_be_set_once():
    app = Cli.command("app").with_subcommands(Cli.command("x"))

    with pytest.raises(TypeError) as info:
        app.with_subcommands(Cli.command("y"))

    assert str(info.value) == "app: subcommands are already set"


def test_with_subcommands_rejects_duplicate_names():
    with pytest.raises(TypeError) as info:
        Cli.command("app").with_subcommands(Cli.command("x"), Cli.command("x"))

    assert str(info.value) == "app: two subcommands are named 'x'"


def test_usage_errors_render_usage_and_a_help_hint():
    error = Cli.UsageError(
        "changeset add",
        "Usage: changeset add [OPTIONS]",
        Cli.UnknownOption("--foo"),
    )

    assert str(error) == (
        "Usage: changeset add [OPTIONS]\n"
        "Try 'changeset add --help' for help.\n"
        "\n"
        "No such option '--foo'."
    )
    assert error.exit_code == 2


def run_cli(command, *argv):
    return E.run_sync_exit(
        Cli.run(command).provide(E.Process.Protocol)(E.Process.Test(arguments=argv))
    )


def recording(received: list):
    def handler(args=None):
        received.append(args)
        return E.success(None)

    return handler


def usage(command_path: str, usage_line: str, reason: str) -> str:
    return f"{usage_line}\nTry '{command_path} --help' for help.\n\n{reason}"


def test_runs_a_leaf_command_with_long_options():
    received = []
    add = Cli.command("add", args=Add, handler=recording(received))

    exit = run_cli(add, "--package", "effecton", "--bump=patch", "--message", "Fix")

    assert exit == E.Succeeded(None)
    assert received == [Add(package="effecton", bump="patch", message="Fix")]


def test_dispatches_through_nested_subcommands():
    received = []
    notes = Cli.command("notes", args=Notes, handler=recording(received))
    app = Cli.command("changeset").with_subcommands(
        Cli.command("show").with_subcommands(notes)
    )

    exit = run_cli(app, "show", "notes", "effecton")

    assert exit == E.Succeeded(None)
    assert received == [Notes(package="effecton")]


def test_runs_a_handler_without_args():
    received = []
    status = Cli.command("status", handler=recording(received))

    exit = run_cli(status)

    assert exit == E.Succeeded(None)
    assert received == [None]


def test_short_flags_flags_and_repeated_options():
    class Opts(Cli.Args):
        tags: Annotated[tuple[int, ...], Cli.Option(short="-t")] = ()
        name: str = "a"
        verbose: Annotated[bool, Cli.Option(short="-v")] = False

    received = []
    cmd = Cli.command("x", args=Opts, handler=recording(received))

    exit = run_cli(cmd, "-t", "1", "--tags", "2", "-v", "--name", "b", "--name", "c")

    assert exit == E.Succeeded(None)
    assert received == [Opts(tags=(1, 2), name="c", verbose=True)]


def test_positionals_optional_and_variadic():
    class Files(Cli.Args):
        first: Annotated[str, Cli.Argument()]
        second: Annotated[str, Cli.Argument()] = "none"
        rest: Annotated[tuple[str, ...], Cli.Argument()] = ()

    received = []
    cmd = Cli.command("x", args=Files, handler=recording(received))

    only_first = run_cli(cmd, "a")
    every = run_cli(cmd, "a", "b", "c", "d")

    assert (only_first, every) == (E.Succeeded(None), E.Succeeded(None))
    assert received == [
        Files(first="a"),
        Files(first="a", second="b", rest=("c", "d")),
    ]


def test_double_dash_ends_option_parsing():
    received = []
    cmd = Cli.command("x", args=Notes, handler=recording(received))

    exit = run_cli(cmd, "--", "--not-an-option")

    assert exit == E.Succeeded(None)
    assert received == [Notes(package="--not-an-option")]


def test_an_option_value_may_start_with_a_dash():
    received = []
    cmd = Cli.command("add", args=Add, handler=recording(received))

    exit = run_cli(cmd, "--package", "-x", "--bump", "patch", "--message", "m")

    assert received == [Add(package="-x", bump="patch", message="m")]
    assert exit == E.Succeeded(None)


def test_a_handler_failure_is_the_effects_failure():
    @dataclasses.dataclass(frozen=True)
    class Boom(E.EffectonError):
        pass

    cmd = Cli.command("x", handler=lambda: E.fail(Boom()))

    exit = run_cli(cmd)

    assert exit == E.Failure(E.Fail(Boom()))


ADD_USAGE = "Usage: changeset add [OPTIONS]"
ROOT_USAGE = "Usage: changeset [OPTIONS] COMMAND [ARGS]..."


def changeset_app(received):
    add = Cli.command("add", args=Add, handler=recording(received))
    notes = Cli.command("notes", args=Notes, handler=recording(received))
    return Cli.command("changeset").with_subcommands(add, notes)


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        ((), Cli.UsageError("changeset", ROOT_USAGE, Cli.MissingCommand())),
        (
            ("--bogus",),
            Cli.UsageError("changeset", ROOT_USAGE, Cli.UnknownOption("--bogus")),
        ),
        (
            ("--bogus=1",),
            Cli.UsageError("changeset", ROOT_USAGE, Cli.UnknownOption("--bogus")),
        ),
        (
            ("remove",),
            Cli.UsageError("changeset", ROOT_USAGE, Cli.UnknownCommand("remove")),
        ),
        (
            ("add", "--foo", "1"),
            Cli.UsageError("changeset add", ADD_USAGE, Cli.UnknownOption("--foo")),
        ),
        (
            ("add", "-xvalue"),
            Cli.UsageError("changeset add", ADD_USAGE, Cli.UnknownOption("-xvalue")),
        ),
        (
            ("add", "-1"),
            Cli.UsageError("changeset add", ADD_USAGE, Cli.UnknownOption("-1")),
        ),
        (
            ("add", "--package"),
            Cli.UsageError(
                "changeset add", ADD_USAGE, Cli.MissingOptionValue("--package")
            ),
        ),
        (
            ("add", "--dry-run=yes"),
            Cli.UsageError(
                "changeset add",
                ADD_USAGE,
                Cli.UnexpectedOptionValue("--dry-run", "yes"),
            ),
        ),
        (
            ("notes", "effecton", "extra"),
            Cli.UsageError(
                "changeset notes",
                "Usage: changeset notes [OPTIONS] PACKAGE",
                Cli.UnexpectedArgument("extra"),
            ),
        ),
    ],
)
def test_usage_errors(argv, error):
    exit = run_cli(changeset_app([]), *argv)

    assert exit == E.Failure(E.Fail(error))


def test_catch_usage_error_covers_every_reason():
    program = Cli.run(changeset_app([])).catch(Cli.UsageError)(
        lambda e: E.success(e.reason)
    )

    reason = E.run_sync(
        program.provide(E.Process.Protocol)(E.Process.Test(arguments=("remove",)))
    )

    assert isinstance(reason, Cli.UnknownCommand)
    match reason:
        case Cli.UnknownCommand(name=name):
            assert name == "remove"
        case _:
            pytest.fail("expected Cli.UnknownCommand")


def test_invalid_arguments_reports_every_issue():
    exit = run_cli(changeset_app([]), "add", "--bump", "big", "--message", " ")

    assert exit == E.Failure(
        E.Fail(
            Cli.UsageError(
                "changeset add",
                ADD_USAGE,
                Cli.InvalidArguments(
                    (
                        S.MissingKey(("--package",)),
                        S.TypeMismatch(
                            ("--bump",), "'major' | 'minor' | 'patch'", "big"
                        ),
                        S.RefinementFailed(
                            ("--message",), "expected a non-empty message", " "
                        ),
                    )
                ),
            )
        )
    )


def test_invalid_arguments_renders_missing_and_invalid_lines():
    error = Cli.UsageError(
        "changeset add",
        ADD_USAGE,
        Cli.InvalidArguments(
            (
                S.MissingKey(("--package",)),
                S.MissingKey(("PACKAGE",)),
                S.TypeMismatch(("--bump",), "'major' | 'minor' | 'patch'", "big"),
                S.TransformFailed(("--tags", 1), "expected an integer string", "x"),
            )
        ),
    )

    assert str(error) == usage(
        "changeset add",
        ADD_USAGE,
        "Missing option '--package'.\n"
        "Missing argument 'PACKAGE'.\n"
        "Invalid value for '--bump': expected 'major' | 'minor' | 'patch', got 'big'\n"
        "Invalid value for '--tags': [1]: expected an integer string, got 'x'",
    )


def test_usage_line_lists_positionals():
    class Files(Cli.Args):
        first: Annotated[str, Cli.Argument()]
        second: Annotated[str, Cli.Argument()] = "none"
        rest: Annotated[tuple[str, ...], Cli.Argument()] = ()

    cmd = Cli.command("cp", args=Files, handler=lambda a: E.success(None))

    exit = run_cli(cmd, "--nope")

    assert exit == E.Failure(
        E.Fail(
            Cli.UsageError(
                "cp",
                "Usage: cp [OPTIONS] FIRST [SECOND] [REST]...",
                Cli.UnknownOption("--nope"),
            )
        )
    )


ADD_HELP = """\
Usage: changeset add [OPTIONS]

Create a changeset from the given package, bump level, and message.

Options:
  --package TEXT              Package the change belongs to. [required]
  --bump [major|minor|patch]  major, minor, or patch. [required]
  --message TEXT              Changelog entry for the change. [required]
  -n, --dry-run               Print the changeset instead of writing it.
  --help                      Show this message and exit.
"""

ROOT_HELP = """\
Usage: changeset [OPTIONS] COMMAND [ARGS]...

Changeset-based changelog and version management.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  add      Create a changeset from the given package, bump level, and message.
  status   Show pending changesets and the releases they would produce.
  version  Apply pending changesets: bump versions and update changelogs.
  notes    Print the latest released CHANGELOG section for a package.
"""


def documented_app():
    quiet = lambda *args: E.success(None)  # noqa: E731
    return Cli.command(
        "changeset", help="Changeset-based changelog and version management."
    ).with_subcommands(
        Cli.command(
            "add",
            args=Add,
            handler=quiet,
            help="Create a changeset from the given package, bump level, and message.",
        ),
        Cli.command(
            "status",
            handler=quiet,
            help="Show pending changesets and the releases they would produce.",
        ),
        Cli.command(
            "version",
            handler=quiet,
            help="Apply pending changesets: bump versions and update changelogs.",
        ),
        Cli.command(
            "notes",
            args=Notes,
            handler=quiet,
            help="Print the latest released CHANGELOG section for a package.",
        ),
    )


def test_leaf_help_is_rendered_exactly(capsys):
    exit = run_cli(documented_app(), "add", "--help")

    assert exit == E.Succeeded(None)
    assert capsys.readouterr().out == ADD_HELP


def test_root_help_is_rendered_exactly(capsys):
    exit = run_cli(documented_app(), "--help")

    assert exit == E.Succeeded(None)
    assert capsys.readouterr().out == ROOT_HELP


def test_help_wins_over_other_tokens(capsys):
    exit = run_cli(documented_app(), "add", "--bogus", "--help")

    assert exit == E.Succeeded(None)
    assert capsys.readouterr().out == ADD_HELP


def test_help_after_double_dash_is_positional():
    exit = run_cli(documented_app(), "notes", "--", "--help")

    assert exit == E.Succeeded(None)


def test_arguments_section_and_defaults(capsys):
    class Copy(Cli.Args):
        source: Annotated[E.Path, Cli.Argument(help="What to copy.")]
        dest: Annotated[E.Path, Cli.Argument(help="Where to.")] = E.Path("out")
        tags: Annotated[tuple[str, ...], Cli.Option(help="Tags.")] = ("a", "b")
        port: Annotated[int | None, Cli.Option(help="Port.")] = None
        secret: str = "s"

    cmd = Cli.command("cp", args=Copy, handler=lambda a: E.success(None), help="Copy.")

    run_cli(cmd, "--help")

    assert capsys.readouterr().out == (
        "Usage: cp [OPTIONS] SOURCE [DEST]\n"
        "\n"
        "Copy.\n"
        "\n"
        "Arguments:\n"
        "  SOURCE  What to copy. [required]\n"
        "  DEST    Where to. [default: out]\n"
        "\n"
        "Options:\n"
        "  --tags TEXT     Tags. [default: a, b]\n"
        "  --port INTEGER  Port.\n"
        "  --secret TEXT   [default: s]\n"
        "  --version       Show the version and exit.\n"
        "  --help          Show this message and exit.\n"
    )


def test_a_command_with_neither_handler_nor_subcommands_prints_help(capsys):
    exit = run_cli(Cli.command("empty", help="Nothing yet."), "anything")

    assert exit == E.Succeeded(None)
    assert capsys.readouterr().out == (
        "Usage: empty [OPTIONS]\n\nNothing yet.\n\nOptions:\n"
        "  --version  Show the version and exit.\n"
        "  --help     Show this message and exit.\n"
    )


def test_version_prints_the_distribution_version(capsys):
    exit = run_cli(documented_app(), "--version")

    assert exit == E.Succeeded(None)
    assert (
        capsys.readouterr().out
        == f"changeset {importlib.metadata.version('effecton')}\n"
    )


def test_version_on_a_subcommand_is_an_unknown_option():
    exit = run_cli(documented_app(), "add", "--version")

    assert exit == E.Failure(
        E.Fail(
            Cli.UsageError("changeset add", ADD_USAGE, Cli.UnknownOption("--version"))
        )
    )


def test_version_dies_when_no_distribution_owns_the_module():
    root = Cli.Command("prog", "", "__main__", None, None, ())

    exit = run_cli(root, "--version")

    assert isinstance(exit, E.Failure)
    assert isinstance(exit.cause, E.Die)
    assert str(exit.cause.defect) == (
        "prog: cannot determine the version: module '__main__' belongs to no "
        "installed distribution"
    )


def test_run_main_returns_none_and_prints_nothing_on_success(capsys):
    program = Cli.run(documented_app()).provide(E.Process.Protocol)(
        E.Process.Test(
            arguments=(
                "add",
                "--package",
                "effecton",
                "--bump",
                "patch",
                "--message",
                "m",
            )
        )
    )

    result = E.run_main(program)

    assert result is None
    assert capsys.readouterr().out == ""


def test_run_main_exits_2_on_a_usage_error():
    program = Cli.run(documented_app()).provide(E.Process.Protocol)(
        E.Process.Test(arguments=("bogus",))
    )

    with pytest.raises(SystemExit) as info:
        E.run_main(program)

    assert info.value.code == 2


def test_run_main_exits_1_on_a_handler_failure():
    @final
    @dataclasses.dataclass(frozen=True)
    class Boom(E.EffectonError):
        def __str__(self) -> str:
            return "boom"

    cmd = Cli.command("x", handler=lambda: E.fail(Boom()))
    program = Cli.run(cmd).provide(E.Process.Protocol)(E.Process.Test(arguments=()))

    with pytest.raises(SystemExit) as info:
        E.run_main(program)

    assert info.value.code == 1
