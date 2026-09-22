"""Cli: declare a command's arguments as an annotated class, then parse argv
through Schema and run the handler as an effect.

An Args subclass is a frozen keyword-only dataclass: annotations are the
decoded types and Annotated metadata (Option, Argument) describes the
command line. Each field gets a text codec, a Schema whose wire side is
str, so the arguments decode like any other struct and every problem is
reported together as one usage error. Commands nest with
with_subcommands, and run(command) is one Effect that reads argv through
E.Process, prints help and the version, and fails with a UsageError that
exits with status 2 under run_main.
"""

import dataclasses
import importlib.metadata
import sys
import typing
from collections.abc import Callable
from dataclasses import MISSING, dataclass
from datetime import date, datetime
from types import NoneType, UnionType
from typing import (
    Any,
    ClassVar,
    Generic,
    Never,
    TypeAliasType,
    TypeVar,
    dataclass_transform,
    final,
    overload,
)

from effecton.effect import Effect, EffectonError, fail, require, sync
from effecton.std import process
from effecton.std import schema as S
from effecton.std.path import Path


def run[E: EffectonError, R](
    command: Command[E, R],
) -> Effect[None, E | UsageError, R | process.Protocol]:
    """Read argv through E.Process, parse it against the command tree, run the handler.

    --help prints the command's help and --version, on the root, its
    distribution's version; both succeed. A parsing problem fails with a
    UsageError, which exits with status 2 under run_main.
    """
    return (
        require(process.Protocol)
        .flat_map(lambda p: p.argv())
        .flat_map(lambda argv: _dispatch(command, [command.name], list(argv), command))
    )


@overload
def command[T: Args, E: EffectonError, R](
    name: str,
    *,
    help: str = "",
    args: type[T],
    handler: Callable[[T], Effect[None, E, R]],
) -> Command[E, R]: ...


@overload
def command[E: EffectonError, R](
    name: str, *, help: str = "", handler: Callable[[], Effect[None, E, R]]
) -> Command[E, R]: ...


@overload
def command(name: str, *, help: str = "") -> Command[Never, Never]: ...


def command(
    name: str,
    *,
    help: str = "",
    args: type[Args] | None = None,
    handler: Callable[..., Effect[None, Any, Any]] | None = None,
) -> Command[Any, Any]:
    """A command: a handler over an Args class, a handler alone, or a parent
    for with_subcommands. The caller's module is recorded for --version."""
    module = sys._getframe(1).f_globals.get("__name__", "__main__")
    return Command(name, help, module, args, handler, ())


# Old-style TypeVars declare the covariance ty cannot infer for a class that
# refers to itself in with_subcommands; see the ty notes in CLAUDE.md.
_E = TypeVar("_E", bound=EffectonError, covariant=True)
_R = TypeVar("_R", covariant=True)


@final
@dataclass(frozen=True)
class Command(Generic[_E, _R]):  # noqa: UP046
    """A named command: E and R are the union over every handler beneath it."""

    name: str
    help: str
    _module: str
    _args: type[Args] | None
    _handler: Callable[..., Effect[None, Any, Any]] | None
    _subcommands: tuple[Command[Any, Any], ...]

    def with_subcommands[E2: EffectonError, R2](
        self, *commands: Command[E2, R2]
    ) -> Command[_E | E2, _R | R2]:
        """A copy of this command that dispatches to the given subcommands."""
        if self._handler is not None:
            raise TypeError(
                f"{self.name}: a command has either a handler or subcommands"
            )
        if self._subcommands:
            raise TypeError(f"{self.name}: subcommands are already set")
        seen: set[str] = set()
        for sub in commands:
            if sub.name in seen:
                raise TypeError(f"{self.name}: two subcommands are named {sub.name!r}")
            seen.add(sub.name)
        return Command(self.name, self.help, self._module, None, None, commands)


@final
@dataclass(frozen=True)
class Option:
    """Annotated metadata for an option field: --name VALUE, or a flag for bool."""

    help: str = ""
    name: str | None = None
    short: str | None = None
    metavar: str | None = None
    schema: S.Schema[Any, str] | None = None


