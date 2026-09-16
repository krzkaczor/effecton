// Child entry point: one ty language-server session for one snippet.
//
// Reads `{ code, uri, rootDir, queries }` as JSON on stdin, runs `uv run ty
// server` from the repo root, hovers every identifier-like token, resolves the
// `^?` queries and collects diagnostics, then prints one JSON object on stdout.
// It is a separate process because shiki transformers are synchronous while
// the LSP is not; the parent drives it with `spawnSync`.
//
//   node --experimental-strip-types --no-warnings ty-client.ts < input.json

import { LspClient } from './lsp.ts'

export type Position = { line: number; character: number }
export type LspRange = { start: Position; end: Position }

export type ClientInput = {
  code: string
  uri: string
  rootDir: string
  queries: Position[]
}

export type ClientHover = Position & { length: number; tokenType: string; value: string }
export type ClientDiagnostic = {
  code?: string | number
  severity?: number
  message: string
  range: LspRange
}
export type ClientOutput = {
  hovers: ClientHover[]
  queries: (Position & { length: number; value: string })[]
  diagnostics: ClientDiagnostic[]
}

type HoverResult = { contents: { kind?: string; value: string } | string; range?: LspRange } | null
type SemanticToken = Position & { length: number; tokenType: string }

const HOVER_TOKEN_TYPES = new Set([
  'class',
  'parameter',
  'selfParameter',
  'clsParameter',
  'variable',
  'property',
  'function',
  'method',
  'decorator',
  'typeParam',
  'typeParameter',
  'enumMember',
])

const PYTHON_KEYWORDS = new Set(
  'False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case type'.split(
    ' ',
  ),
)

const SESSION_TIMEOUT_MS = 30_000

export async function analyze(input: ClientInput): Promise<ClientOutput> {
  const client = new LspClient('uv', ['run', 'ty', 'server'], {
    cwd: input.rootDir,
    onServerRequest: (method, params) => {
      if (method === 'workspace/configuration') {
        const items = (params as { items?: unknown[] } | undefined)?.items ?? []
        return items.map(() => null)
      }
      return null
    },
  })

  try {
    const rootUri = `file://${input.rootDir}`
    const init = await client.request<{
      capabilities: {
        semanticTokensProvider?: { legend: { tokenTypes: string[] } }
      }
    }>('initialize', {
      processId: process.pid,
      rootUri,
      workspaceFolders: [{ uri: rootUri, name: 'effecton' }],
      capabilities: {
        general: { positionEncodings: ['utf-16'] },
        textDocument: {
          hover: { contentFormat: ['markdown', 'plaintext'] },
          semanticTokens: {
            requests: { full: true },
            formats: ['relative'],
            tokenTypes: [],
            tokenModifiers: [],
          },
          diagnostic: {},
        },
      },
    })
    client.notify('initialized', {})
    client.notify('textDocument/didOpen', {
      textDocument: { uri: input.uri, languageId: 'python', version: 1, text: input.code },
    })
    const textDocument = { uri: input.uri }

    const legend = init.capabilities.semanticTokensProvider?.legend.tokenTypes
    let tokens = legend ? await semanticTokens(client, textDocument, legend) : []
    if (tokens.length === 0) tokens = scanIdentifiers(input.code)

    const hover = (position: Position) =>
      client.request<HoverResult>('textDocument/hover', { textDocument, position })

    const hovers: ClientHover[] = []
    const hoverResults = await Promise.all(tokens.map((token) => hover(token)))
    for (const [i, result] of hoverResults.entries()) {
      const token = tokens[i]!
      const value = hoverValue(result)
      if (value === null) continue
      const range = result?.range
      const position = range && range.start.line === range.end.line ? range.start : token
      const length =
        range && range.start.line === range.end.line
          ? range.end.character - range.start.character
          : token.length
      hovers.push({ ...position, length, tokenType: token.tokenType, value })
    }

    const queries: ClientOutput['queries'] = []
    for (const position of input.queries) {
      const result = await hover(position)
      const value = hoverValue(result)
      if (value === null) continue
      const range = result?.range
      if (range && range.start.line === range.end.line) {
        queries.push({ ...range.start, length: range.end.character - range.start.character, value })
        continue
      }
      const covering = tokens.find(
        (t) => t.line === position.line && t.character <= position.character && position.character < t.character + t.length,
      )
      if (covering) {
        queries.push({ line: covering.line, character: covering.character, length: covering.length, value })
        continue
      }
      const word = wordAt(input.code, position)
      if (word) queries.push({ ...word, value })
    }

    const diagnostic = await client.request<{ items?: ClientDiagnostic[] } | null>(
      'textDocument/diagnostic',
      { textDocument },
    )
    const diagnostics = (diagnostic?.items ?? []).map(({ code, severity, message, range }) => ({
      code,
      severity,
      message,
      range,
    }))

    await client.request('shutdown', null).catch(() => undefined)
    client.notify('exit', null)
    return { hovers, queries, diagnostics }
  } finally {
    await client.close()
  }
}

async function semanticTokens(
  client: LspClient,
  textDocument: { uri: string },
  legend: string[],
): Promise<SemanticToken[]> {
  const result = await client
    .request<{ data: number[] } | null>('textDocument/semanticTokens/full', { textDocument })
    .catch(() => null)
  const data = result?.data ?? []
  const tokens: SemanticToken[] = []
  let line = 0
  let character = 0
  for (let i = 0; i + 4 < data.length; i += 5) {
    const deltaLine = data[i]!
    const deltaStart = data[i + 1]!
    const length = data[i + 2]!
    const tokenType = legend[data[i + 3]!] ?? 'unknown'
    line += deltaLine
    character = deltaLine === 0 ? character + deltaStart : deltaStart
    if (HOVER_TOKEN_TYPES.has(tokenType)) tokens.push({ line, character, length, tokenType })
  }
  return tokens
}

/** Fallback when semantic tokens are unavailable: every identifier that is not a keyword. */
function scanIdentifiers(code: string): SemanticToken[] {
  const tokens: SemanticToken[] = []
  for (const [line, text] of code.split('\n').entries()) {
    for (const match of text.matchAll(/[A-Za-z_]\w*/g)) {
      if (PYTHON_KEYWORDS.has(match[0])) continue
      tokens.push({ line, character: match.index, length: match[0].length, tokenType: 'identifier' })
    }
  }
  return tokens
}

function wordAt(code: string, position: Position): (Position & { length: number }) | null {
  const text = code.split('\n')[position.line]
  if (text === undefined) return null
  for (const match of text.matchAll(/[A-Za-z_]\w*/g)) {
    if (match.index <= position.character && position.character < match.index + match[0].length)
      return { line: position.line, character: match.index, length: match[0].length }
  }
  return null
}

function hoverValue(result: HoverResult): string | null {
  if (!result) return null
  const contents = result.contents
  const value = typeof contents === 'string' ? contents : contents.value
  return value.trim() === '' ? null : value
}

async function main(): Promise<void> {
  const chunks: Buffer[] = []
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer)
  const input = JSON.parse(Buffer.concat(chunks).toString('utf8')) as ClientInput

  const timer = setTimeout(() => {
    process.stderr.write(`ty-client: session exceeded ${SESSION_TIMEOUT_MS}ms\n`)
    process.exit(2)
  }, SESSION_TIMEOUT_MS)

  try {
    const output = await analyze(input)
    process.stdout.write(`${JSON.stringify(output)}\n`)
  } catch (error) {
    process.stderr.write(`ty-client: ${error instanceof Error ? error.message : String(error)}\n`)
    process.exitCode = 1
  } finally {
    clearTimeout(timer)
  }
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) void main()
