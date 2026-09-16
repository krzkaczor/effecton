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
  sidebar: [{ text: 'Introduction', link: '/introduction' }],
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