@final
@dataclass(frozen=True)
class Argument:
    """Annotated metadata for a positional argument field."""

    help: str = ""
    name: str | None = None
    metavar: str | None = None
    schema: S.Schema[Any, str] | None = None


@dataclass_transform(frozen_default=True, kw_only_default=True)
class Args:
    """Subclass to declare a command's arguments: annotations are the decoded types.

    Every subclass becomes a frozen, keyword-only dataclass. A field is an
    option unless its Annotated metadata is Argument; both carry help text,
    names and an optional explicit text codec (a Schema whose wire side is
    str). str, int, float, E.Path, datetime, date and Literal[str...] infer
    theirs; bool is a flag; T | None is optional; tuple[T, ...] repeats.
    """

    __cli_params__: ClassVar[tuple[_Param, ...]]
    __cli_schema__: ClassVar[S.Schema[Any, dict[str, object]]]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        dataclass(frozen=True, kw_only=True)(cls)
        cls.__cli_params__ = _plan_params(cls)
        by_field = {p.field: p for p in cls.__cli_params__}

        def resolve(
            f: dataclasses.Field[Any], hint: Any, where: str
        ) -> tuple[str, S.Schema[Any, Any]]:
            param = by_field[f.name]
            return (param.key, param.codec)

        cls.__cli_schema__ = S._struct_schema(cls, resolve)


@final
@dataclass(frozen=True)
class UsageError(EffectonError):
    """The command line could not be parsed; reason says why.

    Exits with 2 under run_main.
    """

    command: str  # the command path, "changeset add"
    usage: str  # that command's usage line
    reason: UsageReason
    exit_code: ClassVar[int] = 2

    def __str__(self) -> str:
        return f"{self.usage}\nTry '{self.command} --help' for help.\n\n{self.reason}"


type UsageReason = (
    UnknownOption
    | UnknownCommand
    | MissingCommand
    | MissingOptionValue
    | UnexpectedOptionValue
    | UnexpectedArgument
    | InvalidArguments
)


@final
@dataclass(frozen=True)
class UnknownOption:
    option: str

    def __str__(self) -> str:
        return f"No such option '{self.option}'."


@final
@dataclass(frozen=True)
class UnknownCommand:
    name: str

    def __str__(self) -> str:
        return f"No such command '{self.name}'."


@final
@dataclass(frozen=True)
class MissingCommand:
    def __str__(self) -> str:
        return "Missing command."


@final
@dataclass(frozen=True)
class MissingOptionValue:
    option: str

    def __str__(self) -> str:
        return f"Option '{self.option}' requires a value."


@final
@dataclass(frozen=True)
class UnexpectedOptionValue:
    option: str
    value: str

    def __str__(self) -> str:
        return f"Option '{self.option}' does not take a value."


@final
@dataclass(frozen=True)
class UnexpectedArgument:
    argument: str

    def __str__(self) -> str:
        return f"Got unexpected extra argument '{self.argument}'."


@final
@dataclass(frozen=True)
class InvalidArguments:
    issues: tuple[S.Issue, ...]

    def __str__(self) -> str:
        def describe(issue: S.Issue) -> str:
            head, *rest = issue.path
            if isinstance(issue, S.MissingKey):
                kind = "option" if str(head).startswith("--") else "argument"
                return f"Missing {kind} '{head}'."
            body = str(dataclasses.replace(issue, path=tuple(rest)))
            return f"Invalid value for '{head}': {body}"

        return "\n".join(describe(issue) for issue in self.issues)


@dataclass(frozen=True)
class _Param:
    """One field of an Args class as the command line sees it."""

    field: str
    key: str  # display name and wire key: "--package" or "PACKAGE"
    short: str | None
    help: str
    metavar: str | None  # None for a flag
    codec: S.Schema[Any, Any]
    positional: bool
    flag: bool
    repeated: bool
    required: bool
    default_text: str | None


