// Twoslash directives in Python comment form.
//
// Mirrors the `//`-style directives of twoslash: cut markers hide setup code
// from the rendered block, `^?` asks for a persisted type popup, and the two
// `@` flags control how diagnostics are rendered and gated. The parser only
// reports what it found; the caller removes the ranges and remaps positions.

export type Range = [start: number, end: number]

export type Directives = {
  /** UTF-16 index ranges to delete from the rendered code (directive lines and cut regions). */
  removals: Range[]
  /** Positions of `^?` targets, as UTF-16 indices into the unmodified code. */
  queries: { index: number }[]
  /** `# @noErrors`: diagnostics are neither rendered nor gated. */
  noErrors: boolean
  /** `# @errors: a b`: the exact set of ty rule names the snippet is expected to raise. */
  declaredErrors: string[] | undefined
}

export class DirectiveError extends Error {
  override name = 'DirectiveError'
}

const reCutBefore = /^#\s?---cut(-before)?---$/
const reCutAfter = /^#\s?---cut-after---$/
const reCutStart = /^#\s?---cut-start---$/
const reCutEnd = /^#\s?---cut-end---$/
const reQuery = /^\s*#\s*\^\?( .*)?$/
const reNoErrors = /^#\s?@noErrors$/
const reErrors = /^#\s?@errors:\s?(.+)$/

/** Parses every directive in `code`. `code` must already use `\n` line endings. */
export function parseDirectives(code: string): Directives {
  const lines = code.split('\n')
  const lineStarts: number[] = []
  let offset = 0
  for (const line of lines) {
    lineStarts.push(offset)
    offset += line.length + 1
  }
  const lineRange = (i: number): Range => [
    lineStarts[i]!,
    Math.min(lineStarts[i]! + lines[i]!.length + 1, code.length),
  ]

  let removals: Range[] = []
  const queries: { index: number }[] = []
  const queryLines = new Set<number>()
  const cutStarts: number[] = []
  let noErrors = false
  let declaredErrors: string[] | undefined

  for (const [i, raw] of lines.entries()) {
    const line = raw.trim()
    if (reCutBefore.test(line)) {
      removals = [[0, lineRange(i)[1]]]
    } else if (reCutAfter.test(line)) {
      removals.push([lineStarts[i]!, code.length])
      break
    } else if (reCutStart.test(line)) {
      cutStarts.push(i)
    } else if (reCutEnd.test(line)) {
      const start = cutStarts.pop()
      if (start === undefined)
        throw new DirectiveError(`Mismatched cut markers: cut-end at line ${i + 1} has no cut-start.`)
      removals.push([lineStarts[start]!, lineRange(i)[1]])
    } else if (reQuery.test(raw)) {
      let target = i - 1
      while (target >= 0 && queryLines.has(target)) target--
      if (target < 0) throw new DirectiveError(`A ^? query at line ${i + 1} has no line above it.`)
      const column = raw.indexOf('^')
      if (column > lines[target]!.length)
        throw new DirectiveError(`The ^? query at line ${i + 1} points past the end of line ${target + 1}.`)
      queries.push({ index: lineStarts[target]! + column })
      queryLines.add(i)
      removals.push(lineRange(i))
    } else if (reNoErrors.test(line)) {
      noErrors = true
      removals.push(lineRange(i))
    } else {
      const errors = reErrors.exec(line)
      if (errors) {
        declaredErrors = errors[1]!.split(/[\s,]+/).filter(Boolean)
        removals.push(lineRange(i))
      }
    }
  }

  if (cutStarts.length > 0)
    throw new DirectiveError(
      `Mismatched cut markers: unclosed cut-start at line(s) ${cutStarts.map((l) => l + 1).join(', ')}.`,
    )

  return { removals, queries, noErrors, declaredErrors }
}
