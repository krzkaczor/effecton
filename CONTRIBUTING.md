# Contributing

## Setup

This repo is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): the library lives in `packages/effecton`, and more packages will join it under `packages/`.

```bash
uv sync --all-packages
```

## Development

Requires [just](https://github.com/casey/just) (`brew install just`).

```bash
just format     # Format code
just lint       # Run linter
just lint-fix   # Run linter with auto-fix
just typecheck  # Run type checker
just test       # Run tests
just all        # Run all checks
just fix        # Fix all auto-fixable issues, then run all checks
```

Type-level behavior (inference of value and error channels, variance) is tested in the `packages/effecton/tests/test_types_*.py` files and checked by `ty` as part of `just typecheck`.
