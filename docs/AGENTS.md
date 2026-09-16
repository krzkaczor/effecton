# Docs agent guide

This is the effecton documentation site: [vocs](https://vocs.dev) 2, pnpm, React 19,
TypeScript strict. Pages are Markdown/MDX under `src/pages/`; the landing page at `/` is
a React port of the Figma design under `src/components/landing/` (see its README).

Run everything through pnpm from this directory: `pnpm dev`, `pnpm build`,
`pnpm typecheck`. The `twoslash/` helper needs `uv` on PATH and a synced environment at
the repo root (`uv sync --all-packages`), because the build runs ty.

## Python code snippets are type-checked and get type hovers

Every ```` ```python ```` block on a docs page, and the with-Effecton panel of the landing
playground, is type-checked by ty at build time and rendered with Twoslash-style hovers.
Full details in `twoslash/README.md`; the essentials:

- **Snippets must type-check against the real library.** An undeclared ty error or
  warning fails `pnpm build` and CI with the rule, line and page. In `pnpm dev` it only
  warns and renders a red error line, so you see it while writing. Hovers come from
  `uv run ty server` over a virtual file inside the repo, so `import effecton as E`
  resolves to the workspace package.
- **Write complete snippets, and hide setup with a cut.** Anything a snippet needs but
  the reader should not see (imports, stub classes, fixtures) goes above `# ---cut---`.
  ty sees the whole block; only the part below the cut renders. `# ---cut-after---` and
  `# ---cut-start---` … `# ---cut-end---` also exist.
- **Show a type inline** with a `^?` comment under the token:

  ```python
  program = check_secret().provide(E.HttpClient.Protocol)(E.HttpClient.SyncLive())
  #  ^?
  ```

- **Errors on purpose**: `# @errors: unresolved-attribute` declares the exact ty rules
  the snippet is expected to raise (they render as error lines); `# @noErrors` skips
  diagnostics for that block. Add `notwoslash` to the fence meta to skip a block
  entirely. `reveal_type(x)` renders as an info line and never fails the build.
- **Results are cached** in `node_modules/.cache/vocs/twoslash-ty/`, keyed on the snippet,
  the ty version, the effecton sources, the lockfile and `twoslash/*.ts`. You never need
  to clear it; changing the library recomputes automatically.
- **Landing playground**: `snippets.ts` emits the Python as strings, one per level of the
  guarantee ladder. `LandingPage.tsx` (a server component) runs each level through the
  same helper; nothing is hidden. Keep every emitted line within 68 characters and
  update the line-count table in `src/components/landing/README.md` when the emitters
  change.

When a snippet fails the gate, fix the snippet to match the library rather than
declaring the error, unless the error is what the example is about.

## The API Reference page is generated

`src/pages/api.md` (the `/api` page) is gitignored and written by `pnpm generate:api`,
which `pnpm dev` and `pnpm build` run first through their `predev`/`prebuild` hooks. The
generator is the `packages/api-reference` workspace package (`uv run api-reference` from
the repo root), so it needs the same `uv sync --all-packages` as the type hovers. It reads
`packages/effecton/src/effecton/` statically with griffe: every `__all__` name and every
public member of the std service modules, in the section order of its `topics.py`. Points
to know:

- **Fix the docstrings, not the page.** Content comes from the library's docstrings and
  signatures; the section order and headings live in
  `packages/api-reference/src/api_reference/topics.py`.
- **Rerun after editing Python.** `pnpm dev` regenerates only on start; run
  `pnpm generate:api` again to refresh the page while the dev server is up.
- **A new module fails the build until it is placed.** An export whose module no topic
  lists stops the generator (and `pnpm build`) with an `UnmappedModule` message naming it.
- **Its fences are `notwoslash` on purpose.** Signatures are not complete programs, so
  they skip the type gate and get plain highlighting rather than hovers.

## Verification

`pnpm typecheck && pnpm build` before finishing any change. For a visible change, also
open `pnpm dev` and hover a few identifiers to confirm the popups.
