import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true
      const refresh = localStorage.getItem('admin_refresh_token')
      if (refresh) {
        try {
          const res = await axios.post('/api/v1/auth/refresh', { refresh_token: refresh })
          localStorage.setItem('admin_access_token', res.data.access_token)
          localStorage.setItem('admin_refresh_token', res.data.refresh_token)
          error.config.headers.Authorization = `Bearer ${res.data.access_token}`
          return api(error.config)
        } catch {
          localStorage.removeItem('admin_access_token')
          localStorage.removeItem('admin_refresh_token')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  },
)

export default api
