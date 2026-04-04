import api from './axios'

export interface LoginPayload { email: string; password: string }
export interface TokenResponse { access_token: string; refresh_token: string; token_type: string }
export interface MeResponse {
  id: string
  email: string
  full_name: string
  role: string
  tenant_id: string | null
}

export const authApi = {
  login: (data: LoginPayload) =>
    api.post<TokenResponse>('/auth/login', data).then((r) => r.data),

  refresh: (refreshToken: string) =>
    api.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken }).then((r) => r.data),

  logout: (refreshToken: string) =>
    api.post('/auth/logout', { refresh_token: refreshToken }).catch(() => {}),

  me: () => api.get<MeResponse>('/auth/me').then((r) => r.data),
}
