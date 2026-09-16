import { defineConfig } from 'vocs/config'
import { tyTwoslash } from './twoslash/index.ts'

export default defineConfig({
  title: 'Effecton',
  description: 'Building blocks for reliable, type-safe Python applications.',
  logoUrl: '/logo-wordmark-white.svg',
  iconUrl: '/icon.svg',
  colorScheme: 'dark',
  accentColor: '#C5FF51',
  renderStrategy: 'full-static',
  topNav: [
    { text: 'Docs', link: '/introduction', match: '/introduction' },
    { text: 'API Reference', link: '/api', match: '/api' },
  ],
  sidebar: [
    { text: 'Introduction', link: '/introduction' },
    {
      text: 'Core',
      items: [
        { text: 'Building effects', link: '/core/building-effects' },
        { text: 'Running effects', link: '/core/running-effects' },
        { text: 'Main programs', link: '/core/main-programs' },
        { text: 'Error handling', link: '/core/error-handling' },
        { text: 'Requirements', link: '/core/requirements' },
        { text: 'Implicit requirements', link: '/core/implicit-requirements' },
        { text: 'Resource management', link: '/core/resource-management' },
        { text: 'Generator syntax', link: '/core/generator-syntax' },
        { text: 'Wrapping third party code', link: '/core/wrapping-third-party-code' },
        { text: 'Wrapping async code', link: '/core/wrapping-async-code' },
      ],
    },
    {
      text: 'Standard library',
      items: [
        { text: 'Logger', link: '/std/logger' },
        { text: 'Clock', link: '/std/clock' },
        { text: 'Random', link: '/std/random' },
        { text: 'Tracer', link: '/std/tracer' },
        { text: 'FileSystem', link: '/std/file-system' },
        { text: 'Path', link: '/std/path' },
        { text: 'Process', link: '/std/process' },
        { text: 'HttpClient', link: '/std/http-client' },
        { text: 'Fibers', link: '/std/fibers' },
        { text: 'Racing', link: '/std/racing' },
        { text: 'Timeouts', link: '/std/timeouts' },
        { text: 'Retries', link: '/std/retries' },
      ],
    },
  ],
  socials: [
    { icon: 'github', link: 'https://github.com/krzkaczor/effecton' },
    { icon: 'discord', link: 'https://discord.gg/fNhY7AxMyh' },
  ],
  editLink: {
    link: 'https://github.com/krzkaczor/effecton/edit/main/docs/src/pages/:path',
  },
  // Every ```python block is typed by ty and gets hover popups; see twoslash/README.md.
  twoslash: { transformers: [tyTwoslash()] },
})
