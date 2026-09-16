// The comparison playground's Python emitters and the tokeniser that colours
// their output. Pure functions: the component renders their output.
//
// Both sides load a profile document from one endpoint. The guarantees form
// a ladder: each level keeps everything below it and
// adds one more, so the left panel compounds (the retry loop has to catch
// the timeout, the span has to sit inside the loop) while the right adds a
// line to a chain. Every line is kept to 68 characters, the width of a code
// panel at 1440px, and laid out the way `ruff format --line-length 68`
// would print it.
//
// The with-Effecton side is type-checked by ty at build time (see
// `twoslash/README.md`): `LandingPage.tsx` runs every level through the ty
// twoslasher and hands the hover data to `highlight()`. Both sides are
// complete modules; nothing is hidden.

/** The guarantees, in ladder order: picking one turns on everything before it. */
export const STEPS = [
  { key: 'timeout', label: 'Timeout' },
  { key: 'retry', label: 'Retry' },
  { key: 'trace', label: 'Trace' },
] as const

/** How many guarantees are on, counted from the start of STEPS. */
export type Level = 0 | 1 | 2 | 3

/** Every level, in the order the README's line-count table lists them. */
export const ALL_LEVELS: readonly Level[] = [0, 1, 2, 3]

export function levelKey(level: Level): string {
  return String(level)
}

/** Hover key for the phone-width snippet (`buildMobile`), next to the levels. */
export const MOBILE_KEY = 'mobile'

/**
 * What phones get instead of the ladder: one complete program that fits a
 * 375px screen without scrolling sideways (46 columns at 12px, 33 lines): two
 * plain error classes, a @gen program that fails with either, and a chain
 * whose rungs carry their own captions: a retry whose `until` gives up on one
 * error, then a span. It is type-checked like the with-Effecton levels and
 * it runs.
 */
export function buildMobile(): string {
  return MOBILE
}

const MOBILE = `import effecton as E


class TooLate(E.EffectonError): ...


class Closed(E.EffectonError): ...


@E.gen
def greet(
    name: str,
) -> E.EffectGen[str, TooLate | Closed]:
    now = yield from E.now()
    if now.weekday() == 6:
        yield from E.fail(Closed())
    if now.hour >= 22:
        yield from E.fail(TooLate())
    return f"hello {name}"


program = (
    greet("ada")
    .retry(  # typesafe retries
        E.Schedule.spaced(minutes=1),
        until=lambda e: isinstance(e, Closed),
    )
    .with_span(  # observability built in
        "greet"
    )
)

E.run_main(program)`

export function buildWithout(level: Level): string {
  const timeout = level >= 1
  const retry = level >= 2
  const trace = level >= 3
  const L: string[] = []

  // isort: stdlib first, plain imports before from-imports, then third party.
  if (timeout) L.push('import asyncio')
  if (retry) L.push('import random')
  if (timeout) L.push('')
  L.push('import httpx')
  if (trace) L.push('from opentelemetry import trace')
  L.push('')
  if (trace) L.push('tracer = trace.get_tracer(__name__)', '')
  L.push('')

  L.push('async def fetch_profile(')
  L.push('    client: httpx.AsyncClient, user_id: int')
  L.push(') -> str:')
  L.push('    response = await client.get(f"/users/{user_id}")')
  L.push('    response.raise_for_status()')
  L.push('    return response.text')

  if (timeout) {
    L.push('', '')
    L.push('async def load_profile(')
    L.push('    client: httpx.AsyncClient, user_id: int')
    L.push(') -> str:')
    // Each guarantee is one more level of nesting around the call.
    let body = ['async with asyncio.timeout(5):', '    return await fetch_profile(client, user_id)']
    if (trace) {
      body = [
        'with tracer.start_as_current_span(',
        '    "fetch_profile", attributes={"user_id": user_id}',
        '):',
        ...body.map((line) => (line ? `    ${line}` : line)),
      ]
    }
    if (retry) {
      body = [
        'attempt = 0',
        'delay = 0.1',
        '',
        'while True:',
        '    try:',
        ...body.map((line) => (line ? `        ${line}` : line)),
        '    except httpx.HTTPStatusError as exc:',
        '        if exc.response.status_code < 500 or attempt == 5:',
        '            raise',
        '    except (httpx.TransportError, TimeoutError):',
        '        if attempt == 5:',
        '            raise',
        '    attempt += 1',
        '    await asyncio.sleep(delay * random.uniform(0.8, 1.2))',
        '    delay *= 2',
      ]
    }
    if (trace) {
      body = [
        'with tracer.start_as_current_span(',
        '    "load_profile", attributes={"user_id": user_id}',
        '):',
        ...body.map((line) => (line ? `    ${line}` : line)),
      ]
    }
    L.push(...body.map((line) => (line ? `    ${line}` : line)))
  }

  return L.join('\n')
}

