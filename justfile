# Run type checker
typecheck:
    cd packages/effecton && uv run ty check .
    cd packages/examples/skills-cli && uv run ty check .

# Run linter
lint:
    uv run ruff check .

# Run linter with auto-fix
lint-fix:
    uv run ruff check . --fix --unsafe-fixes

# Format code
format:
    uv run ruff format .

# Check formatting without modifying files
format-check:
    uv run ruff format . --check

# Run tests
test:
    cd packages/effecton && uv run pytest -s
    cd packages/examples/skills-cli && uv run pytest -s

# Copy root README/LICENSE into the published package (hatchling can't reference parent paths)
sync-package-files:
    cp README.md LICENSE packages/effecton/

# Run all checks (format, lint, typecheck, test)
all: sync-package-files format lint typecheck test

# Run all checks without modifying any files (CI gate)
check: format-check lint typecheck test

# Fix all auto-fixable issues, then run all checks
fix: sync-package-files format lint-fix typecheck test
