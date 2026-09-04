# effecton agent guide

effecton is a typed effect system for Python inspired by Effect-TS: sync-only, zero runtime dependencies, Python 3.14, typechecked with ty. Kernel modules live in `packages/effecton/src/effecton/`, std services in `packages/effecton/src/effecton/std/`, and tests collocated next to the module they cover as `test_<module>.py` (the release workflow deletes every `test_*.py` under `src/` before building the published package).

## Verification

Verify every change as follows:

- `uv run ut fix` is the verification gate: ruff format, then ruff check with fixes, then `ty check`, then pytest. Run it before finishing any change.
- Run everything through `uv run` (tasks via `uv run ut <task>`, defined in `[tool.ut.tasks]`), never through bare `python3`.
- Type behavior is pinned in `src/effecton/test_types_*.py` through `assert_type` calls plus deliberate `# ty: ignore[rule]` negative assertions; `unused-ignore-comment = "error"` makes them self-checking.

## Naming and API design

Follow these rules when adding or changing public API:

- **Effect-TS naming parity** for combinators—check Effect-TS for the canonical name (such as `suspend`, `attempt`, and `catch_all`) before inventing one. Diverge only when a better term fits effecton's "requirement" vocabulary; for example, `ImplicitRequirement` instead of Context.Reference, or the overloaded `suspend` decorator instead of Effect.fn.
- **Errors are cause-specific, never generic buckets**: one frozen `EffectonError` dataclass per failure cause, such as `FileNotExists` or `HttpStatusError`. Signatures carry precise unions through `type` aliases. `attempt` error mappers translate only the expected exception types and re-raise the rest so they stay defects.
- **Errors live in the module that raises them, never in a central `errors.py`**: service errors in the service module, program-level errors alongside the program, each with a module-local union alias (`type FileSystemError = ...`). Cross-module unions compose through the module namespace (`config.ConfigError | FileSystem.FileSystemError`). Each error overrides `__str__` with its human-readable message, so rendering a failure is just `str(error)` — no CLI-side describe-match. `packages/changesets` is the exemplar.
- **No abstract base classes, ever—always `typing.Protocol`** with `@runtime_checkable`. Implementing classes still explicitly subclass the protocol so that a missing member is a static error.

## Code style

Follow these conventions in all effecton code:

- **Consumer code (tests, README, examples) imports the package once as `import effecton as E`** and accesses everything through it: `E.success`, `E.gen`, `class ParseError(E.EffectonError)`. Don't use flat `from effecton import ...` imports. Library internals import submodules directly (`from effecton.effect import ...`) because `E` is the error TypeVar there.
- **Service pattern**: one module per service, exporting `Protocol`, `Live`, and `Test` (with `__test__ = False`). Consumers alias the module: `from ... import file_system as FileSystem`, then `FileSystem.Protocol`.
- **Use the `@suspend` decorator only where the body does eager work.** A body that only builds an `attempt(...)` doesn't need it, because `attempt` already defers. `suspend` is overloaded: a zero-argument thunk resolves to the deferred effect itself, and a function with parameters resolves to a decorated callable that defers its body per call. `sync` wraps an eager thunk whose exceptions should become defects, as in Test service impls.
- **Use `yield from` over bare `yield`** in `@gen` programs. `Effect.__iter__` types the sent-back value per expression; bare `yield` types as `Any`.
- **Nest helpers inside their only caller**, closing over locals. Reserve module-level private helpers for logic that multiple functions share.
- **Order functions by importance**: public or more important functions come before the private or less important ones they call, so a module's entry point reads first and details follow (e.g. `add_changeset` before `pick_name`). Forward references inside function bodies make this safe.
- **ty inference notes**: literal arguments stay literal (`E.success(1)` is `Effect[Literal[1]]`; covariance widens it where an `Effect[int]` is expected), and constructor calls whose return type the signature widens may need explicit specialization because ty solves class type parameters from the arguments alone — see `catch_all` in `src/effecton/effect.py`. Keep every type parameter of `Effect` out of contravariant slots in its own methods (e.g. the `__iter__` send channel is `Any`, not `A`, and explicitly-annotated `self` parameters use fresh method-level typevars), or ty's variance inference turns the parameter invariant; when two classes reference each other (`Effect` ↔ `ProvideBinder`), inference gives up entirely and variance must be declared through old-style TypeVars (suppress UP046). R-subtraction (`provide`, `scoped`) only solves when at most one typevar is free in the union match: pin the subtracted type first (a class parameter on the binder, or a concrete class like `Scope`) and default the remainder (`[R2 = Never]`) so the vacuous case lands on `Never` instead of `Unknown`; in `ProvideBinder.__call__`'s self annotation the class-scoped `T` must be reused as-is — re-binding it as a method typevar recreates the unsolvable two-typevar match. `provide` stays curried (`provide(T)(impl)`, never `provide(T, impl)`) because a one-call form lets a mismatched impl silently join into `T` and subtract too much, instead of erroring. See `src/effecton/provide.py`.

## Blank lines

Use blank lines deliberately:

- **Tests follow the Arrange-Act-Assert structure** with a single blank line between the three blocks; `src/effecton/std/test_scope.py` is the exemplar.
- **`@gen` generator bodies** put requirement acquisition (`yield from require(...)` or `require_implicit(...)`) at the top, followed by a blank line, then the rest. Never reorder requirement acquisition across guards only for grouping.
- Use exactly one blank line: ruff format collapses runs of two or more and strips blanks that directly follow `def`.