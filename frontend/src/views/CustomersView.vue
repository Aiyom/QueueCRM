<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">Customers</h1>
      <button @click="showCreate = true" class="btn-primary">+ New Customer</button>
    </div>

    <!-- Segment stats -->
    <div v-if="segmentStats" class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div class="card text-center">
        <p class="text-2xl font-bold text-gray-900">{{ segmentStats.total_customers }}</p>
        <p class="text-xs text-gray-500 mt-1">Total</p>
      </div>
      <div class="card text-center">
        <p class="text-2xl font-bold text-purple-600">{{ segmentStats.vip_customers }}</p>
        <p class="text-xs text-gray-500 mt-1">VIP</p>
      </div>
      <div class="card text-center">
        <p class="text-2xl font-bold text-blue-600">{{ segmentStats.new_this_month }}</p>
        <p class="text-xs text-gray-500 mt-1">New This Month</p>
      </div>
      <div class="card text-center">
        <p class="text-2xl font-bold text-green-600">{{ segmentStats.avg_visits }}</p>
        <p class="text-xs text-gray-500 mt-1">Avg Visits</p>
      </div>
      <div class="card text-center">
        <p class="text-2xl font-bold text-yellow-600">{{ segmentStats.avg_spent }} SAR</p>
        <p class="text-xs text-gray-500 mt-1">Avg Spent</p>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex gap-3">
      <input
        v-model="search"
        class="input flex-1 max-w-xs"
        placeholder="Search name or phone..."
        @input="debouncedSearch"
      />
      <select v-model="vipFilter" class="input w-36">
        <option value="">All</option>
        <option value="true">VIP only</option>
        <option value="false">Regular</option>
      </select>
    </div>

    <!-- Table -->
    <div class="card p-0 overflow-hidden">
      <table class="w-full">
        <thead class="bg-gray-50 border-b border-gray-100">
          <tr>
            <th class="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Customer</th>
            <th class="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Phone</th>
            <th class="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Visits</th>
            <th class="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Spent</th>
            <th class="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Last Visit</th>
            <th class="px-6 py-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-if="isLoading">
            <td colspan="6" class="py-8 text-center text-gray-400">Loading...</td>
          </tr>
          <tr v-else-if="!customers?.items?.length">
            <td colspan="6" class="py-8 text-center text-gray-400">No customers found</td>
          </tr>
          <tr
            v-else
            v-for="c in customers.items"
            :key="c.id"
            class="hover:bg-gray-50 cursor-pointer"
            @click="$router.push(`/customers/${c.id}`)"
          >
            <td class="px-6 py-4">
              <div class="flex items-center gap-2">
                <span class="font-medium text-gray-900">{{ c.name || '—' }}</span>
                <span v-if="c.is_vip" class="badge badge-purple">VIP</span>
              </div>
            </td>
            <td class="px-6 py-4 text-gray-500 text-sm">{{ c.phone }}</td>
            <td class="px-6 py-4 text-gray-700 text-sm">{{ c.total_visits }}</td>
            <td class="px-6 py-4 text-gray-700 text-sm">{{ c.total_spent }} SAR</td>
            <td class="px-6 py-4 text-gray-500 text-sm">{{ formatDate(c.last_seen_at) }}</td>
            <td class="px-6 py-4 text-right">
              <button
                @click.stop="$router.push(`/customers/${c.id}`)"
                class="text-blue-600 hover:text-blue-800 text-sm"
              >
                View →
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div v-if="customers && customers.total > pageSize" class="px-6 py-3 border-t border-gray-100 flex items-center justify-between">
        <p class="text-sm text-gray-500">{{ customers.total }} customers</p>
        <div class="flex gap-2">
          <button @click="page--" :disabled="page === 1" class="btn-secondary text-sm py-1 px-3">Prev</button>
          <button @click="page++" :disabled="page * pageSize >= customers.total" class="btn-secondary text-sm py-1 px-3">Next</button>
        </div>
      </div>
    </div>

    <!-- Create customer modal -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl">
        <h3 class="font-semibold text-gray-900 mb-4">New Customer</h3>
        <form @submit.prevent="handleCreate" class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Phone *</label>
            <input v-model="createForm.phone" class="input" placeholder="+966501234567" required />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input v-model="createForm.name" class="input" placeholder="Optional" />
          </div>
          <div class="flex gap-3 mt-4">
            <button type="button" @click="showCreate = false" class="btn-secondary flex-1">Cancel</button>
            <button type="submit" class="btn-primary flex-1">Create</button>
          </div>
          <p v-if="createError" class="text-sm text-red-600">{{ createError }}</p>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { customersApi } from '@/api/customers'
import { format, parseISO } from 'date-fns'

const search = ref('')
const vipFilter = ref('')
const page = ref(1)
const pageSize = 20

let searchTimer: ReturnType<typeof setTimeout>
function debouncedSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1 }, 400)
}

watch([vipFilter], () => { page.value = 1 })

const queryParams = computed(() => ({
  page: page.value,
  page_size: pageSize,
  search: search.value || undefined,
  is_vip: vipFilter.value === '' ? undefined : vipFilter.value === 'true',
}))

const { data: customers, isLoading } = useQuery({
  queryKey: computed(() => ['customers', queryParams.value]),
  queryFn: () => customersApi.list(queryParams.value),
})

const { data: segmentStats } = useQuery({
  queryKey: ['customer-segments'],
  queryFn: customersApi.segmentStats,
})

function formatDate(d: string | null) {
  if (!d) return '—'
  try { return format(parseISO(d), 'MMM d, yyyy') } catch { return '—' }
}

// Create
const showCreate = ref(false)
const createForm = ref({ phone: '', name: '' })
const createError = ref('')

async function handleCreate() {
  createError.value = ''
  try {
    await customersApi.create({ phone: createForm.value.phone, name: createForm.value.name || undefined })
    showCreate.value = false
    createForm.value = { phone: '', name: '' }
  } catch (e: any) {
    createError.value = e?.response?.data?.detail ?? 'Failed to create customer'
  }
}
</script>
