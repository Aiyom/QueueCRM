import api from './axios'

export type QueueStatus = 'waiting' | 'called' | 'in_service' | 'done' | 'cancelled' | 'no_show'

export interface QueueEntry {
  id: string
  position: number
  status: QueueStatus
  eta_minutes: number
  customer: { id: string; phone: string; name: string | null; is_vip: boolean }
  service: { id: string; name_ar: string; name_en: string; name_ru: string | null } | null
  created_at: string
}

export interface QueueEntryDetail {
  id: string
  tenant_id: string
  customer_id: string
  service_id: string | null
  status: QueueStatus
  position: number | null
  called_at: string | null
  started_at: string | null
  finished_at: string | null
  amount: number | null
  notes: string | null
  created_at: string
}

export interface QueueStats {
  total_waiting: number
  total_called: number
  total_in_service: number
  avg_wait_time_minutes: number
  is_accepting_queue: boolean
}

export const queueApi = {
  getQueue: () => api.get<QueueEntry[]>('/queue/').then((r) => r.data),
  getStats: () => api.get<QueueStats>('/queue/stats').then((r) => r.data),

  addToQueue: (data: { customer_id: string; service_id?: string }) =>
    api.post<QueueEntryDetail>('/queue/add', data).then((r) => r.data),

  callNext: () => api.post<QueueEntryDetail>('/queue/call-next').then((r) => r.data),

  startService: (entryId: string) =>
    api.post<QueueEntryDetail>(`/queue/${entryId}/start`).then((r) => r.data),

  finishService: (entryId: string, data: { amount?: number; notes?: string }) =>
    api.post<QueueEntryDetail>(`/queue/${entryId}/finish`, data).then((r) => r.data),

  cancel: (entryId: string) =>
    api.post<QueueEntryDetail>(`/queue/${entryId}/cancel`).then((r) => r.data),

  noShow: (entryId: string) =>
    api.post<QueueEntryDetail>(`/queue/${entryId}/no-show`).then((r) => r.data),

  toggleAccepting: () =>
    api.patch<{ is_accepting_queue: boolean }>('/queue/toggle-accepting').then((r) => r.data),
}
