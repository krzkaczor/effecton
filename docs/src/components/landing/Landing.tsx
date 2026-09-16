'use client'

import { useEffect, useRef, useState } from 'react'
import './landing.css'
import { mountDotField } from './dot-field'
import { MARK_H, MARK_PATH, MARK_W, WORDMARK_H, WORDMARK_PATHS, WORDMARK_W } from './mark'
import {
  CHATGPT_PATH,
  CLAUDE_PATH,
  DISCORD_PATH,
  GITHUB_PATH,
  SCAN_PATH,
  SPARKLE_PATH,
  X_PATH,
} from './social'
import {
  type HoverRef,
  type Level,
  MOBILE_KEY,
  STEPS,
  addedLines,
  buildMobile,
  buildWith,
  buildWithout,
  highlight,
  highlightType,
  levelKey,
  lineCount,
  lineDelta,
} from './snippets'

/** Type hovers for the with-Effecton panel, computed by ty in LandingPage.tsx. */
export type Hovers = {
  /** Hover ranges per `levelKey`, into the rendered snippet. */
  hovers: Readonly<Record<string, readonly HoverRef[]>>
  /** The deduplicated hover texts the ranges point into. */
  texts: readonly string[]
}

const REPO = 'https://github.com/krzkaczor/effecton'
const DOCS = '/introduction'
const API_REFERENCE = '/api'
const CHANGELOG = 'https://github.com/krzkaczor/effecton/releases'
const X = 'https://x.com/krzkaczor'
const DISCORD = 'https://discord.gg/fNhY7AxMyh'
const TAGLINE = 'Building blocks for Python apps in the agentic era.'
/** The hero headline's rotating object; the first entry is the server render. */
const HERO_WORDS = ['AI', 'type safety', 'correctness'] as const
const HERO_WORD_MS = 2600

/** The std services in the building-blocks cloud: name and a one-line note. */
const SERVICES: readonly (readonly [string, string])[] = [
  ['HTTP client', 'sync and async, on httpx'],
  ['File system', 'sync and async'],
  ['In-memory file system', 'the Test double'],
  ['Pretty logger', 'levels, colour, annotations'],
  ['Clock', 'a test clock you can wind'],
  ['Tracer', 'OpenTelemetry spans'],
  ['Random', 'seedable in tests'],
  ['Process', 'cwd and home'],
  ['Schedule', 'spaced, exponential, jittered'],
]
/** Services the phone layout leaves out, so the cloud stays to one screen. */
const PHONE_HIDDEN = new Set(['Pretty logger', 'Clock', 'Tracer'])

