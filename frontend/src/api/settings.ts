import api from './axios'

export interface TenantSettings {
  enabled_languages: string[]
  telegram_bot_token: string | null
  d360_api_key: string | null
  d360_channel_id: string | null
}

export async function getSettings(): Promise<TenantSettings> {
  const res = await api.get('/settings/')
  return res.data
}

export async function updateSettings(data: Partial<TenantSettings>): Promise<TenantSettings> {
  const res = await api.patch('/settings/', data)
  return res.data
}
