import api from './axios'

export interface Subscription {
  id: string
  status: string
  plan: string
  trial_ends_at: string
  current_period_end: string | null
  monthly_price_usd: number | null
  discount_pct: number | null
  notes: string | null
}

export interface Tenant {
  id: string
  name: string
  slug: string
  business_type: string
  phone: string
  is_active: boolean
  is_accepting_queue: boolean
  d360_api_key: string | null
  d360_channel_id: string | null
  enabled_languages: string[]
  telegram_bot_token: string | null
  created_at: string
  subscription?: Subscription
}

export interface Plan {
  id: string
  slug: string
  name_en: string
  name_ar: string | null
  name_ru: string | null
  price_usd: number
  features: string[] | null
  is_active: boolean
  sort_order: number
}

export const adminApi = {
  // Auth
  login: (email: string, password: string) =>
    api.post('/auth/super-admin/login', { email, password }).then((r) => r.data),

  // Tenants
  listTenants: () => api.get<Tenant[]>('/admin/tenants').then((r) => r.data),
  getTenant: (id: string) => api.get<Tenant>(`/admin/tenants/${id}`).then((r) => r.data),
  createTenant: (data: any) => api.post<Tenant>('/admin/tenants', data).then((r) => r.data),
  updateTenant: (id: string, data: any) =>
    api.patch<Tenant>(`/admin/tenants/${id}`, data).then((r) => r.data),
  activateTenant: (id: string) =>
    api.post(`/admin/tenants/${id}/activate`).then((r) => r.data),
  deactivateTenant: (id: string) =>
    api.post(`/admin/tenants/${id}/deactivate`).then((r) => r.data),
  extendTrial: (id: string, days: number) =>
    api.post(`/admin/tenants/${id}/extend-trial`, { days }).then((r) => r.data),
  updateSubscription: (id: string, data: {
    plan?: string
    status?: string
    monthly_price_usd?: number | null
    discount_pct?: number | null
    notes?: string | null
  }) => api.patch<Tenant>(`/admin/tenants/${id}/subscription`, data).then((r) => r.data),

  // Plans
  listPlans: () => api.get<Plan[]>('/admin/plans').then((r) => r.data),
  createPlan: (data: {
    slug: string
    name_en: string
    name_ar?: string
    name_ru?: string
    price_usd: number
    features?: string[]
    sort_order?: number
  }) => api.post<Plan>('/admin/plans', data).then((r) => r.data),
  updatePlan: (id: string, data: {
    name_en?: string
    name_ar?: string
    name_ru?: string
    price_usd?: number
    features?: string[]
    is_active?: boolean
    sort_order?: number
  }) => api.patch<Plan>(`/admin/plans/${id}`, data).then((r) => r.data),
  deletePlan: (id: string) => api.delete(`/admin/plans/${id}`),
}