export function Landing(props: Hovers) {
  return (
    <div className="landing">
      {/* ======================= Nav + Hero (Figma 1:32) ======================= */}
      <nav className="nav">
        <div className="nav__inner">
          <a href="/" aria-label="Effecton home">
            <Mark className="nav__mark" />
          </a>

          <ul className="nav__links">
            <li>
              <a href={DOCS}>Docs</a>
            </li>
            <li>
              <a href={API_REFERENCE}>API Reference</a>
            </li>
            <li>
              <a href={CHANGELOG}>Changelog</a>
            </li>
          </ul>

          <div className="nav__actions">
            <SocialLinks className="nav__social" />
          </div>
        </div>
      </nav>

      <Hero />

      <main>
        <Compare hovers={props.hovers} texts={props.texts} />

        {/* ================== Describe / white panel (Figma 1:85) ================== */}
        <section className="section describe">
          <div className="container container--ruled">
            <Rules />
            <div className="section-inner">
              <h2 className="h-serif describe__title">E.Effect describes your program</h2>

              {/* One signature, coloured by hand: the three type parameters are
                  the three channels the cards below explain, so each carries
                  the colour of its card's label. On phones it is broken over
                  seven lines the way ruff would print it; <Sep> holds both the
                  one-line and the multi-line separators and CSS picks one. */}
              <div className="describe__bar">
                <code>
                  <span className="k">def</span> <span className="n">charge</span>(
                  <Sep many={'\n    '} />
                  order: <span className="t">Order</span>
                  <Sep many={',\n'} />) -&gt; E.Effect[
                  <Sep many={'\n    '} />
                  <span className="ch ch--success">Receipt</span>,
                  <Sep one=" " many={'\n    '} />
                  <span className="ch ch--error">CardDeclined | CardExpired</span>,
                  <Sep one=" " many={'\n    '} />
                  <span className="ch ch--requirements">PaymentGateway</span>
                  <Sep many={',\n'} />
                  ]: ...
                </code>
              </div>

              <div className="describe__cards">
                <article className="describe__card">
                  <p className="describe__channel ch--success">Success · Receipt</p>
                  <h3>What it produces</h3>
                  <p>
                    The value a successful run hands back. Use,{' '}
                    <code>yield from charge(order)</code> and possible errors automatically
                    propagate. Just like with async / await code.
                  </p>
                </article>
                <article className="describe__card">
                  <p className="describe__channel ch--error">Error · CardDeclined | CardExpired</p>
                  <h3>How it can fail</h3>
                  <p>
                    Every expected failure, as a union of plain classes. Implement granular,
                    type-safe error handling with <code>catch(CardExpired)</code>.
                  </p>
                </article>
                <article className="describe__card">
                  <p className="describe__channel ch--requirements">
                    Requirements · PaymentGateway
                  </p>
                  <h3>What it needs</h3>
                  <p>
                    The services the program depends on. Inject Live dependencies in your production
                    code and mocks in tests. Type checker knows when you forget to do so.
                  </p>
                </article>
              </div>
            </div>
          </div>
        </section>

        {/* ==================== AI-era ready (Figma 1:97) ==================== */}
        <section className="section ai">
          <div className="container">
            <div className="section-inner">
              <h2 className="h-serif">Agent-era ready Python</h2>

              <div className="ai__cards">
                <article className="ai__card">
                  <h3>Type safe to the limit</h3>
                  <p>
                    Every function says what it returns, how it can fail and what it needs, right in
                    its signature. You and your agent sees the whole interface.
                  </p>
                </article>
                <article className="ai__card">
                  <h3>Unsloppable code</h3>
                  <p>
                    Agents love building from reusable building blocks. Small, typed, composable
                    primitives are easy for a model to reason about.
                  </p>
                </article>
                <article className="ai__card">
                  <h3>Your agent already knows Effecton</h3>
                  <p>
                    Just point it to <a href={DOCS}>the docs</a>. Your agent is already effecton
                    expert.
                  </p>
                </article>
              </div>
            </div>
          </div>
        </section>

        {/* ================= Building blocks (Figma 1:72) ================= */}
        <section className="section blocks" id="building-blocks">
          <div className="container">
            <div className="section-inner">
              <h2 className="h-serif blocks__title">Building blocks to build whatever you want</h2>

              <div className="blocks__grid">
                <div className="blocks__cloud">
                  <p className="eyebrow eyebrow--lime" id="cloud-label">
                    Building blocks
                  </p>
                  <ul className="cloud" aria-labelledby="cloud-label">
                    {SERVICES.map(([name, note]) => (
                      <li
                        key={name}
                        className={
                          PHONE_HIDDEN.has(name) ? 'cloud__pill cloud__pill--wide' : 'cloud__pill'
                        }
                      >
                        <span className="cloud__name">{name}</span>
                        <span className="cloud__note">{note}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="blocks__list">
                  <p className="eyebrow eyebrow--lime">What they add up to</p>
                  <article className="blocks__item">
                    <h3>Web APIs</h3>
                    <p>Typed handlers with built-in retries and tracing</p>
                  </article>
                  <article className="blocks__item">
                    <h3>Command-line tools</h3>
                    <p>Testable side effects, structured errors</p>
                  </article>
                  <article className="blocks__item">
                    <h3>ML pipelines</h3>
                    <p>Reliable steps that retry, time out, and log themselves</p>
                  </article>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ==================== Closing band (Figma 1:106) ==================== */}
      <section className="closing">
        <div className="closing__inner">
          <h2 className="h-serif closing__title">{TAGLINE}</h2>
          <div className="cta-row">
            <a className="btn btn--dark" href={DOCS}>
              Read the docs
            </a>
            <a className="btn btn--light" href={REPO}>
              <Icon path={GITHUB_PATH} />
              GitHub
            </a>
          </div>
          <AgentPrompt light />
        </div>
      </section>

      {/* ====================== Footer (Figma 1:117) ====================== */}
      <footer className="footer">
        <div className="container">
          <div className="section-inner">
            <a href="/" aria-label="Effecton home">
              <Wordmark className="footer__wordmark" />
            </a>
            <ul className="footer__links">
              <li>
                <a href={DOCS}>Docs</a>
              </li>
              <li>
                <a href={CHANGELOG}>Changelog</a>
              </li>
            </ul>
            <SocialLinks className="footer__social" />
          </div>
        </div>
      </footer>
    </div>
  )
}

/* ---- Hero ------------------------------------------------------------- */

function Hero() {
  const host = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!host.current || !canvas.current) return
    return mountDotField(host.current, canvas.current)
  }, [])

  return (
    <header className="hero">
      <div className="hero__inner" ref={host}>
        <canvas className="hero__dots" aria-hidden="true" ref={canvas} />
        <div className="hero__badge">
          <Wordmark className="hero__wordmark" />
          <span className="tag">Alpha stage</span>
        </div>

        <h1 className="hero__title">
          Python optimized for <RotatingWord />
        </h1>

        <p className="hero__sub">{TAGLINE}</p>

        <div className="cta-row">
          <a className="btn btn--light" href={DOCS}>
            Read the docs
          </a>
          <a className="btn btn--ghost" href={REPO}>
            <Icon path={GITHUB_PATH} />
            GitHub
          </a>
        </div>

        <AgentPrompt />
      </div>
    </header>
  )
}

