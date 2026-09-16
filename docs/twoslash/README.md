# Type hovers for Python snippets

Every ```` ```python ```` block in the docs is type-checked by [ty](https://docs.astral.sh/ty/)
at build time and rendered with Twoslash-style hovers: hover an identifier and
the popup shows its inferred type and docstring. The landing page's playground
uses the same pipeline for its with-Effecton panel.

## How it works

```
vocs.config.ts ── twoslash.transformers: [tyTwoslash()]
      │ shiki preprocess hook (sync)
twoslasher.ts ── directives → cache → spawnSync(ty-client.ts) → twoslash nodes → error gate
      │ stdin JSON {code, uri, rootDir, queries}     stdout JSON {hovers, queries, diagnostics}
ty-client.ts ── `uv run ty server` (cwd = repo root) → didOpen virtual file
                → semanticTokens/full → hover per identifier → diagnostic → exit
```

- `ty check` has no machine-readable output, so the helper talks to ty's
  language server instead. Each snippet is opened as a virtual document under
  `docs/snippets/` (never written to disk), so `import effecton as E` resolves
  through the repo's `.venv`.
- Shiki transformers are synchronous and the LSP is not, so the session runs
  in a child Node process (`ty-client.ts`) driven with `spawnSync`. A session
  takes around 100 ms; results are cached (see below).
- On docs pages the popup UI is vocs' own twoslash renderer. The landing page
  renders its own popup (`Landing.tsx`, `.hv` / `.hv-pop`) from the same data.

Requirements: `uv` on PATH and a synced environment at the repo root
(`uv sync --all-packages`). Node 22.6+ (runs the `.ts` helper directly).

## Directives

Python-comment versions of the usual Twoslash directives. Directive lines are
removed from the rendered code; ty sees the whole snippet.

| Directive | Effect |
| --- | --- |
| `# ---cut---` / `# ---cut-before---` | Hide everything above (setup, stubs, imports). |
| `# ---cut-after---` | Hide everything below. |
| `# ---cut-start---` … `# ---cut-end---` | Hide a region. |
| `#     ^?` | Show a persisted type popup for the token at the caret on the line above. |
| `# @errors: rule-a rule-b` | The snippet is expected to raise exactly these ty rules; they render as error lines. |
| `# @noErrors` | Do not render or gate diagnostics. |
| fence meta `notwoslash` | Skip the block. |

## The type gate

ty diagnostics with severity error or warning render as red lines under the
code. Undeclared ones (and declared ones that no longer occur) are reported:

- `vocs dev` prints a warning and keeps rendering, so you see the problem
  while writing.
- `vocs build` fails, so CI rejects snippets that drifted from the library.
  The message lists each rule, the line, and the numbered snippet.

Fix the snippet, declare the errors with `# @errors: …` when they are the
point of the example, or add `# @noErrors`. `reveal_type(x)` works too: ty's
`revealed-type` note renders as an info line and never fails the build.

## Cache

Results live in `docs/node_modules/.cache/vocs/twoslash-ty/<key>.json`. The
key covers the snippet, `uv run ty --version`, the effecton sources
(`packages/effecton/src`, excluding tests), both `pyproject.toml` files,
`uv.lock` and the files in this directory. Changing any of them invalidates
automatically; delete the directory to force a full recompute.

## Environment variables

- `TY_TWOSLASH=off` — strip directives but skip ty entirely (no hovers).
- `TY_TWOSLASH_DEBUG=1` — log every cache miss.

## Debugging by hand

```sh
cd docs
printf '%s' '{"code":"import effecton as E\nx = E.success(1)\n","uri":"file:///tmp/snippets/t.py","rootDir":"'"$(cd .. && pwd)"'","queries":[]}' \
  | node --experimental-strip-types --no-warnings twoslash/ty-client.ts | jq .
```

## Not yet

- Inlay hints (ty supports them; twoslash has no node type for them).
- Hovers on the playground's without-Effecton panel.
