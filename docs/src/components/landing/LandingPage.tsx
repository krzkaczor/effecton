// Server component: types the playground's with-Effecton snippets with ty at
// build time and hands the hover data to the client-side <Landing />.
//
// It has no 'use client' on purpose. index.mdx is a server component, so this
// runs once per build under `full-static` (and per request in `vocs dev`,
// against the on-disk cache), keeping `uv`, the language server and the
// twoslash helper out of the browser bundle.

import { createTyTwoslasher } from '../../../twoslash/twoslasher.ts'
import { Landing } from './Landing'
import {
  ALL_LEVELS,
  type HoverRef,
  MOBILE_KEY,
  buildMobile,
  buildWith,
  levelKey,
} from './snippets'

export function LandingPage() {
  const { hovers, texts } = computeHovers()
  return <Landing hovers={hovers} texts={texts} />
}

function computeHovers(): {
  hovers: Record<string, HoverRef[]>
  texts: string[]
} {
  const twoslasher = createTyTwoslasher()
  const texts: string[] = []
  const indexOf = new Map<string, number>()
  const intern = (text: string) => {
    let idx = indexOf.get(text)
    if (idx === undefined) {
      idx = texts.push(text) - 1
      indexOf.set(text, idx)
    }
    return idx
  }

  const hovers: Record<string, HoverRef[]> = {}
  const sources: [string, string][] = [
    ...ALL_LEVELS.map((level): [string, string] => [levelKey(level), buildWith(level)]),
    [MOBILE_KEY, buildMobile()],
  ]
  for (const [key, source] of sources) {
    const result = twoslasher(source)
    hovers[key] = result.nodes
      .filter((node) => node.type === 'hover')
      .map((node) => [node.line, node.character, node.length, intern(node.text)] as const)
  }
  return { hovers, texts }
}
