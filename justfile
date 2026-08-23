# Run type checker
typecheck:
    cd packages/effecton && uv run mypy .
    cd packages/examples/skills-cli && uv run mypy .

# Run linter
lint:
    uv run ruff check .

# Run linter with auto-fix
lint-fix:
    uv run ruff check . --fix --unsafe-fixes

# Format code
format:
    uv run ruff format .

# Run tests
test:
    cd packages/effecton && uv run pytest -s
    cd packages/examples/skills-cli && uv run pytest -s

# Copy root README/LICENSE into the published package (hatchling can't reference parent paths)
sync-package-files:
    cp README.md LICENSE packages/effecton/

# Run all checks (format, lint, typecheck, test)
all: sync-package-files format lint typecheck test

# Fix all auto-fixable issues, then run all checks
fix: sync-package-files format lint-fix typecheck test
