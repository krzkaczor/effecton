# Effecton — landing page

React port of the Figma design
[Effecton AI → `version-1-effecton-landing-page`](https://www.figma.com/design/Qdf4ibUJD8Rll8Ei0bQ9iJ/Effecton-AI?node-id=1-57)
(node `1:57`, 1440 × 2975). It renders at `/` from `src/pages/index.mdx` with
vocs' `blank` layout, so nothing of the docs shell surrounds it.

## Files

| Path | What it is |
| --- | --- |
| `Landing.tsx` | The whole page as a client component. Sections are commented with their Figma node ids. |
| `landing.css` | Design tokens + section styles, nested under `.landing` so they never reach the docs pages. Every value is taken from the Figma file. |
| `snippets.ts` | The comparison playground's Python emitters and tokeniser. |
| `dot-field.ts` | The hero's canvas dot field. |
| `mark.ts` | Path data for the "E" mark and the wordmark, exported from the file's vector geometry. The same shapes live in `public/` as SVG files. |
| `social.ts` | The GitHub, X and Discord glyphs (simple-icons, CC0) for the icon links in the nav and footer (`SocialLinks`), the ChatGPT, Claude, sparkle and scan glyphs the agent-prompt row uses, and the hamburger / close glyphs for the phone nav. |

## Design tokens

Pulled from the Figma document, not eyeballed:

```
Background      #101010      Nav background   #101010 *
Surface (cards) #212121      Border (dark)    #2C2C2F
Text            #FFFFFF      Border (light)   #E1E1E1
Text muted      #CBCBCB      Input border     #272727
Text dim        #828282      On light         #1D1D1D
Lime            #C5FF51      Lime pale        #F6FF7E
```

- **Serif / headings** — Zodiak Regular, 40px (64px in the hero)
- **Sans / everything else** — Satoshi Regular & Medium, letter-spacing `-1%`
- Both load from the Fontshare CDN, which is where they are published
- Corner radius `8px`; content column `1280px` inside a `1440px` page (80px gutters, 32px inner padding)
- Every section's content column carries a 1px `#2C2C2F` rule on **all four
  sides** (Figma sets `borderTop/Bottom/Left/RightWeight: 1`). Stacked columns
  are pulled together with `margin-top: -1px` so adjacent sections share one
  rule instead of rendering 2px.

Figma stores its *auto* line height as `100%`. The real ratios it rendered are
≈1.35 (Zodiak) and ≈1.335 (Satoshi), so those are what the CSS uses.

\* Figma's nav fill is `#020202`; it was changed to the page background by
request. The original is kept as the unused `--bg-nav` token. The hero
wordmark is also larger than drawn (128 × 22 instead of 70 × 12), by request.


## The calls to action

The hero's buttons follow vocs.dev, by request: a primary **Read the docs**,
a secondary **GitHub** with the mark, and under them the **Copy instructions
for agent** row (`AgentPrompt`): the button copies `Read <site>/introduction
and set up effecton in my project.`, the ChatGPT and Claude icons open that
prompt in either (`chatgpt.com?q=`, `claude.ai/new?q=`) and the last icon
shows it inline. The site origin is only known in the browser, so the prompt
is completed after mount. The row sits at 80% opacity (100% on hover) so it
reads as a step below the buttons. The button's two labels ("Copy instructions
for agent" / "Copied") are stacked in one grid cell and swapped with
`visibility`, so on a phone, where the long one wraps to two lines, the row
keeps its height while "Copied" shows. The closing band has the same two buttons
on lime and the same row in its white `prompt--light` variant;
the nav has no button at all, just the GitHub / X / Discord icon links. The
Figma file's `uv add effecton` install pill is gone from all three places.

## Notes on the source file

A few things in the Figma file needed a judgement call:

1. **The hero headline is Zodiak, not PP Kyoto.** The text node's `fontName` says
   `PP Kyoto / Medium`, but every character carries a style override back to
   `Zodiak / Regular`. Zodiak is what Figma actually renders, and it is freely
   available — so no commercial font is required. The headline's last word
   (Figma's "scales") carries a radial gradient, `#C5FF51 → #F6FF7E`,
   reproduced with `background-clip: text`. The headline is now "Python
   optimized for …" with that last word rotating through *AI*, *type safety*
   and *correctness* every 2.6s (`RotatingWord`). On large screens (≥1260px,
   `HERO_ANCHORED`) the line is laid out once so "Python optimized for"
   never moves: an invisible sizer holds the first word's width, the words
   are positioned over it, and the box is widened just enough that, with the
   line centred, *correctness* ends at the content edge (the prefix lands
   ~77px left of where *AI* alone would centre it, then stays put).
   `clip-path` rather than `overflow` clips the slide so the overrun isn't
   cut. Below 1260px the longest line no longer fits the column, so the box
   is the visible word's width and the centred line re-centres (eased) with
   each word, wrapping naturally on phones. `prefers-reduced-motion` leaves
   it on *AI*.

2. **The hero's background image was a moodboard leftover.** The `cluster-1 1`
   layer behind the hero is a 2458 × 4096 PNG — a full screenshot of an
   unrelated marketing site — stretched into a 1446 × 633 box. All that reads
   through in the design is a faint dot field, so that is rebuilt rather than
   shipping someone else's page as an asset. See **The hero dot field** below.

3. **Placeholder boxes now carry copy.** Four frames were empty in the design:
   the two comparison panels and the "E.Effect describes your program" cards.
   They are filled with representative content — a before/after Python snippet
   and three cards on what an `Effect` is. The two "AI-Era ready" cards had
   lorem ipsum, also replaced. **All of this is placeholder copy: swap it.**

4. **The 56px yellow strip at the bottom is not rendered.** The artboard
   (`#FFED2A`, 2975px) is taller than its content stack (2919px), so the frame
   fill shows through underneath. That reads as an artboard artifact, not a
   design element.

5. **The nav is sticky and page-coloured, by request.** Figma draws it as a
   static `#020202` bar inside the hero frame. It now sits at `body` level
   (outside `.hero`) so `position: sticky` holds for the whole page rather than
   only while the hero is on screen, and its fill matches `--bg`. It keeps the
   1px bottom rule Figma specifies. Below vocs' md breakpoint the content
   column gets `overflow-x: hidden`, which would make it the nav's scroll
   container (the nav would sit 32px down and never stick); a top-level
   `article:has(> .landing)` rule in `landing.css` restores `overflow: visible`.

6. **Responsive behaviour is an extrapolation.** The file is a single fixed
   1440px artboard. Desktop rendering is pixel-accurate to it; the breakpoints
   at 1440 / 1360 / 1260 / 1100 / 900 / 620 are additions. The two around
   1300 exist for the comparison panels: a 68-column line needs ~534px at
   12px, so at ≤1360 the gutter drops to 48px, the panel gap to 32px and the
   code to 12px (which is exactly enough at 1280), and below 1260 the panels
   stack at 13px with no minimum height. At ≤700 the nav's links and social
   icons don't fit beside the mark, so they fold into a panel under the bar
   behind a hamburger (`Nav`, `NAV_MENU_MAX`); it closes on Escape, on a
   link, and when the viewport grows past the breakpoint. At ≤620 the signature bar in
   the describe section is broken over seven lines the way ruff would print
   it (one parameter per line, trailing commas): the JSX carries both the
   one-line and the multi-line separators in `<Sep>` spans and CSS shows one
   set, at 13px so the widest line (31 columns) fits a 375px screen.

## The comparison section is interactive

The three chips above the panels — **Timeout**, **Retry**, **Trace** — form a
ladder, and that is the argument the headline ("Harden it, one line at a time")
is making. The chips are cumulative: turning one on turns on everything before
it, turning one off drops everything after it, so there are four states, not
eight, and each state is the previous one plus one guarantee. Both sides start
from the same job: fetch `/users/{id}` and return the document as text.
Both keep that `fetch_profile` untouched and add a `load_profile` wrapper. The
left takes an `httpx.AsyncClient` argument; the right takes only `user_id` and
requires `E.HttpClient.Protocol` (`yield from E.require(...)` at the top of
the body), so the third slot of every signature names what the program needs
and the caller provides it at the edge. On the right each rung is one more
call in a single chain (`.timeout(...)`,
`.retry(...)` with the schedule and the `until` lambda inline,
`.with_span(...)`); on the left each rung wraps the previous one in another
block, so the retry loop has to catch the timeout and the spans have to sit
inside the loop. The 4xx status is the detail to watch: the `until` lambda
stops the retry on it on the right, and the loop re-raises it on the left, so
a client error is never retried on either side.

| Level | Without Effecton | With Effecton |
| --- | --- | --- |
| plain | 9 lines | 17 lines |
| + timeout | 18 | 25 |
| + retry | 33 | 36 |
| + trace | 42 | 38 |

Both snippets are emitted as plain Python by `buildWithout()` / `buildWith()`
in `snippets.ts` and then run through a small tokeniser, so there is no templated
HTML to keep in sync and all 4 levels stay valid Python. Both sides are
complete modules with nothing hidden. The with-Effecton side is also
**type-checked by ty and gets type hovers**: `LandingPage.tsx` (a server
component) runs each level through the shared ty twoslasher (`docs/twoslash/`)
and passes
the hover ranges to `<Landing>`. `highlight()` wraps them in `.hv` spans and
`CodePanel` shows one `.hv-pop` popup. A type error in a with-Effecton snippet
fails `pnpm build`, which is how the snippets stay honest against the library.
The without side is not part of the build gate; when you edit it, dump the
levels to files and check them by hand with
`uv run --with opentelemetry-api --with httpx ty check` and
`ruff format --line-length 68`.
Details worth knowing if you edit it:

- Each panel highlights the lines its current rung added: `addedLines()` in
  `snippets.ts` runs a longest-common-subsequence diff over whole lines
  between the rung below and the current one, `highlight()` wraps every line
  in a `.ln` span and marks those as `.is-add` (a lime wash across the panel's
  full width plus a 2px bar), and the line count gains a `+N` / `−N` delta.
  The comparison is always against the rung *below*, whichever direction the
  chip was toggled from, so the state is a pure function of the level and the
  server render (level 0) has nothing highlighted. A changed line counts as
  added, which is why a rung that reformats the chain (one call on one line
  becoming a multi-line call) highlights the whole chain. The `<pre>` is keyed
  on its source so the wash's flash animation replays on every change.
- **Phones don't get the ladder.** At 620px and below the chips and both
  panels are hidden and `buildMobile()` renders instead: one complete
  33-line, 46-column program that fits a 375px screen with no sideways
  scrolling: two plain error classes (`TooLate`, `Closed`), a `greet` under
  `@E.gen` that fails with either, then a chain whose rungs carry their own
  captions (`.retry(  # typesafe retries` with an `until` that gives up on
  `Closed`, `.with_span(  # observability built in`) and `E.run_main`. The
  comments sit after the opening paren so ruff keeps each call expanded and
  the caption stays on the rung's first line. The section goes edge to
  edge there (no gutter, no side rules, no panel radius) and only the title
  and eyebrow keep the text inset. The snippet is type-checked like the
  levels (`MOBILE_KEY` in `LandingPage.tsx`) and it runs; keep it at 46
  columns or fewer (`ruff format --line-length 46`, rendered at 12px with
  16px panel padding) and re-run it if you edit it. Both variants are in the server
  render and CSS picks one, so there is no layout flash.
- Panels size to their own content (`align-items: start`) with the Figma
  `418px` as a floor. The height gap between the two columns is the payoff, so
  they are deliberately *not* equal-height.
- Line counts are close on the first rungs and the right pulls ahead only at
  the end; what the ladder shows is the *delta* per rung and where it lands:
  one call in a chain versus a block around a loop, and a signature that grows
  (`FetchError | E.TimeoutException`, hover it) versus one that still says
  `-> str`.
- The timeout is per attempt on both sides: `.timeout()` sits inside `.retry()`,
  and the hand-rolled loop catches `TimeoutError` next to transport errors.
- The left keeps the parentheses in `except (httpx.TransportError, TimeoutError):`.
  `ruff format` targeting 3.14 would drop them (PEP 758); they stay because the
  bare form reads like Python 2 to most visitors.
- The chips are real `<input type="checkbox">` elements inside their labels, so
  they are keyboard- and screen-reader-operable. `autoComplete="off"` stops
  the browser restoring a previous visit's selection over the default state.
- Each chip shows an actual checkbox: an empty 16px rounded square when off,
  filled lime with a dark tick when on. That empty box is what signals an
  unselected chip is clickable. All chip surfaces are opaque (`--chip-bg`,
  `--chip-bg-on`, `--chip-box`) rather than alpha-composited, so nothing in the
  control row is see-through.
- The server render ships the default state (nothing selected), so the
  section is correct with JavaScript disabled and there is no flash of
  different code on load.
- Every emitted line fits the 68 characters a panel shows at 1440px, laid out
  the way `ruff format --line-length 68` prints it, so nothing is clipped and
  the panels never scroll sideways. Check that again after editing the
  generators.
- The argument is shape and types, not brevity. Both sides keep the plain
  `fetch_profile` and add a `load_profile` wrapper from the first rung on.

## The building-blocks section

Figma has the title on the left and a three-item list on the right. It is now
the title across the top and two columns under it: on the left a "cloud" of
what ships in `effecton.std` (`SERVICES`, name plus a one-line note), on the
right the list of things to build. The cloud is a centred `flex-wrap` so the
rows come out ragged on both sides, which is what stops it from reading as a
table. Keep `SERVICES` honest against
`packages/effecton/src/effecton/__init__.py` when a service is added or
renamed. At 620px and below the pills named in `PHONE_HIDDEN` (pretty
logger, clock, tracer) are hidden so the cloud stays to six pills on a
phone.

## The hero dot field

`.hero__dots` is a canvas doing three things at once. Brightness is quoted as
alpha over `#101010`; the resting texture was measured off the reference field
so it matches.

| Element | Rest | Under the pointer |
| --- | --- | --- |
| plain dot | 0.090 | 0.306 |
| dot belonging to the "E" | 0.157 – 0.373 (waves) | 0.576 |
| link between two "E" dots | 0.040 – 0.110 (waves) | 0.240 |

- **Even, no vignette.** 16px pitch, uniform across the whole frame.
- **A connected-dot "E".** The real mark from `assets/logo-mark.svg` is
  rasterised at one pixel per grid cell, and the cells it covers get a brighter
  dot plus faint links to their orthogonal neighbours. The links are what make
  it read as a letter rather than a brighter smudge. It is sized to ~86% of the
  hero's height (capped at 62% of its width so narrow viewports don't clip it),
  which puts the top and bottom bars in the empty bands above the badge and
  below the buttons instead of entirely behind the headline.
- **An endless wave down the glyph.** Each glyph dot and link carries a phase
  derived from its position, leaning vertical (`y * 0.85 + x * 0.35`) so the
  E's three bars light in sequence. One wave spans the glyph's height and a
  cycle takes ~3.9s. The dot swings between 0.157 and 0.373, so it breathes
  without ever flashing. **The midpoint matters:** the swing is centred so the
  trough still sits ~1.7× above the plain field (0.090). Lower it and the E
  dissolves into the grid for part of every cycle rather than staying legible
  throughout.
- **Pointer proximity glow**, 150px radius, quadratic falloff. Dots and links
  are lifted *toward* their targets rather than having a delta added, so the
  wave crest and the glow cannot compound into a hotspot. Dots also swell to
  1.8× radius near the pointer, which carries the effect further than
  brightness alone. The pointer position is eased per frame.

Because the wave never stops, an `IntersectionObserver` halts the loop once the
hero scrolls out of view and restarts it on the way back. Hovering, waving and
swelling all at once measures a locked 120Hz (8.3ms median, 9.4ms worst frame).

Degradation: `(hover: hover)` gates the glow, and `prefers-reduced-motion`
switches off the wave *and* the glow, rendering the glyph flat at its midpoint.
With no JavaScript at all, `.hero__inner::before` paints the same dot grid in
CSS and `dot-field.ts` hides it once the canvas is up.

Four things to watch if you touch this:

- Only the **plain** dots are pre-rendered into the static layer. The glyph has
  to be redrawn every frame now that it waves, so it must stay off that layer.
- If you retune the glyph, check the wave **trough** against the plain dot
  alpha, not just the crest. The crest is what you notice while editing; the
  trough is what decides whether the E reads continuously.
- Size the backing store from `canvas.getBoundingClientRect()`, not the host's.
  `.hero__inner` has a 1px border, so its border-box is ~2px wider than the
  canvas's own box; measuring the host offsets and stretches the whole field.
- Blit the static layer with an identity transform (`drawImage(base, 0, 0)`),
  not scaled into a CSS-pixel rect. On a fractional `devicePixelRatio` the
  scaled path resamples every dot, softening it and drifting its peak alpha.
- Per-frame draws are grouped into a `Map` keyed on quantised alpha **and**
  quantised radius, which keeps a frame down to a handful of fill calls even
  though every element's alpha is now unique.

## Fidelity

Rendered at 1440px against the Figma node boxes:

| Element | Figma | Rendered |
| --- | --- | --- |
| Hero headline | 582 × 86 | 581.2 × 86.4 |
| Hero subhead | 510 × 27 | 511.1 × 26.7 |
| Code panel | 575 × 418 | 575 × 418 |
| Closing headline | 1151 × 54 | 1150.4 × 54 |
| Hero CTA button | 167 × 56 | 167 × 56 |
| Install pill | 240 × 56 | 240 × 56 |
| Full page height | 2919 | 2923 |

The page is taller than the artboard in its default state (3155px) because the
left-hand code panel grows past 418px to hold real code.