// Two behaviours, split at HERO_ANCHORED. On large screens the headline is
// laid out once and "Python optimized for" never moves: the box is widened
// from the first word's width just enough that, with the line centred, the
// longest word ends at the content edge; every word is positioned over that
// box and runs on to the right. Below the breakpoint the longest line no
// longer fits, so the box is the visible word's width and the centred line
// re-centres (eased) with each word, wrapping naturally on phones.
const HERO_ANCHORED = '(min-width: 1260px)'

function RotatingWord() {
  const [index, setIndex] = useState(0)
  const [anchored, setAnchored] = useState(false)
  const [width, setWidth] = useState<number>()
  const box = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const id = setInterval(() => setIndex((i) => (i + 1) % HERO_WORDS.length), HERO_WORD_MS)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const el = box.current
    const title = el?.closest<HTMLElement>('.hero__title')
    const area = title?.parentElement
    if (!el || !title || !area) return
    const words = [...el.querySelectorAll('em')]
    const measure = () => {
      const widths = words.map((em) => em.getBoundingClientRect().width)
      const large = window.matchMedia(HERO_ANCHORED).matches
      setAnchored(large)
      if (!large) return setWidth(widths[index])

      const first = widths[0] ?? 0
      const longest = Math.max(...widths)
      const prefix = el.getBoundingClientRect().left - title.getBoundingClientRect().left
      const style = getComputedStyle(area)
      const room =
        area.clientWidth -
        Number.parseFloat(style.paddingLeft) -
        Number.parseFloat(style.paddingRight)
      setWidth(Math.max(first, prefix + 2 * longest - room))
    }
    document.fonts.ready.then(measure)
    const observer = new ResizeObserver(measure)
    observer.observe(area)
    for (const em of words) observer.observe(em)
    return () => observer.disconnect()
  }, [index])

  const previous = (index + HERO_WORDS.length - 1) % HERO_WORDS.length
  return (
    <span
      className={anchored ? 'rotate' : 'rotate is-fluid'}
      style={width === undefined ? undefined : { width }}
      ref={box}
    >
      <span className="rotate__sizer" aria-hidden="true">
        {HERO_WORDS[0]}
      </span>
      {HERO_WORDS.map((word, i) => (
        <em
          key={word}
          className={i === index ? 'is-on' : i === previous ? 'is-out' : undefined}
          aria-hidden={i !== index}
        >
          {word}
        </em>
      ))}
    </span>
  )
}

/* ---- Comparison playground -------------------------------------------- */

// The visitor climbs a ladder of guarantees; both panels are regenerated. The
// chips are cumulative: turning one on turns on everything before it, and
// turning one off drops everything after it. The point of the section is that
// each rung is one line in a chain on the right and a block of bookkeeping
// wrapped around the previous rung on the left, so the left has to compound
// to stay honest. Each panel highlights the lines its current rung added
// relative to the rung below, whichever direction the visitor came from, so
// the cost of a guarantee is visible on both sides at once.

