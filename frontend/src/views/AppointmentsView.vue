<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <h1 class="text-2xl font-bold text-gray-900">Appointments</h1>
      <div class="flex items-center gap-2">
        <!-- View switcher -->
        <div class="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
          <button
            v-for="v in views"
            :key="v.key"
            @click="activeView = v.key"
            class="px-3 py-1.5 transition-colors"
            :class="activeView === v.key ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'"
          >
            {{ v.label }}
          </button>
        </div>
        <!-- Date navigation -->
        <button @click="shiftDate(-1)" class="btn-secondary px-2 py-1.5 text-sm">←</button>
        <input type="date" v-model="selectedDate" class="input text-sm w-36" />
        <button @click="shiftDate(1)" class="btn-secondary px-2 py-1.5 text-sm">→</button>
        <button @click="showCreate = true" class="btn-primary text-sm">+ New</button>
      </div>
    </div>

    <!-- DAY VIEW -->
    <div v-if="activeView === 'day'" class="card p-0 overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-100 bg-gray-50 text-sm font-medium text-gray-600">
        {{ formatDate(selectedDate) }}
      </div>
      <div v-if="!dayAppointments.length" class="py-12 text-center text-gray-400 text-sm">
        No appointments for this day
      </div>
      <div v-else>
        <div
          v-for="appt in dayAppointments"
          :key="appt.id"
          class="flex items-start gap-4 px-4 py-3 border-b border-gray-100 last:border-0 hover:bg-gray-50"
        >
          <div class="w-16 text-sm font-semibold text-gray-700 flex-shrink-0 pt-0.5">
            {{ formatTime(appt.scheduled_at) }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-gray-900 text-sm">
                {{ appt.customer.name || appt.customer.phone }}
              </span>
              <span v-if="appt.customer.is_vip" class="badge badge-purple text-xs">VIP</span>
            </div>
            <div class="text-xs text-gray-500 mt-0.5">
              {{ appt.customer.phone }}
              <span v-if="appt.service"> · {{ appt.service.name_en || appt.service.name_ar }}</span>
              <span v-if="appt.service"> · ~{{ appt.service.avg_duration_minutes }}min</span>
            </div>
            <div v-if="appt.notes" class="text-xs text-gray-400 mt-0.5 italic">{{ appt.notes }}</div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <StatusBadge :status="appt.status" />
            <button
              v-if="appt.status === 'confirmed'"
              @click="handleCancel(appt.id)"
              class="text-xs text-red-500 hover:text-red-700"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- WEEK VIEW -->
    <div v-if="activeView === 'week'" class="card p-0 overflow-hidden">
      <div class="grid grid-cols-7 border-b border-gray-100">
        <div
          v-for="day in weekDays"
          :key="day.date"
          class="px-2 py-2 text-center border-r border-gray-100 last:border-0"
          :class="day.date === selectedDate ? 'bg-blue-50' : 'bg-gray-50'"
        >
          <div class="text-xs font-medium text-gray-500">{{ day.dayLabel }}</div>
          <div
            class="text-sm font-semibold mt-0.5 cursor-pointer hover:text-blue-600"
            :class="day.date === selectedDate ? 'text-blue-600' : 'text-gray-800'"
            @click="selectedDate = day.date; activeView = 'day'"
          >
            {{ day.dayNum }}
          </div>
        </div>
      </div>
      <div class="grid grid-cols-7">
        <div
          v-for="day in weekDays"
          :key="day.date"
          class="border-r border-gray-100 last:border-0 min-h-32 p-1 space-y-1"
          :class="day.date === selectedDate ? 'bg-blue-50/30' : ''"
        >
          <div
            v-for="appt in appointmentsByDate[day.date] || []"
            :key="appt.id"
            class="rounded p-1 text-xs cursor-pointer"
            :class="statusColor(appt.status)"
            @click="selectedDate = day.date; activeView = 'day'"
          >
            <div class="font-medium truncate">{{ formatTime(appt.scheduled_at) }} {{ appt.customer.name || appt.customer.phone }}</div>
            <div v-if="appt.service" class="text-gray-500 truncate">{{ appt.service.name_en || appt.service.name_ar }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- LIST VIEW -->
    <div v-if="activeView === 'list'" class="card p-0 overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b border-gray-100">
          <tr>
            <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Time</th>
            <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Customer</th>
            <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Service</th>
            <th class="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
            <th class="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-if="!appointments.length">
            <td colspan="5" class="py-8 text-center text-gray-400">No appointments</td>
          </tr>
          <tr v-for="appt in appointments" :key="appt.id" class="hover:bg-gray-50">
            <td class="px-4 py-3 font-mono text-gray-700">
              {{ formatDateTime(appt.scheduled_at) }}
            </td>
            <td class="px-4 py-3">
              <div class="font-medium text-gray-900">{{ appt.customer.name || appt.customer.phone }}</div>
              <div class="text-xs text-gray-400">{{ appt.customer.phone }}</div>
            </td>
            <td class="px-4 py-3 text-gray-600">
              {{ appt.service ? (appt.service.name_en || appt.service.name_ar) : '—' }}
            </td>
            <td class="px-4 py-3"><StatusBadge :status="appt.status" /></td>
            <td class="px-4 py-3 text-right">
              <button
                v-if="appt.status === 'confirmed'"
                @click="handleCancel(appt.id)"
                class="text-xs text-red-500 hover:text-red-700"
              >
                Cancel
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create appointment modal -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-md shadow-xl space-y-4">
        <h3 class="font-semibold text-gray-900">New Appointment</h3>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Customer phone</label>
          <input v-model="createForm.phone" class="input" placeholder="+966..." />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Service</label>
          <select v-model="createForm.service_id" class="input">
            <option value="">No specific service</option>
            <option v-for="svc in services" :key="svc.id" :value="svc.id">
              {{ svc.name_en || svc.name_ar }}
            </option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Date</label>
          <input type="date" v-model="createForm.date" class="input" @change="loadSlots" />
        </div>
        <div v-if="createForm.date">
          <label class="block text-sm font-medium text-gray-700 mb-1">Time slot</label>
          <div v-if="loadingSlots" class="text-sm text-gray-400">Loading slots...</div>
          <div v-else-if="!slots.length" class="text-sm text-red-500">No available slots for this date</div>
          <div v-else class="grid grid-cols-3 gap-2">
            <button
              v-for="slot in slots"
              :key="slot.start"
              @click="createForm.scheduled_at = slot.start"
              class="rounded-lg border text-sm py-2 text-center transition-colors"
              :class="createForm.scheduled_at === slot.start
                ? 'border-blue-500 bg-blue-50 text-blue-700 font-medium'
                : 'border-gray-200 hover:border-blue-300 text-gray-700'"
            >
              {{ formatTime(slot.start) }}
              <div class="text-xs text-gray-400">{{ slot.available }} left</div>
            </button>
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
          <input v-model="createForm.notes" class="input" placeholder="Any notes..." />
        </div>
        <div v-if="createError" class="text-sm text-red-500">{{ createError }}</div>
        <div class="flex gap-3">
          <button @click="showCreate = false" class="btn-secondary flex-1">Cancel</button>
          <button
            @click="handleCreate"
            :disabled="!createForm.scheduled_at || !createForm.phone || creating"
            class="btn-primary flex-1"
          >
            {{ creating ? 'Booking...' : 'Book Appointment' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { appointmentsApi, type Appointment, type TimeSlot } from '@/api/appointments'
import { servicesApi } from '@/api/services'
import { customersApi } from '@/api/customers'
import StatusBadge from '@/components/StatusBadge.vue'

const queryClient = useQueryClient()

// --- View state ---
const activeView = ref<'day' | 'week' | 'list'>('day')
const views = [
  { key: 'day', label: 'Day' },
  { key: 'week', label: 'Week' },
  { key: 'list', label: 'List' },
]

const today = new Date().toISOString().split('T')[0]
const selectedDate = ref(today)

// --- Data ---
const { data: services } = useQuery({ queryKey: ['services'], queryFn: servicesApi.list })

const { data: appointments, refetch } = useQuery({
  queryKey: ['appointments', selectedDate],
  queryFn: () => appointmentsApi.list({ target_date: selectedDate.value }),
})

// For week view — load whole week
const weekDays = computed(() => {
  const date = new Date(selectedDate.value + 'T12:00:00')
  const dow = date.getDay() // 0=Sun
  const monday = new Date(date)
  monday.setDate(date.getDate() - ((dow + 6) % 7))
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    const iso = d.toISOString().split('T')[0]
    return {
      date: iso,
      dayLabel: d.toLocaleDateString('en', { weekday: 'short' }),
      dayNum: d.getDate(),
    }
  })
})

const { data: weekAppointments } = useQuery({
  queryKey: ['appointments-week', computed(() => weekDays.value[0].date)],
  queryFn: async () => {
    const days = weekDays.value
    const results = await Promise.all(
      days.map((d) => appointmentsApi.list({ target_date: d.date }))
    )
    return results.flat()
  },
  enabled: computed(() => activeView.value === 'week'),
})

const appointmentsByDate = computed(() => {
  const map: Record<string, Appointment[]> = {}
  for (const appt of weekAppointments.value ?? []) {
    const d = appt.scheduled_at.split('T')[0]
    if (!map[d]) map[d] = []
    map[d].push(appt)
  }
  return map
})

const dayAppointments = computed(() =>
  (appointments.value ?? []).filter((a) => a.status !== 'cancelled')
)

// --- Create form ---
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const slots = ref<TimeSlot[]>([])
const loadingSlots = ref(false)
const createForm = ref({
  phone: '',
  service_id: '',
  date: today,
  scheduled_at: '',
  notes: '',
})

watch(showCreate, (v) => {
  if (v) {
    createForm.value = { phone: '', service_id: '', date: today, scheduled_at: '', notes: '' }
    slots.value = []
  }
})

async function loadSlots() {
  createForm.value.scheduled_at = ''
  if (!createForm.value.date) return
  loadingSlots.value = true
  try {
    slots.value = await appointmentsApi.getSlots(
      createForm.value.date,
      createForm.value.service_id || undefined
    )
  } finally {
    loadingSlots.value = false
  }
}

async function handleCreate() {
  createError.value = ''
  creating.value = true
  try {
    // Find or create customer
    let customer = null
    try {
      const list = await customersApi.list({ search: createForm.value.phone, page_size: 1 })
      customer = list.items.find((c) => c.phone === createForm.value.phone)
    } catch {}
    if (!customer) {
      customer = await customersApi.create({ phone: createForm.value.phone })
    }

    await appointmentsApi.create({
      customer_id: customer.id,
      service_id: createForm.value.service_id || undefined,
      scheduled_at: createForm.value.scheduled_at,
      notes: createForm.value.notes || undefined,
    })
    showCreate.value = false
    refetch()
    queryClient.invalidateQueries({ queryKey: ['appointments-week'] })
  } catch (e: any) {
    createError.value = e?.response?.data?.detail ?? 'Failed to book appointment'
  } finally {
    creating.value = false
  }
}

async function handleCancel(id: string) {
  if (!confirm('Cancel this appointment?')) return
  await appointmentsApi.cancel(id)
  refetch()
  queryClient.invalidateQueries({ queryKey: ['appointments-week'] })
}

function shiftDate(days: number) {
  const d = new Date(selectedDate.value + 'T12:00:00')
  d.setDate(d.getDate() + (activeView.value === 'week' ? days * 7 : days))
  selectedDate.value = d.toISOString().split('T')[0]
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function formatDate(iso: string) {
  return new Date(iso + 'T12:00:00').toLocaleDateString('en', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
}

function formatDateTime(iso: string) {
  const d = new Date(iso)
  return `${d.toLocaleDateString('en', { month: 'short', day: 'numeric' })} ${formatTime(iso)}`
}

function statusColor(status: string) {
  switch (status) {
    case 'confirmed': return 'bg-blue-50 text-blue-700 border border-blue-100'
    case 'cancelled': return 'bg-gray-50 text-gray-400 border border-gray-100'
    case 'done': return 'bg-green-50 text-green-700 border border-green-100'
    default: return 'bg-gray-50 text-gray-500 border border-gray-100'
  }
}
</script>
