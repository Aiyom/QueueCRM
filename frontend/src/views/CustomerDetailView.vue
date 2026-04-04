<template>
  <div class="p-6 space-y-6" v-if="customer">
    <!-- Back -->
    <button @click="$router.back()" class="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900">
      ← Back
    </button>

    <!-- Header -->
    <div class="card flex items-start gap-4">
      <div class="w-14 h-14 bg-blue-100 rounded-full flex items-center justify-center text-blue-700 font-bold text-xl flex-shrink-0">
        {{ (customer.name || customer.phone).charAt(0).toUpperCase() }}
      </div>
      <div class="flex-1">
        <div class="flex items-center gap-3">
          <h1 class="text-xl font-bold text-gray-900">{{ customer.name || customer.phone }}</h1>
          <span v-if="customer.is_vip" class="badge badge-purple">VIP</span>
        </div>
        <p class="text-gray-500">{{ customer.phone }}</p>
        <div class="flex gap-6 mt-3">
          <div>
            <p class="text-2xl font-bold text-gray-900">{{ customer.total_visits }}</p>
            <p class="text-xs text-gray-500">Total Visits</p>
          </div>
          <div>
            <p class="text-2xl font-bold text-gray-900">{{ customer.total_spent }} SAR</p>
            <p class="text-xs text-gray-500">Total Spent</p>
          </div>
        </div>
      </div>
      <button @click="showEdit = !showEdit" class="btn-secondary text-sm">Edit</button>
    </div>

    <!-- Edit form -->
    <div v-if="showEdit" class="card">
      <h2 class="font-semibold text-gray-900 mb-4">Edit Customer</h2>
      <form @submit.prevent="handleUpdate" class="space-y-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input v-model="editForm.name" class="input" placeholder="Customer name" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Notes</label>
          <input v-model="editForm.notes" class="input" placeholder="Internal notes" />
        </div>
        <div class="flex items-center gap-2">
          <input v-model="editForm.is_vip" type="checkbox" id="vip" class="rounded" />
          <label for="vip" class="text-sm text-gray-700">Mark as VIP</label>
        </div>
        <div class="flex gap-3">
          <button type="button" @click="showEdit = false" class="btn-secondary">Cancel</button>
          <button type="submit" class="btn-primary">Save</button>
        </div>
      </form>
    </div>
  </div>
  <div v-else-if="isLoading" class="p-6 text-center text-gray-400">Loading...</div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { customersApi } from '@/api/customers'

const route = useRoute()
const queryClient = useQueryClient()

const { data: customer, isLoading } = useQuery({
  queryKey: computed(() => ['customer', route.params.id]),
  queryFn: () => customersApi.get(route.params.id as string),
})

const showEdit = ref(false)
const editForm = ref({ name: '', notes: '', is_vip: false })

watch(customer, (c) => {
  if (c) editForm.value = { name: c.name ?? '', notes: c.notes ?? '', is_vip: c.is_vip }
}, { immediate: true })

async function handleUpdate() {
  await customersApi.update(route.params.id as string, {
    name: editForm.value.name || undefined,
    notes: editForm.value.notes || undefined,
    is_vip: editForm.value.is_vip,
  })
  queryClient.invalidateQueries({ queryKey: ['customer', route.params.id] })
  showEdit.value = false
}
</script>

<script lang="ts">
import { computed } from 'vue'
export default { name: 'CustomerDetailView' }
</script>