def _plan_params(cls: type[Any]) -> tuple[_Param, ...]:
    def _metavar_for(annotation: Any) -> str | None:
        """The metavar inferable for an annotation, or None when it has none.

        Used for a field with an explicit schema=: the annotation still picks
        the metavar when it is one of the standard inferable types, falling
        back to VALUE only when it is not (which is also why a schema was
        required).
        """
        try:
            return _text_codec(annotation, "")[1]
        except TypeError:
            return None

    def _optional(codec: S.Schema[Any, Any]) -> S.Schema[Any, Any]:
        """Decode as the codec does (the wire never carries None); encode as None."""

        def encode(value: Any, path: S.IssuePath) -> Any:
            return None if value is None else codec._encode(value, path)

        return S.Schema(codec._decode, encode)

    hints = typing.get_type_hints(cls, include_extras=True)
    params: list[_Param] = []
    owner_of: dict[str, str] = {}
    for f in dataclasses.fields(cls):
        where = f"{cls.__name__}.{f.name}"
        annotation = hints[f.name]
        spec: Option | Argument = Option()
        if typing.get_origin(annotation) is typing.Annotated:
            for meta in annotation.__metadata__:
                if isinstance(meta, Option | Argument):
                    spec = meta
            annotation = typing.get_args(annotation)[0]
        while isinstance(annotation, TypeAliasType):
            annotation = annotation.__value__
        positional = isinstance(spec, Argument)
        short = None if isinstance(spec, Argument) else spec.short
        if positional:
            key = f.name.upper() if spec.name is None else spec.name
            if not key:
                raise TypeError(f"{where}: Argument name must not be empty")
        else:
            key = "--" + f.name.replace("_", "-") if spec.name is None else spec.name
            if not key.startswith("--"):
                raise TypeError(f"{where}: Option name {key!r} must start with '--'")
            if key in ("--help", "--version"):
                raise TypeError(f"{where}: the option name {key!r} is reserved")
            if short is not None and not (
                len(short) == 2 and short[0] == "-" and short[1] != "-"
            ):
                raise TypeError(
                    f"{where}: short flag {short!r} must be '-' followed by one "
                    "character"
                )
        for name in (key, short) if short is not None else (key,):
            if name in owner_of:
                raise TypeError(
                    f"{cls.__name__}: fields {owner_of[name]!r} and {f.name!r} "
                    f"share the wire key {name!r}"
                )
            owner_of[name] = f.name

        origin, args = typing.get_origin(annotation), typing.get_args(annotation)
        flag = annotation is bool
        optional = (
            origin in (UnionType, typing.Union) and len(args) == 2 and NoneType in args
        )
        repeated = origin is tuple and len(args) == 2 and args[1] is Ellipsis
        codec: S.Schema[Any, Any]
        metavar: str | None
        if flag:
            if positional:
                raise TypeError(f"{where}: Cli.Argument cannot be a flag")
            if f.default is not False:
                raise TypeError(f"{where}: a flag's default must be False")
            if spec.metavar is not None:
                raise TypeError(f"{where}: a flag takes no metavar")
            if spec.schema is not None:
                raise TypeError(f"{where}: a flag takes no schema")
            codec, metavar = S.Bool, None
        else:
            if optional:
                inner = next(a for a in args if a is not NoneType)
            elif repeated:
                inner = args[0]
            else:
                inner = annotation
            if spec.schema is None:
                codec, metavar = _text_codec(inner, where)
            else:
                codec, metavar = spec.schema, _metavar_for(inner) or "VALUE"
            if spec.metavar is not None:
                metavar = spec.metavar
            if optional:
                if f.default is not None:
                    raise TypeError(
                        f"{where}: an optional field's default must be None"
                    )
                codec = _optional(codec)
            elif repeated:
                codec = S.Array(codec)

        required = f.default is MISSING
        default_text = None
        if (
            not required
            and f.default is not None
            and f.default is not False
            and f.default != ()
        ):
            encoded: Any = codec._encode(f.default, ())
            # An invalid default is reported by the struct builder right after.
            if not isinstance(encoded, S._Issues):
                default_text = (
                    ", ".join(map(str, encoded)) if repeated else str(encoded)
                )
        params.append(
            _Param(
                field=f.name,
                key=key,
                short=short,
                help=spec.help,
                metavar=metavar,
                codec=codec,
                positional=positional,
                flag=flag,
                repeated=repeated,
                required=required,
                default_text=default_text,
            )
        )

    previous: _Param | None = None
    for p in (p for p in params if p.positional):
        if previous is not None and previous.repeated:
            raise TypeError(
                f"{cls.__name__}: argument {p.field!r} cannot follow "
                f"the variadic argument {previous.field!r}"
            )
        if previous is not None and not previous.required and p.required:
            raise TypeError(
                f"{cls.__name__}: argument {p.field!r} cannot follow "
                f"the optional argument {previous.field!r}"
            )
        previous = p
    return tuple(params)


