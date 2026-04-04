<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Queue</h1>
        <p class="text-sm text-gray-500 mt-0.5">
          <span :class="queueStore.connected ? 'text-green-600' : 'text-yellow-600'">
            {{ queueStore.connected ? '● Live' : '○ Connecting...' }}
          </span>
        </p>
      </div>
      <div class="flex items-center gap-3">
        <button
          @click="handleToggleAccepting"
          class="btn"
          :class="stats?.is_accepting_queue ? 'btn-danger' : 'btn-success'"
        >
          {{ stats?.is_accepting_queue ? 'Close Queue' : 'Open Queue' }}
        </button>
        <button @click="handleCallNext" class="btn-primary" :disabled="callNextLoading || waitingCount === 0">
          <svg v-if="callNextLoading" class="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Call Next
        </button>
      </div>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="card text-center">
        <p class="text-3xl font-bold text-blue-600">{{ stats?.total_waiting ?? 0 }}</p>
        <p class="text-sm text-gray-500 mt-1">Waiting</p>
      </div>
      <div class="card text-center">
        <p class="text-3xl font-bold text-yellow-600">{{ stats?.total_called ?? 0 }}</p>
        <p class="text-sm text-gray-500 mt-1">Called</p>
      </div>
      <div class="card text-center">
        <p class="text-3xl font-bold text-green-600">{{ stats?.total_in_service ?? 0 }}</p>
        <p class="text-sm text-gray-500 mt-1">In Service</p>
      </div>
      <div class="card text-center">
        <p class="text-3xl font-bold text-gray-700">{{ stats?.avg_wait_time_minutes ?? 0 }}</p>
        <p class="text-sm text-gray-500 mt-1">Avg Wait (min)</p>
      </div>
    </div>

    <!-- Add to Queue form -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-4">Add to Queue</h2>
      <form @submit.prevent="handleAdd" class="flex gap-3">
        <input
          v-model="addForm.phone"
          class="input flex-1"
          placeholder="Customer phone (+966...)"
          required
        />
        <select v-model="addForm.service_id" class="input w-48">
          <option value="">No service</option>
          <option v-for="svc in services" :key="svc.id" :value="svc.id">
            {{ svc.name_en }}
          </option>
        </select>
        <button type="submit" class="btn-primary whitespace-nowrap" :disabled="addLoading">
          Add
        </button>
      </form>
      <p v-if="addError" class="text-sm text-red-600 mt-2">{{ addError }}</p>
    </div>

    <!-- Queue list -->
    <div class="card p-0 overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">Current Queue</h2>
        <span class="badge badge-blue">{{ queueEntries.length }} in queue</span>
      </div>

      <div v-if="queueEntries.length === 0" class="py-12 text-center text-gray-400">
        <svg class="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M4 6h16M4 10h16M4 14h10" />
        </svg>
        <p>Queue is empty</p>
      </div>

      <div v-else class="divide-y divide-gray-100">
        <div
          v-for="entry in queueEntries"
          :key="entry.id"
          class="px-6 py-4 flex items-center gap-4 hover:bg-gray-50 transition-colors"
        >
          <!-- Position -->
          <div class="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-sm flex-shrink-0">
            {{ entry.position }}
          </div>

          <!-- Customer info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <p class="font-medium text-gray-900 truncate">
                {{ entry.customer.name || entry.customer.phone }}
              </p>
              <span v-if="entry.customer.is_vip" class="badge badge-purple">VIP</span>
            </div>
            <p class="text-sm text-gray-500">
              {{ entry.customer.phone }}
              <span v-if="entry.service"> · {{ entry.service.name_en }}</span>
              <span> · ~{{ entry.eta_minutes }}min</span>
            </p>
          </div>

          <!-- Status -->
          <StatusBadge :status="entry.status" />

          <!-- Actions -->
          <div class="flex items-center gap-2">
            <template v-if="entry.status === 'waiting'">
              <button
                @click="handleCancel(entry.id)"
                class="text-sm text-red-600 hover:text-red-800 px-2 py-1 rounded hover:bg-red-50"
              >
                Cancel
              </button>
            </template>
            <template v-if="entry.status === 'called'">
              <button
                @click="handleStart(entry.id)"
                class="btn-success text-xs py-1"
              >
                Start
              </button>
              <button
                @click="handleNoShow(entry.id)"
                class="text-sm text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
              >
                No Show
              </button>
            </template>
            <template v-if="entry.status === 'in_service'">
              <button
                @click="openFinish(entry.id)"
                class="btn-primary text-xs py-1"
              >
                Finish
              </button>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Finish modal -->
    <div v-if="finishModal.open" class="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl">
        <h3 class="font-semibold text-gray-900 mb-4">Finish Service</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Amount (SAR)</label>
            <input v-model.number="finishModal.amount" type="number" min="0" class="input" placeholder="0.00" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Notes</label>
            <input v-model="finishModal.notes" class="input" placeholder="Optional notes..." />
          </div>
        </div>
        <div class="flex gap-3 mt-5">
          <button @click="finishModal.open = false" class="btn-secondary flex-1">Cancel</button>
          <button @click="handleFinish" class="btn-primary flex-1" :disabled="finishLoading">
            Finish
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useAuthStore } from '@/stores/auth'
import { useQueueStore } from '@/stores/queue'
import { queueApi } from '@/api/queue'
import { servicesApi } from '@/api/services'
import { customersApi } from '@/api/customers'
import StatusBadge from '@/components/StatusBadge.vue'