function Compare(props: Hovers) {
  const [level, setLevel] = useState<Level>(0)
  const without = buildWithout(level)
  const withE = buildWith(level)
  const hovers = props.hovers[levelKey(level)] ?? []
  const below = level === 0 ? null : ((level - 1) as Level)
  const prevWithout = below === null ? without : buildWithout(below)
  const prevWith = below === null ? withE : buildWith(below)
  const mobile = buildMobile()

  return (
    <section className="section compare">
      <div className="container container--ruled">
        <Rules />
        <div className="section-inner">
          <h2 className="h-serif compare__title">Harden it, one line at a time</h2>

          {/* Phones get one short program instead of the ladder (CSS swaps the
              two; both are in the server render). */}
          <div className="compare__mobile">
            <CodePanel
              eyebrow="With Effecton"
              source={mobile}
              previous={mobile}
              hovers={props.hovers[MOBILE_KEY] ?? []}
              texts={props.texts}
              lime
            />
          </div>

          <div className="compare__desktop">
            <div className="compare__controls">
              <p className="compare__controls-label" id="guarantees-label">
                Add a guarantee
              </p>
              <div className="chips" role="group" aria-labelledby="guarantees-label">
                {STEPS.map(({ key, label }, i) => {
                  const on = i < level
                  return (
                    <label key={key} className={on ? 'chip is-on' : 'chip'}>
                      <input
                        type="checkbox"
                        autoComplete="off"
                        checked={on}
                        onChange={(e) => setLevel((e.target.checked ? i + 1 : i) as Level)}
                      />
                      <span className="chip__box" aria-hidden="true">
                        <svg viewBox="0 0 12 12">
                          <path d="M1.6 6.3 4.4 9 10.4 2.7" />
                        </svg>
                      </span>
                      <span>{label}</span>
                    </label>
                  )
                })}
              </div>
            </div>

            <div className="compare__grid">
              <CodePanel eyebrow="Without Effecton" source={without} previous={prevWithout} />
              <CodePanel
                eyebrow="With Effecton"
                source={withE}
                previous={prevWith}
                hovers={hovers}
                texts={props.texts}
                lime
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

type Popup = { idx: number; left: number; top: number; maxWidth: number }

function CodePanel(props: {
  eyebrow: string
  source: string
  /** The rung below's snippet; lines not in it are highlighted as added. */
  previous: string
  lime?: boolean
  hovers?: readonly HoverRef[]
  texts?: readonly string[]
}) {
  const col = useRef<HTMLDivElement>(null)
  const [popup, setPopup] = useState<Popup | null>(null)
  const added = addedLines(props.previous, props.source)
  const delta = lineDelta(props.previous, props.source)

  // A new snippet means the hovered span is gone.
  useEffect(() => setPopup(null), [props.source])

  function showFor(target: EventTarget | null) {
    const span = target instanceof Element ? target.closest('.hv') : null
    if (!span || !col.current) return setPopup(null)
    const idx = Number(span.getAttribute('data-hv'))
    const box = span.getBoundingClientRect()
    const colBox = col.current.getBoundingClientRect()
    const left = box.left - colBox.left
    setPopup({
      idx,
      left,
      top: box.bottom - colBox.top + 4,
      maxWidth: colBox.width - left,
    })
  }

  const text = popup && props.texts?.[popup.idx]
  return (
    <div className="compare__col" ref={col}>
      <p className={props.lime ? 'eyebrow eyebrow--lime' : 'eyebrow'}>
        <span>{props.eyebrow}</span>
        <span className="loc">
          {lineCount(props.source)}
          {delta && (
            <>
              {' '}
              <span className="loc__delta">{delta}</span>
            </>
          )}
        </span>
      </p>
      <pre
        key={props.source}
        className="code"
        onMouseOver={(e) => showFor(e.target)}
        onMouseLeave={() => setPopup(null)}
      >
        <code
          dangerouslySetInnerHTML={{
            __html: highlight(props.source, props.hovers, added),
          }}
        />
      </pre>
      {popup && text && (
        <div
          className="hv-pop"
          role="tooltip"
          style={{ left: popup.left, top: popup.top, maxWidth: popup.maxWidth }}
          dangerouslySetInnerHTML={{ __html: highlightType(text) }}
        />
      )}
    </div>
  )
}

/* ---- Bits ------------------------------------------------------------- */

/** GitHub, X and Discord as icon links; the nav and the footer both carry them. */
function SocialLinks(props: { className: string }) {
  return (
    <ul className={`social ${props.className}`}>
      <li>
        <a className="social__link" href={REPO} aria-label="Effecton on GitHub" title="GitHub">
          <Icon path={GITHUB_PATH} />
        </a>
      </li>
      <li>
        <a className="social__link" href={X} aria-label="@krzkaczor on X" title="@krzkaczor on X">
          <Icon path={X_PATH} />
        </a>
      </li>
      <li>
        <a className="social__link" href={DISCORD} aria-label="Effecton on Discord" title="Discord">
          <Icon path={DISCORD_PATH} />
        </a>
      </li>
    </ul>
  )
}

/** A separator in the describe bar's signature: `one` on one line, `many` when it wraps. */
function Sep(props: { one?: string; many: string }) {
  return (
    <>
      {props.one && <span className="bar-one">{props.one}</span>}
      <span className="bar-many">{props.many}</span>
    </>
  )
}

/**
 * The vocs-style "Copy instructions for agent" row under the hero buttons
 * (and, in its `light` variant, under the closing band's):
 * the button copies a one-line prompt, the icons open the same prompt in
 * ChatGPT or Claude, and the last one shows the prompt inline. The prompt
 * names this site's docs URL, which is only known in the browser, so it is
 * filled in after mount (the server render carries the path alone).
 */
function AgentPrompt(props: { light?: boolean }) {
  const [copied, setCopied] = useState(false)
  const [shown, setShown] = useState(false)
  const [origin, setOrigin] = useState('')
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    setOrigin(window.location.origin)
    return () => clearTimeout(timer.current)
  }, [])

  const prompt = `Read ${origin}${DOCS} and set up effecton in my project.`
  const query = encodeURIComponent(prompt)

  async function copy() {
    try {
      await navigator.clipboard.writeText(prompt)
    } catch {
      // Clipboard API needs a secure context; fall back to a temp selection.
      const ta = document.createElement('textarea')
      ta.value = prompt
      ta.setAttribute('readonly', '')
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
    }

    setCopied(true)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className={props.light ? 'prompt prompt--light' : 'prompt'}>
      <div className="prompt__row">
        <button
          className={copied ? 'prompt__copy is-copied' : 'prompt__copy'}
          type="button"
          onClick={copy}
        >
          <Icon path={SPARKLE_PATH} />
          <span aria-live="polite">{copied ? 'Copied' : 'Copy instructions for agent'}</span>
        </button>
        <div className="prompt__actions">
          <a
            className="prompt__action"
            href={`https://chatgpt.com?hints=search&q=${query}`}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open in ChatGPT"
            title="Open in ChatGPT"
          >
            <Icon path={CHATGPT_PATH} />
          </a>
          <a
            className="prompt__action"
            href={`https://claude.ai/new?q=${query}`}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open in Claude"
            title="Open in Claude"
          >
            <Icon path={CLAUDE_PATH} />
          </a>
          <button
            className={shown ? 'prompt__action is-on' : 'prompt__action'}
            type="button"
            aria-expanded={shown}
            aria-label="View prompt"
            title="View prompt"
            onClick={() => setShown((v) => !v)}
          >
            <Icon path={SCAN_PATH} stroke />
          </button>
        </div>
      </div>
      {shown && <p className="prompt__text">{prompt}</p>}
    </div>
  )
}