def _text_codec(annotation: Any, where: str) -> tuple[S.Schema[Any, str], str]:
    """The Schema[T, str] and metavar inferred for a scalar annotation."""
    table: dict[Any, tuple[S.Schema[Any, str], str]] = {
        str: (S.String, "TEXT"),
        int: (S.IntFromString, "INTEGER"),
        float: (S.FloatFromString, "FLOAT"),
        Path: (S.PathFromString, "PATH"),
        datetime: (S.DateTimeFromString, "DATETIME"),
        date: (S.DateFromString, "DATE"),
    }
    if annotation in table:
        return table[annotation]
    if typing.get_origin(annotation) is typing.Literal:
        values = typing.get_args(annotation)
        if all(isinstance(v, str) for v in values):
            return S.Literal(*values), "[" + "|".join(values) + "]"
    raise TypeError(
        f"{where}: no text codec can be inferred for {annotation!r}; "
        "pass one with Cli.Option(schema=...)"
    )


def _dispatch(
    command: Command[Any, Any],
    path: list[str],
    tokens: list[str],
    root: Command[Any, Any],
) -> Effect[None, Any, Any]:
    command_path = " ".join(path)
    usage = _usage_line(command, command_path)
    is_root = command is root
    if command._subcommands:
        if tokens and tokens[0] == "--help":
            return _print(_help(command, command_path, is_root))
        if is_root and tokens and tokens[0] == "--version":
            return _print_version(root)
        if not tokens:
            return fail(UsageError(command_path, usage, MissingCommand()))
        if tokens[0].startswith("-"):
            return fail(
                UsageError(
                    command_path, usage, UnknownOption(tokens[0].partition("=")[0])
                )
            )
        sub = next((c for c in command._subcommands if c.name == tokens[0]), None)
        if sub is None:
            return fail(UsageError(command_path, usage, UnknownCommand(tokens[0])))
        return _dispatch(sub, [*path, sub.name], tokens[1:], root)

    before_separator = tokens[: tokens.index("--")] if "--" in tokens else tokens
    if "--help" in before_separator:
        return _print(_help(command, command_path, is_root))
    if is_root and "--version" in before_separator:
        return _print_version(root)
    if command._handler is None:
        return _print(_help(command, command_path, is_root))

    params = () if command._args is None else command._args.__cli_params__
    raw = _tokenize(params, tokens)
    if not isinstance(raw, dict):
        return fail(UsageError(command_path, usage, raw))
    handler = command._handler
    if command._args is None:
        return handler()
    return (
        S.decode(command._args.__cli_schema__)(raw)
        .catch(S.ParseError)(
            lambda e: fail(UsageError(command_path, usage, InvalidArguments(e.issues)))
        )
        .flat_map(handler)
    )


