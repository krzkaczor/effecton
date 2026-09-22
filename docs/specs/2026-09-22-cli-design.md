# E.Cli design

A typer replacement for effecton: declare a command's arguments as an annotated class, parse `argv` through `E.Schema`, and run the handler as an effect. Pure Python, no typer or click, no new dependencies. The shape follows `@effect/cli` (`Command.make`, `withSubcommands`, `Command.run`) with typer's `Annotated` declaration style.

## Goals

- A command's arguments are one `Cli.Args` class: a frozen, keyword-only dataclass whose annotations are the decoded types and whose `Annotated` metadata describes the command line. The handler receives the decoded instance and returns an `Effect`.
- The whole CLI is one effect: `Cli.run(app)` has type `Effect[None, E | Cli.UsageError, R | E.Process.Protocol]` where `E` and `R` are the union of every handler's. `argv` is read through `E.Process`, which gains `argv()`. Services are provided once, at the root, and tests run a command with `E.run_sync` against Test services, pinning the arguments with `E.Process.Test(arguments=(...))`, instead of a `CliRunner`.
- Parsing failures are one `Cli.UsageError` carrying a `UsageReason` union, so `effect.catch(Cli.UsageError)` catches every parsing failure at once; it exits with status 2 through `E.run_main`. Handler failures keep their own errors and exit with status 1.
- Text to value conversion and validation are `E.Schema` codecs whose encoded side is `str`, so `Cli.Option(schema=S.DateFromString)` and refinements through `.check(...)` work unchanged and every problem is reported at once with its option name.

## Non-goals (v1)

Environment variable fallback, shell completion, grouped short flags (`-vq`), `--no-flag` forms, prompts, colors, help text wrapping, options on a command that also has subcommands (git-style global options), an explicit version string (see `--version` below), and a console service for output (handlers print through `E.sync(lambda: print(...))`).

## Placement

`packages/effecton/src/effecton/std/cli.py`, exported from `effecton/__init__.py` as `E.Cli` (`from effecton.std import cli as Cli`). Consumers alias it: `Cli = E.Cli`. The module is added to `api_reference`'s `topics.TOPICS` as `Topic("Cli", ("std.cli",))` with no `extras`, because `Command` is a public member of the module and already renders as `E.Cli.Command`. Tests are collocated: `std/test_cli.py` and `std/test_types_cli.py`. A patch changeset accompanies the change, a docs page `docs/src/pages/std/cli.md` follows the existing std pages and joins the sidebar after Schema, and the effecton agent skill gains a CLI section. `packages/changesets`, `packages/api-reference` and `packages/examples/skills-cli` are ported in the same change and `typer` leaves the workspace.

## Architecture

Three layers, each a pure function over the previous one:

1. **Declaration.** `Cli.Args.__init_subclass__` turns the class into a frozen keyword-only dataclass and builds a `Schema[Args, dict[str, object]]` through the schema module's struct builder, which is generalized to take a per-field resolver `(field, hint, where) -> (wire key, schema)`, `where` being the dotted `Class.field` name for error messages. `S.Struct` passes its own resolver (`S.field` metadata plus JSON inference); `Cli.Args` passes one that reads `Cli.Option` / `Cli.Argument` from `Annotated` metadata and infers a text codec (`Schema[T, str]`) from the annotation. The wire key of a field is its display name (`--package` or `PACKAGE`), so issue paths already read as option names. Type hints are read with `include_extras=True` in both cases and `Annotated` is unwrapped for `S.Struct`. Default values are validated against the field's schema at class definition exactly as for structs. `__init_subclass__` stores the struct schema on `__cli_schema__` and the parameter table on `__cli_params__`: a tuple, in declaration order, of one frozen record per field with `field` (attribute name), `key` (display name and wire key), `short`, `help`, `metavar` (`None` for a flag), `codec`, `positional`, `flag`, `repeated`, `required` (no default) and `default_text` (the text after `[default: ` in help, or `None`). Tests read both directly.
2. **Tokenizing.** `argv` tokens are matched against the command tree and, for the leaf command, against its option and argument table, producing a raw `dict[str, object]` keyed by display name: `str` for a valued option or positional, `True` for a flag, `list[str]` for a repeated field. Keys not given are absent, so struct defaults apply. This step knows nothing about types beyond "flag or value".
3. **Decoding and running.** `S.decode(schema)(raw)` produces the `Args` instance or a `ParseError`, which becomes `InvalidArguments`. The handler runs with the instance.

