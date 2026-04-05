import api from './axios'

export type AppointmentStatus = 'confirmed' | 'cancelled' | 'done' | 'no_show'

export interface WorkScheduleItem {
  id?: string
  tenant_id?: string
  day_of_week?: number | null
  specific_date?: string | null
  is_working: boolean
  open_time?: string | null
  close_time?: string | null
  max_parallel: number
  notes?: string | null
}

export interface TimeSlot {
  start: string
  end: string
  available: number
}

export interface AppointmentCustomer {
  id: string
  phone: string
  name: string | null
  is_vip: boolean
}

export interface AppointmentService {
  id: string
  name_ar: string
  name_en: string
  name_ru: string | null
  avg_duration_minutes: number
}

export interface Appointment {
  id: string
  tenant_id: string
  customer: AppointmentCustomer
  service: AppointmentService | null
  scheduled_at: string
  status: AppointmentStatus
  reminder_sent: boolean
  queue_entry_id: string | null
  notes: string | null
  created_at: string
}

export const appointmentsApi = {
  // Work schedule
  getSchedule: () =>
    api.get<WorkScheduleItem[]>('/work-schedule/').then((r) => r.data),

  saveSchedule: (items: WorkScheduleItem[]) =>
    api.put<WorkScheduleItem[]>('/work-schedule/', { items }).then((r) => r.data),

  addOverride: (data: Omit<WorkScheduleItem, 'id' | 'tenant_id' | 'day_of_week'> & { specific_date: string }) =>
    api.post<WorkScheduleItem>('/work-schedule/override', data).then((r) => r.data),

  deleteOverride: (date: string) =>
    api.delete(`/work-schedule/override/${date}`),

  // Slots
  getSlots: (date: string, serviceId?: string) =>
    api.get<TimeSlot[]>('/appointments/slots', {
      params: { target_date: date, service_id: serviceId },
    }).then((r) => r.data),

  getWorkingDays: (fromDate?: string, count = 7) =>
    api.get<string[]>('/appointments/working-days', {
      params: { from_date: fromDate, count },
    }).then((r) => r.data),

  // Appointments
  list: (params?: { target_date?: string; status?: AppointmentStatus }) =>
    api.get<Appointment[]>('/appointments/', { params }).then((r) => r.data),

  create: (data: { customer_id: string; service_id?: string; scheduled_at: string; notes?: string }) =>
    api.post<Appointment>('/appointments/', data).then((r) => r.data),

  cancel: (id: string) =>
    api.patch<Appointment>(`/appointments/${id}/cancel`).then((r) => r.data),
}