const auth = useAuthStore()
const queueStore = useQueueStore()
const queryClient = useQueryClient()

// Connect WebSocket
onMounted(() => {
  if (auth.tenantId) queueStore.connect(auth.tenantId)
})
onUnmounted(() => queueStore.disconnect())

// Stats
const { data: stats, refetch: refetchStats } = useQuery({
  queryKey: ['queue-stats'],
  queryFn: queueApi.getStats,
  refetchInterval: 10_000,
})

// Services for dropdown
const { data: services } = useQuery({
  queryKey: ['services'],
  queryFn: servicesApi.list,
})

// Queue entries from WebSocket store (falls back to API)
const { data: queueData, refetch: refetchQueue } = useQuery({
  queryKey: ['queue'],
  queryFn: queueApi.getQueue,
  refetchInterval: 15_000,
})

const queueEntries = computed(() =>
  queueStore.entries.length ? queueStore.entries : (queueData.value ?? [])
)

const waitingCount = computed(() =>
  queueEntries.value.filter((e) => e.status === 'waiting').length
)

// Add to queue
const addForm = ref({ phone: '', service_id: '' })
const addError = ref('')
const addLoading = ref(false)

async function handleAdd() {
  addError.value = ''
  addLoading.value = true
  try {
    // Find or create customer by phone
    let customer = null
    try {
      const list = await customersApi.list({ search: addForm.value.phone, page_size: 1 })
      customer = list.items.find((c) => c.phone === addForm.value.phone)
    } catch {}

    if (!customer) {
      customer = await customersApi.create({ phone: addForm.value.phone })
    }

    await queueApi.addToQueue({
      customer_id: customer.id,
      service_id: addForm.value.service_id || undefined,
    })
    addForm.value.phone = ''
    addForm.value.service_id = ''
    refetchQueue()
    refetchStats()
  } catch (e: any) {
    addError.value = e?.response?.data?.detail ?? 'Failed to add customer'
  } finally {
    addLoading.value = false
  }
}

// Call next
const callNextLoading = ref(false)
async function handleCallNext() {
  callNextLoading.value = true
  try {
    await queueApi.callNext()
    refetchQueue()
    refetchStats()
  } catch (e: any) {
    alert(e?.response?.data?.detail ?? 'Queue is empty')
  } finally {
    callNextLoading.value = false
  }
}

// Start / Cancel / No Show
async function handleStart(id: string) {
  await queueApi.startService(id)
  refetchQueue()
}
async function handleCancel(id: string) {
  await queueApi.cancel(id)
  refetchQueue()
  refetchStats()
}
async function handleNoShow(id: string) {
  await queueApi.noShow(id)
  refetchQueue()
  refetchStats()
}

// Finish modal
const finishModal = ref({ open: false, entryId: '', amount: undefined as number | undefined, notes: '' })
const finishLoading = ref(false)

function openFinish(id: string) {
  finishModal.value = { open: true, entryId: id, amount: undefined, notes: '' }
}
async function handleFinish() {
  finishLoading.value = true
  try {
    await queueApi.finishService(finishModal.value.entryId, {
      amount: finishModal.value.amount,
      notes: finishModal.value.notes || undefined,
    })
    finishModal.value.open = false
    refetchQueue()
    refetchStats()
  } finally {
    finishLoading.value = false
  }
}

// Toggle accepting queue
async function handleToggleAccepting() {
  await queueApi.toggleAccepting()
  refetchStats()
}
</script>
