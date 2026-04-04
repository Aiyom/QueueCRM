<template>
  <div class="min-h-screen bg-gray-100 flex">
    <!-- Sidebar -->
    <aside class="w-56 bg-indigo-900 text-white flex flex-col">
      <div class="px-6 py-5 border-b border-indigo-800">
        <p class="font-bold text-lg">QueueCRM</p>
        <p class="text-indigo-300 text-xs mt-0.5">{{ $t('auth.title') }}</p>
      </div>
      <nav class="flex-1 px-4 py-4 space-y-1">
        <RouterLink
          to="/tenants"
          class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium hover:bg-indigo-800 transition"
          active-class="bg-indigo-800"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          {{ $t('nav.tenants') }}
        </RouterLink>
        <RouterLink
          to="/plans"
          class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium hover:bg-indigo-800 transition"
          active-class="bg-indigo-800"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          {{ $t('nav.plans') }}
        </RouterLink>
      </nav>
      <div class="px-4 py-4 border-t border-indigo-800 space-y-3">
        <LocaleSwitcher />
        <button
          @click="logout"
          class="w-full text-left text-sm text-indigo-300 hover:text-white px-3 py-2 rounded-lg hover:bg-indigo-800 transition"
        >
          {{ $t('nav.logout') }}
        </button>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-y-auto">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from 'vue-router'
import LocaleSwitcher from '@/components/LocaleSwitcher.vue'

const router = useRouter()

function logout() {
  localStorage.removeItem('admin_access_token')
  localStorage.removeItem('admin_refresh_token')
  router.push('/login')
}
</script>
