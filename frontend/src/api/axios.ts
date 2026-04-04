import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach access token to every request
api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// Auto-refresh on 401
let refreshing = false
let waiters: Array<(token: string) => void> = []

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }
    original._retry = true

    if (refreshing) {
      return new Promise((resolve) => {
        waiters.push((token) => {
          original.headers.Authorization = `Bearer ${token}`
          resolve(api(original))
        })
      })
    }

    refreshing = true
    try {
      const auth = useAuthStore()
      const newToken = await auth.refresh()
      waiters.forEach((cb) => cb(newToken))
      waiters = []
      original.headers.Authorization = `Bearer ${newToken}`
      return api(original)
    } catch {
      const auth = useAuthStore()
      auth.logout()
      return Promise.reject(error)
    } finally {
      refreshing = false
    }
  },
)

export default api
