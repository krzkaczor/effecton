// Normalises ty's hover markdown into what a twoslash popup shows.
//
// ty answers `textDocument/hover` with a fenced block holding the type, and
// optionally a `---` separator followed by the docstring as markdown. Modules
// and classes come back in an `xml` fence as `<module 'x'>` / `<class 'X'>`.

export type HoverInfo = { text: string; docs?: string }

const reFenced = /^```(\w*)\n([\s\S]*?)\n```(?:\n---\n([\s\S]*))?$/
const reModule = /^<module '(.+)'>$/
const reClass = /^<class '(.+)'>$/

/** Returns `null` for hovers that are not worth a popup (modules, `Unknown`, empty). */
export function normalizeHover(value: string): HoverInfo | null {
  const match = reFenced.exec(value.trim())
  let text = match ? match[2]!.trim() : value.trim()
  const trailing = match?.[3]?.trim()

  if (reModule.test(text)) return null
  const cls = reClass.exec(text)
  if (cls) text = `class ${cls[1]}`
  if (text === '' || text === 'Unknown') return null

  // typeshed docstrings open code blocks with runs of 11 backticks, which
  // markdown parsers read as a single long fence; shorten them so the popup's
  // unclosed-fence repair sees ordinary fences.
  const docs = trailing?.replace(/`{4,}/g, '```')
  return docs ? { text, docs } : { text }
}
