import api from './axios'

export interface Service {
  id: string
  name_ar: string
  name_en: string
  name_ru: string | null
  avg_duration_minutes: number
  is_active: boolean
  sort_order: number
}

export const servicesApi = {
  list: () => api.get<Service[]>('/services/').then((r) => r.data),

  create: (data: { name_ar: string; name_en: string; name_ru?: string; avg_duration_minutes?: number; sort_order?: number }) =>
    api.post<Service>('/services/', data).then((r) => r.data),

  update: (id: string, data: Partial<Omit<Service, 'id'>>) =>
    api.patch<Service>(`/services/${id}`, data).then((r) => r.data),

  delete: (id: string) => api.delete(`/services/${id}`),
}
