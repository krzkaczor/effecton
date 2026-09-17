# Effecton docs

The documentation site, built with [vocs](https://vocs.dev). The landing page at `/` is a
React port of the Figma design (see `src/components/landing/README.md`); everything else
is Markdown under `src/pages/`.

```bash
pnpm install     # Install
pnpm dev         # Start the dev server
pnpm build       # Build a static site into dist/
pnpm preview     # Serve the build
pnpm typecheck   # tsc --noEmit
```

Every ```` ```python ```` block is type-checked by ty and gets type hovers, and a snippet
with an undeclared type error fails `pnpm build`. This needs `uv` on PATH and a synced
environment at the repo root (`uv sync --all-packages`). See `twoslash/README.md` for the
directives (`# ---cut---`, `#  ^?`, `# @errors:`, `# @noErrors`) and how it works.

`logo/` holds the brand PNG exports and is not used by the site; the SVGs the site
uses live in `public/`. `public/og.png` is the social preview card every page links to
(`ogImageUrl` in `vocs.config.ts`); its source is `og/og.html`, so after editing that file
open it in a browser at a 1200×630 viewport and save a screenshot over the PNG.
