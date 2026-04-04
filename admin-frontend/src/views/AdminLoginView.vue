<template>
  <div class="min-h-screen bg-gray-100 flex items-center justify-center">
    <div class="bg-white rounded-xl shadow-md p-8 w-full max-w-sm">
      <h1 class="text-2xl font-bold text-gray-800 mb-6 text-center">{{ $t('auth.title') }}</h1>
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.email') }}</label>
          <input
            v-model="email"
            type="email"
            required
            class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">{{ $t('auth.password') }}</label>
          <input
            v-model="password"
            type="password"
            required
            class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <p v-if="error" class="text-red-600 text-sm">{{ $t('auth.error') }}</p>
        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium py-2 rounded-lg transition"
        >
          {{ loading ? $t('common.loading') : $t('auth.login') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { adminApi } from '@/api/admin'

const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref(false)
const loading = ref(false)

async function handleLogin() {
  error.value = false
  loading.value = true
  try {
    const data = await adminApi.login(email.value, password.value)
    localStorage.setItem('admin_access_token', data.access_token)
    localStorage.setItem('admin_refresh_token', data.refresh_token)
    router.push('/')
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}
</script>
