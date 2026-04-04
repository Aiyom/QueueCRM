<template>
  <div class="p-8">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">{{ $t('tenants.title') }}</h1>
      <button
        @click="showCreate = true"
        class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition"
      >
        + {{ $t('tenants.newTenant') }}
      </button>
    </div>

    <div v-if="isLoading" class="text-gray-500 text-sm">{{ $t('common.loading') }}</div>
    <div v-else-if="isError" class="text-red-600 text-sm">{{ $t('common.error') }}</div>

    <div v-else class="bg-white rounded-xl shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b">
          <tr>
            <th class="text-left px-4 py-3 font-medium text-gray-600">{{ $t('tenants.cols.name') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">{{ $t('tenants.cols.slug') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">{{ $t('tenants.businessType') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">{{ $t('tenants.cols.status') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">{{ $t('tenants.cols.trialEnds') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">{{ $t('tenants.cols.actions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr
            v-for="tenant in data"
            :key="tenant.id"
            class="hover:bg-gray-50 cursor-pointer"
            @click="router.push(`/tenants/${tenant.id}`)"
          >
            <td class="px-4 py-3 font-medium text-gray-800">{{ tenant.name }}</td>
            <td class="px-4 py-3 text-gray-500">{{ tenant.slug }}</td>
            <td class="px-4 py-3 text-gray-500">{{ $t(`tenants.types.${tenant.business_type}`) }}</td>
            <td class="px-4 py-3">
              <span
                :class="tenant.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
                class="px-2 py-0.5 rounded-full text-xs font-medium"
              >
                {{ tenant.is_active ? $t('statuses.active') : $t('statuses.inactive') }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-500">
              <span v-if="tenant.subscription">
                <span :class="subBadge(tenant.subscription.status)" class="px-2 py-0.5 rounded-full text-xs font-medium mr-1">
                  {{ $t(`statuses.${tenant.subscription.status}`) }}
                </span>
                {{ formatDate(tenant.subscription.trial_ends_at) }}
              </span>
              <span v-else class="text-gray-400">—</span>
            </td>
            <td class="px-4 py-3" @click.stop>
              <button
                v-if="tenant.is_active"
                @click="toggleActive(tenant.id, false)"
                class="text-xs text-red-600 hover:underline"
              >{{ $t('tenants.actions.deactivate') }}</button>
              <button
                v-else
                @click="toggleActive(tenant.id, true)"
                class="text-xs text-green-600 hover:underline"
              >{{ $t('tenants.actions.activate') }}</button>
            </td>
          </tr>
          <tr v-if="data && data.length === 0">
            <td colspan="6" class="px-4 py-8 text-center text-gray-400 text-sm">{{ $t('tenants.empty') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create modal -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
        <h2 class="text-lg font-semibold mb-4">{{ $t('addTenantModal.title') }}</h2>
        <form @submit.prevent="handleCreate" class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ $t('addTenantModal.businessName') }}</label>
            <input v-model="form.name" required class="input" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ $t('addTenantModal.slug') }}</label>
            <input v-model="form.slug" required class="input" :placeholder="$t('addTenantModal.slugHint')" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ $t('addTenantModal.phone') }}</label>
            <input v-model="form.phone" required class="input" placeholder="+966501234567" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ $t('tenants.businessType') }}</label>
            <select v-model="form.business_type" class="input">
              <option value="auto_service">{{ $t('tenants.types.auto_service') }}</option>
              <option value="barbershop">{{ $t('tenants.types.barbershop') }}</option>
              <option value="beauty_salon">{{ $t('tenants.types.beauty_salon') }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ $t('addTenantModal.apiKey') }}</label>
            <input v-model="form.d360_api_key" class="input" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">{{ $t('addTenantModal.channelId') }}</label>
            <input v-model="form.d360_channel_id" class="input" />
          </div>
          <p v-if="createError" class="text-red-600 text-xs">{{ createError }}</p>
          <div class="flex gap-2 pt-2">
            <button type="submit" :disabled="creating"
              class="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition">
              {{ creating ? $t('tenants.creating') : $t('tenants.create') }}
            </button>
            <button type="button" @click="showCreate = false"
              class="flex-1 border text-sm font-medium py-2 rounded-lg hover:bg-gray-50 transition">
              {{ $t('tenants.cancel') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { adminApi } from '@/api/admin'
import { useFormatters } from '@/composables/useFormatters'

const { t } = useI18n()
const router = useRouter()
const queryClient = useQueryClient()
const { formatDate } = useFormatters()

const { data, isLoading, isError } = useQuery({
  queryKey: ['tenants'],
  queryFn: adminApi.listTenants,
})

const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const form = ref({
  name: '',
  slug: '',
  phone: '',
  business_type: 'auto_service',
  d360_api_key: '',
  d360_channel_id: '',
})

async function handleCreate() {
  creating.value = true
  createError.value = ''
  try {
    await adminApi.createTenant(form.value)
    await queryClient.invalidateQueries({ queryKey: ['tenants'] })
    showCreate.value = false
    form.value = { name: '', slug: '', phone: '', business_type: 'auto_service', d360_api_key: '', d360_channel_id: '' }
  } catch (e: any) {
    createError.value = e.response?.data?.detail ?? t('common.error')
  } finally {
    creating.value = false
  }
}

async function toggleActive(id: string, activate: boolean) {
  try {
    if (activate) {
      await adminApi.activateTenant(id)
    } else {
      await adminApi.deactivateTenant(id)
    }
    await queryClient.invalidateQueries({ queryKey: ['tenants'] })
  } catch {
    alert(t('common.failed'))
  }
}

function subBadge(status: string) {
  return {
    trial: 'bg-blue-100 text-blue-700',
    active: 'bg-green-100 text-green-700',
    past_due: 'bg-red-100 text-red-700',
    cancelled: 'bg-gray-100 text-gray-600',
  }[status] ?? 'bg-gray-100 text-gray-600'
}
</script>

<style scoped>
.input {
  @apply w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500;
}
</style>