def _tokenize(
    params: tuple[_Param, ...], tokens: list[str]
) -> dict[str, object] | UsageReason:
    """argv tokens to the raw dict the Args schema decodes, or the first usage
    reason."""
    options = {p.key: p for p in params if not p.positional}
    options |= {p.short: p for p in params if p.short is not None}
    positionals = [p for p in params if p.positional]
    raw: dict[str, object] = {}
    extra: list[str] = []
    only_positional = False
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if only_positional or token == "-" or not token.startswith("-"):
            extra.append(token)
            continue
        if token == "--":
            only_positional = True
            continue
        if token.startswith("--"):
            name, eq, inline = token.partition("=")
        else:
            name, eq, inline = token, "", ""
        param = options.get(name)
        if param is None:
            return UnknownOption(name)
        if param.flag:
            if eq:
                return UnexpectedOptionValue(name, inline)
            raw[param.key] = True
            continue
        if eq:
            value = inline
        elif i < len(tokens):
            value = tokens[i]
            i += 1
        else:
            return MissingOptionValue(name)
        if param.repeated:
            raw.setdefault(param.key, [])
            typing.cast(list[str], raw[param.key]).append(value)
        else:
            raw[param.key] = value
    for param in positionals:
        if not extra:
            break
        if param.repeated:
            raw[param.key], extra = extra, []
        else:
            raw[param.key] = extra.pop(0)
    if extra:
        return UnexpectedArgument(extra[0])
    return raw


def _usage_line(command: Command[Any, Any], command_path: str) -> str:
    parts = [f"Usage: {command_path} [OPTIONS]"]
    if command._subcommands:
        parts.append("COMMAND [ARGS]...")
    params = () if command._args is None else command._args.__cli_params__
    for p in params:
        if p.positional:
            name = p.key if p.required else f"[{p.key}]"
            parts.append(f"{name}..." if p.repeated else name)
    return " ".join(parts)


def _print(text: str) -> Effect[None]:
    return sync(lambda: print(text, end=""))


def _print_version(root: Command[Any, Any]) -> Effect[None]:
    return sync(lambda: print(f"{root.name} {_distribution_version(root)}"))


def _help(command: Command[Any, Any], command_path: str, is_root: bool) -> str:
    def describe(p: _Param) -> str:
        parts = [p.help] if p.help else []
        if p.required:
            parts.append("[required]")
        elif p.default_text is not None:
            parts.append(f"[default: {p.default_text}]")
        return " ".join(parts)

    def option_left(p: _Param) -> str:
        left = f"{p.short}, {p.key}" if p.short is not None else p.key
        return left if p.flag else f"{left} {p.metavar}"

    def table(rows: list[tuple[str, str]]) -> list[str]:
        width = max(len(left) for left, _ in rows)
        return [f"  {left:<{width}}  {right}".rstrip() for left, right in rows]

    params = () if command._args is None else command._args.__cli_params__
    arguments = [(p.key, describe(p)) for p in params if p.positional]
    options = [(option_left(p), describe(p)) for p in params if not p.positional]
    if is_root:
        options.append(("--version", "Show the version and exit."))
    options.append(("--help", "Show this message and exit."))
    commands = [(c.name, c.help) for c in command._subcommands]
    lines = [_usage_line(command, command_path)]
    if command.help:
        lines += ["", command.help]
    for title, rows in (
        ("Arguments:", arguments),
        ("Options:", options),
        ("Commands:", commands),
    ):
        if rows:
            lines += ["", title, *table(rows)]
    return "\n".join(lines) + "\n"


def _distribution_version(root: Command[Any, Any]) -> str:
    """The installed version of the distribution owning the root command's module.

    Editable installs are missing from packages_distributions(), so a
    package that maps to nothing is tried as a distribution name itself.
    """
    module = root._module
    package = module.split(".")[0]
    names: list[str] = []
    if package != "__main__":
        names = sorted(
            set(importlib.metadata.packages_distributions().get(package, []))
        )
        if not names:
            try:
                importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                pass
            else:
                names = [package]
    if not names:
        raise RuntimeError(
            f"{root.name}: cannot determine the version: module {module!r} "
            "belongs to no installed distribution"
        )
    if len(names) > 1:
        raise RuntimeError(
            f"{root.name}: cannot determine the version: module {module!r} "
            f"belongs to several installed distributions: {', '.join(names)}"
        )
    return importlib.metadata.version(names[0])
