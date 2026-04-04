import { defineConfig } from 'astro/config'
import tailwind from '@astrojs/tailwind'

export default defineConfig({
  site: 'https://qcrm.sa',
  integrations: [tailwind()],
})
