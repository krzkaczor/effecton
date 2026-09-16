// The ty twoslasher: snippet in, twoslash nodes out.
//
// Synchronous by necessity (shiki transformers are), so the language-server
// session runs in a child process (`ty-client.ts`) driven with `spawnSync`,
// with results cached on disk keyed on the snippet, ty and the library.

import { spawnSync } from 'node:child_process'
import * as path from 'node:path'
import {
  createPositionConverter,
  type NodeError,
  type NodeHover,
  type NodeQuery,
  type NodeWithoutPosition,
  removeCodeRanges,
  resolveNodePositions,
  type TwoslashNode,
} from 'twoslash-protocol'
import { TyUnavailableError, cacheKey, readCache, tyVersion, writeCache } from './cache.ts'
import { parseDirectives } from './directives.ts'
import { normalizeHover } from './hover.ts'
import type { ClientDiagnostic, ClientInput, ClientOutput } from './ty-client.ts'

export type Mode = 'dev' | 'build'

export type TyTwoslasherOptions = {
  /** vocs' cache directory; defaults to `<docsDir>/node_modules/.cache/vocs`. */
  cacheDir?: string | undefined
  /** Repository root, where `uv run ty server` is launched. Defaults to the parent of `docsDir`. */
  rootDir?: string | undefined
  /** The docs site directory. Defaults to `process.cwd()`, which is where vocs runs. */
  docsDir?: string | undefined
  /** `build` fails on undeclared errors and missing ty; `dev` warns and renders what it can. */
  mode?: Mode | undefined
}

export type TyTwoslashResult = { code: string; nodes: TwoslashNode[] }

/** A snippet failed the type gate or could not be analysed. */
export class TyTwoslashError extends Error {
  override name = 'TyTwoslashError'
}

export { TyUnavailableError } from './cache.ts'

const ERROR_SEVERITIES = new Set([1, 2])
const LEVELS: Record<number, NodeError['level']> = {
  1: 'error',
  2: 'warning',
  3: 'message',
  4: 'suggestion',
}

export function detectMode(): Mode {
  return process.argv.includes('build') ? 'build' : 'dev'
}

