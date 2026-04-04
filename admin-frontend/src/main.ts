import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import App from './App.vue'
import router from './router'
import { i18n } from './i18n'
import './assets/main.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

createApp(App).use(createPinia()).use(router).use(VueQueryPlugin, { queryClient }).use(i18n).mount('#app')