`Cli.run` starts by requiring `E.Process.Protocol` and reading `argv()`, then tokenizes. `--help` and `--version` short-circuit after tokenizing the command path and print to stdout through `sync(lambda: print(text, end=""))`.

### Process.argv

`E.Process.Protocol` gains `argv(self) -> Effect[tuple[str, ...]]`: the command-line arguments without the program name. `Live` returns `tuple(sys.argv[1:])` as a sync effect; `Test` gains a third plain field `arguments: tuple[str, ...] = ()`. The Process docs page and its docstring mention it.

## Declaration

```python
from typing import Annotated, Literal

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
                S.filter(lambda m: m.strip() != "", message="expected a non-empty message")
            ),
        ),
    ]
    dry_run: Annotated[bool, Cli.Option(short="-n", help="Print the changeset instead of writing it.")] = False


class Notes(Cli.Args):
    package: Annotated[str, Cli.Argument(help="Package to print notes for.")]
```

The `dry_run` field is illustrative: the ported changesets `add` command has no dry-run mode.

- `Cli.Args` is marked `@dataclass_transform(frozen_default=True, kw_only_default=True)` and has no field specifier: defaults are plain values. Instances are constructed directly in tests (`Add(package="effecton", bump="patch", message="…")`).
- A field is an **option** unless its metadata is `Cli.Argument`, in which case it is a **positional argument**. A field without metadata is an option with no help text. A `tuple[T, ...]` field without a default requires at least one occurrence; with `= ()` it is optional.
- `Cli.Option(*, help="", name=None, short=None, metavar=None, schema=None)` and `Cli.Argument(*, help="", name=None, metavar=None, schema=None)` are `@final` frozen dataclasses. `name` overrides the display name and must start with `--` (options) or be non-empty (arguments); `short` must be `-` followed by one character; `metavar` overrides the placeholder in help; `schema` is a `Schema[Any, str]` that replaces inference. ty cannot check `Annotated` metadata against the annotation, so a `schema` whose decoded type disagrees with the annotation is not a static error; the encoded type must be `str` and is likewise unchecked.
- The default display name is `--` plus the field name with `_` replaced by `-` for options, and the field name upper-cased for arguments (`skill_url` becomes `SKILL_URL`). `--help` and `--version` are reserved: a field whose display name is either (a field named `help`, or `name="--version"`) is a definition-time error, so the built-in rows never collide with a user option.

### Text inference

The codec is inferred from the annotation (after unwrapping `Annotated`); `schema=` wins when given, and then the annotation only decides flag-ness, repetition and optionality as below. A PEP 695 alias (`type Bump = Literal["major", "minor", "patch"]`) is unwrapped through its `__value__` before inference runs, so `Bump` in the declaration above infers `S.Literal("major", "minor", "patch")` exactly as the spelled-out `Literal` would.

| Annotation | Codec | Metavar |
| --- | --- | --- |
| `str` | `S.String` | `TEXT` |
| `int` | `S.IntFromString` | `INTEGER` |
| `float` | `S.FloatFromString` | `FLOAT` |
| `E.Path` | `S.PathFromString` | `PATH` |
| `datetime` | `S.DateTimeFromString` | `DATETIME` |
| `date` | `S.DateFromString` | `DATE` |
| `Literal[...]` of `str` values | `S.Literal(...)` | `[a\|b\|c]` |
| `bool` | flag: `S.Bool`; present is `True`; `schema=` is a definition-time error | none |
| `T \| None` | the codec of `T` on decode (the wire never carries `None`), and `None` encodes to `None`; the default must be `None` | metavar of `T` |
| `tuple[T, ...]` | `S.Array(codec of T)`; every occurrence is collected | metavar of `T` |
| explicit `schema=` | as given | metavar of the annotation when it is a table entry above, else `VALUE`; `metavar=` overrides either |

