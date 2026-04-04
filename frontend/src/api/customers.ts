import api from './axios'

export interface Customer {
  id: string
  phone: string
  name: string | null
  notes: string | null
  is_vip: boolean
  vip_set_manually: boolean
  total_visits: number
  total_spent: number
  preferred_language: string
  last_seen_at: string | null
  created_at: string
}

export interface CustomerList {
  items: Customer[]
  total: number
  page: number
  page_size: number
}

export interface SegmentStats {
  total_customers: number
  vip_customers: number
  new_this_month: number
  avg_visits: number
  avg_spent: number
}

export const customersApi = {
  list: (params?: { page?: number; page_size?: number; search?: string; is_vip?: boolean }) =>
    api.get<CustomerList>('/customers/', { params }).then((r) => r.data),

  get: (id: string) => api.get<Customer>(`/customers/${id}`).then((r) => r.data),

  create: (data: { phone: string; name?: string; notes?: string; is_vip?: boolean }) =>
    api.post<Customer>('/customers/', data).then((r) => r.data),

  update: (id: string, data: { name?: string; notes?: string; is_vip?: boolean }) =>
    api.patch<Customer>(`/customers/${id}`, data).then((r) => r.data),

  segmentStats: () => api.get<SegmentStats>('/customers/segments/stats').then((r) => r.data),
}