/** A 24 × 24 glyph from social.ts; `stroke` for the line icons. */
function Icon(props: { path: string; stroke?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill={props.stroke ? 'none' : 'currentColor'}
      stroke={props.stroke ? 'currentColor' : undefined}
      strokeWidth={props.stroke ? 2 : undefined}
      strokeLinecap={props.stroke ? 'round' : undefined}
      strokeLinejoin={props.stroke ? 'round' : undefined}
    >
      <path d={props.path} />
    </svg>
  )
}

/** The 6-column vertical rule overlay behind a ruled container. */
function Rules() {
  return (
    <div className="rules" aria-hidden="true">
      <span />
      <span />
      <span />
      <span />
      <span />
      <span />
    </div>
  )
}

function Mark(props: { className: string }) {
  return (
    <svg
      className={props.className}
      viewBox={`0 0 ${MARK_W} ${MARK_H}`}
      fill="currentColor"
      aria-hidden="true"
    >
      <path d={MARK_PATH} />
    </svg>
  )
}

function Wordmark(props: { className: string }) {
  return (
    <svg
      className={props.className}
      viewBox={`0 0 ${WORDMARK_W} ${WORDMARK_H}`}
      fill="currentColor"
      aria-hidden="true"
    >
      {WORDMARK_PATHS.map((d) => (
        <path key={d.slice(0, 24)} d={d} />
      ))}
    </svg>
  )
}
