// vocs entry point: a twoslash transformer for Python code blocks, typed by ty.
//
//   import { tyTwoslash } from './twoslash/index.ts'
//   export default defineConfig({ twoslash: { transformers: [tyTwoslash()] } })
//
// Every ```python block gets hovers (no `twoslash` fence meta needed); add
// `notwoslash` to the fence meta to opt one out. See README.md.

import { createTransformerFactory } from '@shikijs/twoslash/core'
import { Twoslash } from 'vocs/config'
import { type TyTwoslasherOptions, createTyTwoslasher, detectMode } from './twoslasher.ts'

export type { TyTwoslasherOptions } from './twoslasher.ts'
export { createTyTwoslasher, TyTwoslashError, TyUnavailableError } from './twoslasher.ts'

export function tyTwoslash(options: Omit<TyTwoslasherOptions, 'cacheDir'> = {}) {
  return (injected: { cacheDir?: string | undefined }) => {
    const mode = options.mode ?? detectMode()
    const twoslasher = createTyTwoslasher({ ...options, cacheDir: injected.cacheDir, mode })
    return createTransformerFactory(twoslasher, Twoslash.Renderer.rich())({
      langs: ['python', 'py'],
      explicitTrigger: false,
      throws: true,
      onShikiError(error, code) {
        if (mode === 'build') throw error
        console.warn(`[ty-twoslash] ${error instanceof Error ? error.message : String(error)}\n${code.slice(0, 200)}`)
      },
    })
  }
}
