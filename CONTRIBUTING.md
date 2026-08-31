# Contributing

## Setup

This repo is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): the library lives in `packages/effecton`, and more packages will join it under `packages/`.

```bash
uv sync --all-packages
```

## Development

Tasks are run with [uv-tasks](https://github.com/krzkaczor/uv-tasks), installed as a dev dependency by `uv sync` — nothing extra to install.

```bash
uv run ut format     # Format code
uv run ut lint       # Run linter
uv run ut lint-fix   # Run linter with auto-fix
uv run ut typecheck  # Run type checker
uv run ut test       # Run tests
uv run ut all        # Run all checks
uv run ut fix        # Fix all auto-fixable issues, then run all checks
uv run ut list       # List workspace members and their tasks
```

`typecheck` and `test` fan out across every workspace package; run them from inside a package (for example `packages/effecton/`) to check just that package.

Type-level behavior (inference of value and error channels, variance) is tested in the `packages/effecton/tests/test_types_*.py` files and checked by `ty` as part of `uv run ut typecheck`.