export function buildWith(level: Level): string {
  const timeout = level >= 1
  const retry = level >= 2
  const trace = level >= 3
  const L: string[] = []

  L.push('import effecton as E')
  L.push('', '')

  L.push('type FetchError = (')
  L.push('    E.HttpClient.TransportError | E.HttpClient.StatusError')
  L.push(')')
  L.push('', '')

  // The HTTP client is a requirement, not a parameter: the signature's third
  // slot says so, and whoever runs the program provides it.
  L.push('@E.gen')
  L.push('def fetch_profile(')
  L.push('    user_id: int,')
  L.push(') -> E.EffectGen[str, FetchError, E.HttpClient.Protocol]:')
  L.push('    http = yield from E.require(E.HttpClient.Protocol)')
  L.push('')
  L.push('    response = yield from http.get(f"/users/{user_id}")')
  L.push('    ok = yield from E.HttpClient.filter_status_ok(response)')
  L.push('    return ok.text')

  if (timeout) {
    L.push('', '')
    L.push('def load_profile(')
    L.push('    user_id: int,')
    L.push(') -> E.Effect[')
    L.push('    str, FetchError | E.TimeoutException, E.HttpClient.Protocol')
    L.push(']:')
    if (retry) {
      // Two or more calls in the chain: ruff lays it out fluently.
      L.push('    return (')
      L.push('        fetch_profile(user_id)')
      if (trace) L.push('        .with_span("fetch_profile", user_id=user_id)')
      L.push('        .timeout(seconds=5)')
      L.push('        .retry(')
      L.push('            E.Schedule.exponential(seconds=0.1).jittered(),')
      L.push('            times=5,')
      L.push('            until=lambda e: (')
      L.push('                isinstance(e, E.HttpClient.StatusError)')
      L.push('                and e.status < 500')
      L.push('            ),')
      L.push('        )')
      if (trace) L.push('        .with_span("load_profile", user_id=user_id)')
      L.push('    )')
    } else {
      L.push('    return fetch_profile(user_id).timeout(seconds=5)')
    }
  }

  return L.join('\n')
}

const KEYWORDS =
  'import|from|def|class|return|for|in|if|as|raise|except|try|break|while|else|elif|with|pass|and|or|not|is|None|True|False|async|await|yield|lambda|match|case|type'
const TYPES =
  'str|dict|int|float|bool|bytes|list|Exception|TimeoutError|FetchError'

const TOKEN = new RegExp(
  '(#[^\\n]*)' + // 1 comment
    '|("""[\\s\\S]*?"""|f?"(?:[^"\\\\]|\\\\.)*"|f?\'(?:[^\'\\\\]|\\\\.)*\')' + // 2 string
    '|(@[A-Za-z_][\\w.]*)' + // 3 decorator
    '|\\b(def|class)(\\s+)([A-Za-z_]\\w*)' + // 4 5 6 binding
    '|\\b(' +
    KEYWORDS +
    ')\\b' + // 7 keyword
    '|\\b(' +
    TYPES +
    ')\\b' + // 8 type
    '|\\b(\\d+(?:\\.\\d+)?)\\b', // 9 number
  'g',
)

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/**
 * A hover computed by ty for a rendered snippet: 0-based line, UTF-16 column,
 * length, and an index into the shared table of hover texts.
 */
export type HoverRef = readonly [line: number, character: number, length: number, text: number]

type Run = { start: number; end: number; cls: string | null }
type HoverSpan = { start: number; end: number; idx: number }

/** Splits a Python snippet into contiguous runs, coloured or plain. */
function tokenize(src: string): Run[] {
  const runs: Run[] = []
  const push = (start: number, end: number, cls: string | null) => {
    if (end > start) runs.push({ start, end, cls })
  }
  let last = 0
  let m: RegExpExecArray | null
  TOKEN.lastIndex = 0

  while ((m = TOKEN.exec(src)) !== null) {
    const end = m.index + m[0].length
    push(last, m.index, null)
    if (m[1]) push(m.index, end, 'c')
    else if (m[2]) push(m.index, end, 's')
    else if (m[3]) push(m.index, end, 'd')
    else if (m[4]) {
      const nameStart = m.index + m[4].length + m[5]!.length
      push(m.index, m.index + m[4].length, 'k')
      push(m.index + m[4].length, nameStart, null)
      push(nameStart, end, 'n')
    } else if (m[7]) push(m.index, end, 'k')
    else if (m[8]) push(m.index, end, 't')
    else if (m[9]) push(m.index, end, 's')
    last = end
  }
  push(last, src.length, null)

  return runs
}