export function createTyTwoslasher(options: TyTwoslasherOptions = {}) {
  const docsDir = options.docsDir ?? process.cwd()
  const rootDir = options.rootDir ?? path.resolve(docsDir, '..')
  const cacheDir = path.join(options.cacheDir ?? path.join(docsDir, 'node_modules/.cache/vocs'), 'twoslash-ty')
  const mode = options.mode ?? detectMode()
  const clientPath = path.join(docsDir, 'twoslash', 'ty-client.ts')
  const disabled = process.env['TY_TWOSLASH'] === 'off'
  const debug = process.env['TY_TWOSLASH_DEBUG'] === '1'
  const memory = new Map<string, ClientOutput>()
  let warnedUnavailable = false

  return function tyTwoslasher(source: string, _lang?: string): TyTwoslashResult {
    const code = source.replace(/\r\n/g, '\n')
    const directives = parseDirectives(code)
    const pc = createPositionConverter(code)
    const stripped = () => ({ code: removeCodeRanges(code, directives.removals).code, nodes: [] })
    if (disabled) return stripped()

    let output: ClientOutput
    try {
      output = analyzeCached(code)
    } catch (error) {
      if (error instanceof TyUnavailableError && mode === 'dev') {
        if (!warnedUnavailable) {
          warnedUnavailable = true
          console.warn(`[ty-twoslash] ${error.message}\nPython snippets render without type hovers.`)
        }
        return stripped()
      }
      throw error
    }

    const nodes: NodeWithoutPosition[] = []
    const queried = new Set(output.queries.map((q) => `${q.line}:${q.character}`))
    for (const hover of output.hovers) {
      if (queried.has(`${hover.line}:${hover.character}`)) continue // the query popup replaces it
      const info = normalizeHover(hover.value)
      if (!info) continue
      const start = pc.posToIndex(hover.line, hover.character)
      const target = code.slice(start, start + hover.length)
      nodes.push({
        type: 'hover',
        start,
        length: hover.length,
        target,
        text: callableAsDef(target, info.text),
        docs: info.docs,
      } satisfies Omit<NodeHover, 'line' | 'character'>)
    }
    for (const query of output.queries) {
      const info = normalizeHover(query.value)
      if (!info) continue
      const start = pc.posToIndex(query.line, query.character)
      const target = code.slice(start, start + query.length)
      nodes.push({
        type: 'query',
        start,
        length: query.length,
        target,
        text: callableAsDef(target, info.text),
        docs: info.docs,
      } satisfies Omit<NodeQuery, 'line' | 'character'>)
    }

    const errors = output.diagnostics.filter((d) => ERROR_SEVERITIES.has(d.severity ?? 1))
    if (!directives.noErrors) {
      const actual = new Set(errors.map((d) => String(d.code ?? 'unknown')))
      const declared = new Set(directives.declaredErrors ?? [])
      const undeclared = [...actual].filter((c) => !declared.has(c))
      const stale = [...declared].filter((c) => !actual.has(c))
      if (undeclared.length > 0 || stale.length > 0) {
        const message = gateMessage(code, errors, undeclared, stale)
        if (mode === 'build') throw new TyTwoslashError(message)
        console.warn(`[ty-twoslash] ${message}`)
      }
      for (const diagnostic of output.diagnostics) {
        // Hints such as "`x` is unused" are editor grey-outs, not something a reader needs.
        if (diagnostic.severity === 4) continue
        const { start, end } = diagnostic.range
        const startIndex = pc.posToIndex(start.line, start.character)
        const endIndex =
          end.line === start.line
            ? pc.posToIndex(end.line, end.character)
            : startIndex + (pc.lines[start.line]?.length ?? 0) - start.character
        nodes.push({
          type: 'error',
          start: startIndex,
          length: Math.max(endIndex - startIndex, 1),
          text: diagnostic.message,
          code: diagnostic.code,
          level: LEVELS[diagnostic.severity ?? 1] ?? 'error',
        } satisfies Omit<NodeError, 'line' | 'character'>)
      }
    }

    const removed = removeCodeRanges(code, directives.removals, nodes)
    return { code: removed.code, nodes: resolveNodePositions(removed.nodes, removed.code) }
  }

  function analyzeCached(code: string): ClientOutput {
    const key = cacheKey(code, rootDir, docsDir)
    const cached = memory.get(key) ?? readCache<ClientOutput>(cacheDir, key)
    if (cached) {
      memory.set(key, cached)
      return cached
    }
    if (debug) console.log(`[ty-twoslash] cache miss ${key}: ${preview(code)}`)
    const output = analyze(code, key)
    memory.set(key, output)
    writeCache(cacheDir, key, output)
    return output
  }

  function analyze(code: string, key: string): ClientOutput {
    tyVersion(rootDir) // throws TyUnavailableError before we spawn anything
    const input: ClientInput = {
      code,
      uri: `file://${path.join(rootDir, 'docs', 'snippets', `${key}.py`)}`,
      rootDir,
      queries: [],
    }
    input.queries = parseDirectives(code).queries.map((q) => createPositionConverter(code).indexToPos(q.index))
    const result = spawnSync(
      process.execPath,
      ['--experimental-strip-types', '--no-warnings', clientPath],
      { input: JSON.stringify(input), encoding: 'utf8', timeout: 60_000, maxBuffer: 64 * 1024 * 1024 },
    )
    if (result.error) throw new TyUnavailableError(`ty-client could not start: ${result.error.message}`)
    if (result.status !== 0)
      throw new TyUnavailableError(`ty-client failed (${result.status}):\n${result.stderr.trim()}`)
    try {
      return JSON.parse(result.stdout) as ClientOutput
    } catch {
      throw new TyUnavailableError(`ty-client returned invalid JSON:\n${result.stdout.slice(0, 500)}`)
    }
  }
}

/**
 * ty prints a decorated function's type as a bare callable, `(x: int) -> Effect[...]`.
 * Show it as `def name(x: int) -> Effect[...]`, the way ty prints plain functions;
 * this also keeps vocs' renderer from prefixing `function` to it.
 */
function callableAsDef(target: string, text: string): string {
  return text.startsWith('(') && /^\w+$/.test(target) ? `def ${target}${text}` : text
}

function gateMessage(code: string, errors: ClientDiagnostic[], undeclared: string[], stale: string[]): string {
  const lines = code.split('\n')
  const width = String(lines.length).length
  const numbered = lines.map((l, i) => `${String(i + 1).padStart(width)} | ${l}`).join('\n')
  const details = errors
    .map((d) => `  ${String(d.code ?? 'unknown')}: ${d.message.split('\n')[0]} (line ${d.range.start.line + 1})`)
    .join('\n')
  const parts = ['ty reported errors in a Python snippet that the snippet does not declare.']
  if (undeclared.length > 0) parts.push(`Undeclared: ${undeclared.join(' ')}`)
  if (stale.length > 0) parts.push(`Declared but not raised: ${stale.join(' ')}`)
  parts.push(
    `Fix the snippet, declare the errors with \`# @errors: ${[...new Set(errors.map((d) => String(d.code)))].join(' ')}\`, or add \`# @noErrors\`.`,
  )
  if (details) parts.push(`Diagnostics:\n${details}`)
  parts.push(`Snippet:\n${numbered}`)
  return parts.join('\n')
}

function preview(code: string): string {
  const oneLine = code.replace(/\n/g, '\\n')
  return oneLine.length > 60 ? `${oneLine.slice(0, 60)}...` : oneLine
}
