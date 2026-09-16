# api-reference

Renders `docs/src/pages/api.md`, the docs site's API Reference page, from the
effecton sources with [griffe](https://mkdocstrings.github.io/griffe/). Run it from
the repo root with `uv run api-reference` (the docs `pnpm dev` and `pnpm build`
run it automatically). Section order and headings live in
`src/api_reference/topics.py`.
