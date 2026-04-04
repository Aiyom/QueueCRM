<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">Services</h1>
      <button @click="showCreate = true" class="btn-primary">+ New Service</button>
    </div>

    <div class="card p-0 overflow-hidden">
      <table class="w-full">
        <thead class="bg-gray-50 border-b border-gray-100">
          <tr>
            <th class="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">#</th>
            <th class="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Name (EN)</th>
            <th class="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Name (AR)</th>
            <th class="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Avg Duration</th>
            <th class="px-6 py-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-if="!services?.length">
            <td colspan="5" class="py-8 text-center text-gray-400">No services yet</td>
          </tr>
          <tr v-for="(svc, i) in services" :key="svc.id" class="hover:bg-gray-50">
            <td class="px-6 py-4 text-gray-400 text-sm">{{ i + 1 }}</td>
            <td class="px-6 py-4 font-medium text-gray-900">{{ svc.name_en }}</td>
            <td class="px-6 py-4 text-gray-700">{{ svc.name_ar }}</td>
            <td class="px-6 py-4 text-gray-500 text-sm">{{ svc.avg_duration_minutes }} min</td>
            <td class="px-6 py-4 text-right flex items-center gap-2 justify-end">
              <button @click="startEdit(svc)" class="text-sm text-blue-600 hover:text-blue-800">Edit</button>
              <button @click="handleDelete(svc.id)" class="text-sm text-red-600 hover:text-red-800">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit modal -->
    <div v-if="showCreate || editService" class="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl">
        <h3 class="font-semibold text-gray-900 mb-4">{{ editService ? 'Edit Service' : 'New Service' }}</h3>
        <form @submit.prevent="editService ? handleUpdate() : handleCreate()" class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Name (English) *</label>
            <input v-model="form.name_en" class="input" required />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Name (Arabic) *</label>
            <input v-model="form.name_ar" class="input" required dir="rtl" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Avg Duration (minutes)</label>
            <input v-model.number="form.avg_duration_minutes" type="number" min="1" class="input" />
          </div>
          <div class="flex gap-3 mt-4">
            <button type="button" @click="closeModal" class="btn-secondary flex-1">Cancel</button>
            <button type="submit" class="btn-primary flex-1">
              {{ editService ? 'Save' : 'Create' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { servicesApi, type Service } from '@/api/services'

const queryClient = useQueryClient()

const { data: services } = useQuery({
  queryKey: ['services'],
  queryFn: servicesApi.list,
})

const showCreate = ref(false)
const editService = ref<Service | null>(null)
const form = ref({ name_en: '', name_ar: '', avg_duration_minutes: 30 })

function startEdit(svc: Service) {
  editService.value = svc
  form.value = { name_en: svc.name_en, name_ar: svc.name_ar, avg_duration_minutes: svc.avg_duration_minutes }
}

function closeModal() {
  showCreate.value = false
  editService.value = null
  form.value = { name_en: '', name_ar: '', avg_duration_minutes: 30 }
}

async function handleCreate() {
  await servicesApi.create(form.value)
  queryClient.invalidateQueries({ queryKey: ['services'] })
  closeModal()
}

async function handleUpdate() {
  if (!editService.value) return
  await servicesApi.update(editService.value.id, form.value)
  queryClient.invalidateQueries({ queryKey: ['services'] })
  closeModal()
}

async function handleDelete(id: string) {
  if (!confirm('Delete this service?')) return
  await servicesApi.delete(id)
  queryClient.invalidateQueries({ queryKey: ['services'] })
}
</script>
