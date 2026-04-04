import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type MeResponse } from '@/api/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const user = ref<MeResponse | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isSuperAdmin = computed(() => user.value?.role === 'super_admin')
  const tenantId = computed(() => user.value?.tenant_id)

  async function login(email: string, password: string) {
    const tokens = await authApi.login({ email, password })
    _setTokens(tokens.access_token, tokens.refresh_token)
    await fetchMe()
  }

  async function refresh(): Promise<string> {
    if (!refreshToken.value) throw new Error('No refresh token')
    const tokens = await authApi.refresh(refreshToken.value)
    _setTokens(tokens.access_token, tokens.refresh_token)
    return tokens.access_token
  }

  async function fetchMe() {
    user.value = await authApi.me()
  }

  async function logout() {
    if (refreshToken.value) {
      await authApi.logout(refreshToken.value)
    }
    _clearTokens()
    router.push('/login')
  }

  function _setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }

  function _clearTokens() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  return {
    accessToken,
    refreshToken,
    user,
    isAuthenticated,
    isAdmin,
    isSuperAdmin,
    tenantId,
    login,
    refresh,
    fetchMe,
    logout,
  }
})