function hoverSpans(src: string, hovers: readonly HoverRef[]): HoverSpan[] {
  const lineStarts = [0]
  for (let i = 0; i < src.length; i++) if (src[i] === '\n') lineStarts.push(i + 1)
  const spans: HoverSpan[] = []
  for (const [line, character, length, idx] of hovers) {
    const lineStart = lineStarts[line]
    if (lineStart === undefined) continue
    const start = lineStart + character
    const end = Math.min(start + length, src.length)
    if (end > start) spans.push({ start, end, idx })
  }
  spans.sort((a, b) => a.start - b.start)
  return spans
}

/**
 * Colours a Python snippet; the result is HTML made of <span class="k|n|d|s|t|c"> runs.
 * With `hovers`, the covered ranges are additionally wrapped in
 * <span class="hv" data-hv="i"> so the component can show ty's type on hover.
 */
/**
 * Renders `src` as HTML. Every line is wrapped in a `.ln` span; lines whose
 * (0-based) index is in `added` also get `.is-add`, which is how the panels
 * highlight what the current rung contributed (see `addedLines`).
 */
export function highlight(
  src: string,
  hovers: readonly HoverRef[] = [],
  added: ReadonlySet<number> = new Set(),
): string {
  const runs = tokenize(src)
  const spans = hoverSpans(src, hovers)
  const cuts = new Set<number>([0, src.length])
  for (const r of runs) cuts.add(r.start).add(r.end)
  for (const s of spans) cuts.add(s.start).add(s.end)
  // Cut at every newline too, so a run never crosses a line wrapper.
  for (let i = src.indexOf('\n'); i !== -1; i = src.indexOf('\n', i + 1)) cuts.add(i).add(i + 1)
  const points = [...cuts].sort((a, b) => a - b)

  const open = (line: number) => `<span class="${added.has(line) ? 'ln is-add' : 'ln'}">`
  let out = open(0)
  let line = 0
  let ri = 0
  let hi = 0
  for (let i = 0; i + 1 < points.length; i++) {
    const start = points[i]!
    const end = points[i + 1]!
    if (src[start] === '\n' && end === start + 1) {
      line++
      out += `</span>\n${open(line)}`
      continue
    }
    while (ri < runs.length && runs[ri]!.end <= start) ri++
    while (hi < spans.length && spans[hi]!.end <= start) hi++
    const run = runs[ri]
    const span = spans[hi]
    let piece = esc(src.slice(start, end))
    if (run?.cls && run.start <= start) piece = `<span class="${run.cls}">${piece}</span>`
    if (span && span.start <= start) piece = `<span class="hv" data-hv="${span.idx}">${piece}</span>`
    out += piece
  }

  return `${out}</span>`
}

/**
 * The (0-based) indices of the lines in `next` that are not in `prev`: a
 * longest-common-subsequence diff over whole lines, so a changed line counts
 * as added. The panels use it to show what one rung of the ladder costs.
 */
export function addedLines(prev: string, next: string): ReadonlySet<number> {
  const a = prev.split('\n')
  const b = next.split('\n')
  // lcs[i][j] = length of the LCS of a[i..] and b[j..]
  const lcs: number[][] = Array.from({ length: a.length + 1 }, () =>
    new Array(b.length + 1).fill(0),
  )
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i]![j] =
        a[i] === b[j] ? lcs[i + 1]![j + 1]! + 1 : Math.max(lcs[i + 1]![j]!, lcs[i]![j + 1]!)
    }
  }

  const added = new Set<number>()
  let i = 0
  let j = 0
  while (j < b.length) {
    if (i < a.length && a[i] === b[j]) {
      i++
      j++
    } else if (i < a.length && lcs[i + 1]![j]! >= lcs[i]![j + 1]!) {
      i++
    } else {
      added.add(j)
      j++
    }
  }

  // An LCS is ambiguous around repeated lines (blank ones, mostly): inserting
  // `X` + blank before a blank can be reported as blank + `X`, which leaves a
  // highlighted blank line hanging under the real insertion. Slide every run
  // of added lines upward while the line above it equals the line that ends
  // it; the run keeps its content and comes to rest against the run above.
  for (let moved = true; moved;) {
    moved = false
    for (let end = b.length - 1; end >= 0; end--) {
      if (!added.has(end)) continue
      let start = end
      while (start > 0 && added.has(start - 1)) start--
      while (start > 0 && !added.has(start - 1) && b[start - 1] === b[end]) {
        added.delete(end)
        added.add(start - 1)
        start--
        end--
        moved = true
      }
      end = start
    }
  }
  return added
}

/** Colours a type as ty prints it, for the hover popup. */
export function highlightType(text: string): string {
  return highlight(text)
}

export function lineCount(src: string): string {
  const n = src.split('\n').length
  return `${n} ${n === 1 ? 'line' : 'lines'}`
}

/** The net line change from `prev` to `next`, as `+9` / `−2`, or `null` if equal. */
export function lineDelta(prev: string, next: string): string | null {
  const d = next.split('\n').length - prev.split('\n').length
  return d === 0 ? null : d > 0 ? `+${d}` : `−${-d}`
}