An explicit `schema=` still runs the annotation through the table for its metavar only: `Cli.Option(schema=S.String.check(...))` on a `str` field gets `TEXT` (the `--message` row in the help example below), while a `schema=` on an annotation with no standard codec (such as `Decimal`) falls back to `VALUE` unless `metavar=` is also given.

Definition-time `TypeError`s, with exact messages:

- `Add.amount: no text codec can be inferred for <class 'decimal.Decimal'>; pass one with Cli.Option(schema=...)` for any other annotation, including a `Literal` with a non-`str` value, `bool | None`, `tuple[bool, ...]` and nested tuples. The message names the innermost annotation the table rejected, in its `repr`: `bool | None` and `tuple[bool, ...]` both report `<class 'bool'>`, and `Literal[1, 2]` reports `typing.Literal[1, 2]`.
- `Add.dry_run: a flag's default must be False` when a `bool` field has no default or a default other than `False`.
- `Bad.verbose: a flag takes no metavar` when a `bool` field is given `Cli.Option(metavar=...)`, and `Bad.verbose: a flag takes no schema` for `Cli.Option(schema=...)`.
- `Bad.help: the option name '--help' is reserved` (likewise `'--version'`) when a field's display name, default or explicit, is a built-in option.
- `Add.port: an optional field's default must be None` when a `T | None` field has no default or a default other than `None`.
- `Notes.name: Argument name must not be empty` when `Cli.Argument(name="")` is given.
- `Notes: argument 'rest' cannot follow the variadic argument 'files'` when a positional comes after a `tuple[T, ...]` positional.
- `Notes: argument 'name' cannot follow the optional argument 'package'` when a required positional follows one with a default.
- `Add: fields 'package' and 'pkg' share the wire key '--package'` (also for a `short` shared by two fields, with the short name as the key).
- `Add.package: the default '' does not satisfy its schema: expected a non-empty message, got ''` (the struct builder's message, unchanged).
- `Add.verbose: Cli.Argument cannot be a flag` for a `bool` positional.
- `Add.bump: Option name '-b' must start with '--'` / `Add.bump: short flag 'b' must be '-' followed by one character`.

Checks run in this order, so the first failing one is the message raised. Fields are visited in declaration order; for each: the display name (`Argument name must not be empty`, `Option name ... must start with '--'`, then the reserved names), the short flag's shape, the wire-key collisions (long name first, then short), then the shape: for a `bool`, `Cli.Argument cannot be a flag`, the `False` default, the metavar, the schema; for anything else, codec inference (`no text codec ...`), then the optional field's `None` default. After every field, the positional order (`cannot follow the variadic argument`, then `cannot follow the optional argument`). Last, the struct builder validates each default against its codec (`does not satisfy its schema`).

## Commands

```python
add = Cli.command("add", args=Add, handler=run_add, help="Create a changeset from the given package, bump level, and message.")
status = Cli.command("status", handler=run_status, help="Show pending changesets and the releases they would produce.")
app = Cli.command("changeset", help="Changeset-based changelog and version management.").with_subcommands(add, status, version, notes)
```

- `Cli.command(name, *, help="", args: type[T], handler: Callable[[T], Effect[None, E, R]]) -> Command[E, R]`; `Cli.command(name, *, help="", handler: Callable[[], Effect[None, E, R]]) -> Command[E, R]`; `Cli.command(name, *, help="") -> Command[Never, Never]`. All parameters after `name` are keyword-only so a class and a callable can never be confused positionally.
- `Command[E, R]` is `@final @dataclass(frozen=True)`, generic over old-style covariant TypeVars (see the ty notes in `CLAUDE.md`), and exposes `name` and `help`. Its remaining fields are private (`_module`, `_args`, `_handler`, `_subcommands`) but the dataclass has no other constructor, so tests build a bare command positionally: `Cli.Command(name, help, module, args, handler, subcommands)`, e.g. `Cli.Command("prog", "", "__main__", None, None, ())`. `Cli.command` also records the `__name__` of the module that called it (`sys._getframe(1).f_globals["__name__"]`), which `--version` uses when the command is the root; `with_subcommands` keeps it. `with_subcommands(*commands: Command[E2, R2]) -> Command[E | E2, R | R2]` returns a new command; calling it on a command that has a handler, or twice, raises `TypeError("changeset: a command has either a handler or subcommands")` / `TypeError("changeset: subcommands are already set")`; two subcommands with the same name raise `TypeError("changeset: two subcommands are named 'add'")`. `Command` is not exported from `E`; it is reachable through `Cli.Command`.
- `Cli.run(command) -> Effect[None, E | UsageError, R | E.Process.Protocol]`. It is not curried: unlike `provide` and `catch`, nothing in its types needs the two-step form, and the arguments come from `E.Process.argv()` rather than a parameter. The command's `name` is the program name in usage lines.
- **`--version`** is always available on the root command and prints `<name> <version>`. The version is derived the way Click's `version_option` does it, resolved only when `--version` is given: take the top-level package of the module that defined the root command (`changesets.cli` gives `changesets`), map it through `importlib.metadata.packages_distributions()`, and read `importlib.metadata.version` of that distribution. Editable installs, which is what `uv sync` makes of workspace members, do not appear in `packages_distributions()`, so when the package maps to nothing the lookup falls back to a distribution named like the package (`skills_cli` finds `skills-cli`, since metadata lookups normalise `_` and `-`). This reads the installed distribution's metadata, written from `pyproject.toml` at build time, so no project file is read. When the module is `__main__`, when neither lookup finds a distribution, or when the mapping yields more than one, `--version` dies with `RuntimeError("changeset: cannot determine the version: module 'x' belongs to no installed distribution")` (or `... belongs to several installed distributions: a, b`, names sorted). This is a defect, as in Click, because it means the program is mis-packaged rather than misused.

```python
def run() -> None:
    E.run_main(
        Cli.run(app)
        .provide(E.FileSystem.Protocol)(E.FileSystem.AsyncLive())
        .provide(E.Process.Protocol)(E.Process.Live())
        .provide(NameGenerator.Protocol)(NameGenerator.Live())
    )
```

## Parsing

Walk the command tree from the root with the remaining tokens:

1. **A command with subcommands.** If the first token is `--help`, print this command's help and succeed. If this is the root and the first token is `--version`, print `<name> <version>` and succeed. No tokens: `MissingCommand`. A token starting with `-`, including a lone `-`: `UnknownOption` with the token (cut at its first `=`). Otherwise look the token up among the subcommands (`UnknownCommand` if absent) and recurse with the rest.
2. **A leaf command** checks, in this order, before it tokenizes anything:
   - Split the tokens on the first `--`, if any, into a before-separator slice and the rest. If `--help` appears anywhere in the before-separator slice, print the leaf's help and succeed, whatever else the tokens contain.
   - If the leaf is also the root command and `--version` appears anywhere in the before-separator slice, print `<name> <version>` and succeed.
   - If the command has neither a handler nor subcommands (a placeholder command), print its help and succeed, whatever the tokens.
   - Otherwise tokenize left to right:
     - `--` ends option parsing; every later token is positional.
     - `--name=value` and `--name value`: the value is the next token verbatim, even if it starts with `-`; a missing next token is `MissingOptionValue`. A flag given `=value` is `UnexpectedOptionValue`. An unknown name is `UnknownOption`.
     - `-x value` for a declared short flag, with the same rules; `-x=value` and `-xvalue` are not recognised, so `-xvalue` is `UnknownOption`. A lone `-` is positional. A negative number such as `-1` is an unknown option unless it follows `--`.
     - Anything else is positional and fills the `Cli.Argument` fields in declaration order; a trailing `tuple[T, ...]` argument takes every remaining positional; a positional with nowhere to go is `UnexpectedArgument`.
     - A scalar option given twice keeps the last value. A `tuple[T, ...]` option keeps every occurrence in order. A flag is `True` on the first occurrence.
     - Tokenizing stops at the first usage error; the raw dict is then decoded and every schema issue is reported together as one `InvalidArguments`.
3. Run the handler with the decoded `Args` (or with no arguments when the command has none).

## Help

`str` output for `changeset add --help`, given the declaration above:

```
Usage: changeset add [OPTIONS]

Create a changeset from the given package, bump level, and message.

Options:
  --package TEXT              Package the change belongs to. [required]
  --bump [major|minor|patch]  major, minor, or patch. [required]
  --message TEXT              Changelog entry for the change. [required]
  -n, --dry-run               Print the changeset instead of writing it.
  --help                      Show this message and exit.
```

And for the root:

```
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
```

Rules:

- The usage line is `Usage: <command path> [OPTIONS]` followed, for a leaf, by each positional in order: `NAME` when required, `[NAME]` when it has a default, `NAME...` / `[NAME]...` when variadic; and for a command with subcommands by `COMMAND [ARGS]...`. `[OPTIONS]` is always present because `--help` exists.
- The help text, when non-empty, follows after a blank line, verbatim and unwrapped.
- Sections appear in the order `Arguments:`, `Options:`, `Commands:`, each preceded by a blank line and only when it has rows. Every row is two spaces, the left column padded to the widest left column of that section, two spaces, the right column, with trailing whitespace stripped.
- Argument rows: left is the display name; right is the help text followed by markers. Option rows: left is `-x, --name` or `--name`, then a space and the metavar unless the option is a flag. `--version` (root command only) and `--help` are the last option rows. Command rows: left is the subcommand name, right its help text.
- Markers follow the help text separated by single spaces: `[required]` when the field has no default; `[default: <text>]` when the default is not `None`, `False` or `()`, where `<text>` is the default run through the field's codec's encode side, tuple items joined by `, `.
- The output ends with a single newline.

## Errors

Every parsing failure is one error class, `Cli.UsageError`, so `effect.catch(Cli.UsageError)(handler)` catches all of them:

```python
@final
@dataclass(frozen=True)
class UsageError(EffectonError):
    command: str  # the command path, "changeset add"
    usage: str  # that command's usage line, "Usage: changeset add [OPTIONS]"
    reason: UsageReason
    exit_code: ClassVar[int] = 2

    def __str__(self) -> str:
        return f"{self.usage}\nTry '{self.command} --help' for help.\n\n{self.reason}"


type UsageReason = (
    UnknownOption | UnknownCommand | MissingCommand | MissingOptionValue
    | UnexpectedOptionValue | UnexpectedArgument | InvalidArguments
)
```

`UsageError.__str__` renders:

```
Usage: changeset add [OPTIONS]
Try 'changeset add --help' for help.

<reason>
```

Each reason is a plain `@final` frozen dataclass (not an `EffectonError`; it never travels on its own, only inside `UsageError.reason`), carrying only its own fields, with `__str__` returning just the reason text embedded above:

| Reason | Fields | Text |
| --- | --- | --- |
| `UnknownOption` | `option: str` | `No such option '--foo'.` (the token as given; a long option is cut at its first `=`, a short token is kept whole) |
| `UnknownCommand` | `name: str` | `No such command 'foo'.` |
| `MissingCommand` | | `Missing command.` |
| `MissingOptionValue` | `option: str` | `Option '--package' requires a value.` |
| `UnexpectedOptionValue` | `option: str, value: str` | `Option '--dry-run' does not take a value.` |
| `UnexpectedArgument` | `argument: str` | `Got unexpected extra argument 'foo'.` |
| `InvalidArguments` | `issues: tuple[S.Issue, ...]` | one line per issue, in issue order |

`InvalidArguments` lines: a `MissingKey` renders `Missing option '--package'.` when the key starts with `--` and `Missing argument 'PACKAGE'.` otherwise. Every other issue renders `Invalid value for '<name>': <body>`, where `<name>` is the first path segment (the display name) and `<body>` is `str(dataclasses.replace(issue, path=issue.path[1:]))`, so an item of a repeated option reads `Invalid value for '--tag': [1]: expected an integer string, got 'x'`. Example: `Invalid value for '--bump': expected 'major' | 'minor' | 'patch', got 'big'`.

Through `E.run_main` a usage error is logged like any failure and exits with 2; help and version exit with 0; handler errors keep their `str` and exit with 1 as today.

## Migration

- **changesets**: `cli.py` builds the root command from `add`, `status`, `version` and `notes` `Command` values exported by the per-command modules and `run()` is the entry point shown above. `add`'s manual bump check becomes the `Literal` codec and the empty-message check the refinement shown above; `typer.echo` calls become `E.sync(lambda: print(...))` inside the handler effect. `test_cli.py` keeps its subprocess tests (exit codes and stderr contents are unchanged) and gains a usage-error case asserting exit code 2 and `Missing option '--package'.`.
- **api-reference**: the command stays a single root leaf, invoked as `api-reference --out PATH` (typer collapsed its one command into the root, so `Cli.command` collapses it the same way: one `Command` with `args=Generate`, no `with_subcommands`), with `Generate(Cli.Args)` holding `out: Annotated[E.Path, Cli.Option(help=...)] = E.Path("docs/src/pages/api.md")`; the entry point provides `E.FileSystem.AsyncLive()` and `E.Process.Live()`.
- **skills-cli**: one root command with `Install(Cli.Args)` holding `skill_url: Annotated[str, Cli.Argument(help=...)]`. `Terminal.Live.confirm` replaces `typer.confirm` with a `sync` effect around `input(f"{prompt} [y/N]: ")`, answering `True` for `y`/`yes` in any case; `EOFError` and `KeyboardInterrupt` stay defects. `cli.py` exports `app` and `run()`; `test_cli.py` drops `CliRunner` and the monkeypatching and runs `E.run_sync(Cli.run(app).provide(E.Process.Protocol)(E.Process.Test(arguments=("https://…",))).provide(...)(other Test services))`, asserting stdout through `capsys` and failures through `E.run_sync_exit`. The `@todo` comment goes.
- `typer` is removed from the three `pyproject.toml` files and the lockfile.

## Testing

- `test_cli.py` (Arrange-Act-Assert, handlers append the received `Args` to a list, arguments pinned through `E.Process.Test(arguments=...)`, `capsys` for output): option forms (`--name value`, `--name=value`, short), flags, positionals including optional and variadic, `--` handling, repeated scalar and tuple options, defaults and `None` optionals, every codec in the inference table, an explicit `schema=` with a refinement, nested subcommands two levels deep, `--help` at each level rendered byte-for-byte against the examples above, `--version` on a root defined in the test module printing `importlib.metadata.version("effecton")` and dying with the exact `RuntimeError` for a root whose recorded module is `__main__`, every `UsageError` (one per reason) with its exact `str`, catching `Cli.UsageError` and matching on `.reason`, `InvalidArguments` accumulating several issues, every definition-time `TypeError` message, and `run_main` integration for exit codes 0, 1 and 2.
- `test_types_cli.py`: `assert_type` pins for `Cli.command` in its three forms, `with_subcommands` producing the union of `E` and `R`, `Cli.run(app)` returning `Effect[None, E | UsageError, R | E.Process.Protocol]`, `Args` field and `__init__` types, and negative pins (handler with the wrong argument type, assigning to a frozen field, `with_subcommands` with a non-command) inside never-called underscore functions.
- `test_process.py` covers `argv()` for `Live` (against `sys.argv`) and `Test`; `test_types_process.py` pins its type.
- `test_schema.py` keeps passing after the struct builder refactor, and gains a case that `Annotated[int, "x"]` on an `S.Struct` field is treated as `int`.

## Risks

- **Union inference through `*commands`.** `with_subcommands(self, *commands: Command[E2, R2]) -> Command[_E | E2, _R | R2]` relies on ty joining `E2` and `R2` across variadic arguments into a union; `test_types_cli.py`'s `_with_subcommands_unions_errors_and_requirements` confirms ty solves the single generic signature directly (`app.with_subcommands(add, status)` pins to `Cli.Command[AddFailed | StatusFailed, E.FileSystem.Protocol | E.Process.Protocol]`), so the shipped code needed no overload fallback and none of the `Tuple`/`Union` precise-overloads-plus-`Any` pattern from `schema.py`.
- **`Callable[[T], Effect[None, E, R]]` against `@gen` handlers.** A `@gen` function returns an `Effect`, so this should infer; a handler written as a lambda returning `E.success(None)` yields `Effect[None, Never, Never]`, which must not widen the union to `Unknown`.
- **Shared struct builder.** Generalizing `_struct_schema` touches the shipped Schema; the existing tests pin its behavior and the refactor adds no public API.
