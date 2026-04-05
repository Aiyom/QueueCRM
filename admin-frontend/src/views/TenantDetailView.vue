<template>
  <div class="p-8 max-w-3xl">
    <button @click="router.back()" class="text-sm text-indigo-600 hover:underline mb-4 flex items-center gap-1">
      {{ $t('tenantDetail.back') }}
    </button>

    <div v-if="isLoading" class="text-gray-500 text-sm">{{ $t('common.loading') }}</div>
    <div v-else-if="isError" class="text-red-600 text-sm">{{ $t('common.error') }}</div>

    <template v-else-if="data">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-2xl font-bold text-gray-800">{{ data.name }}</h1>
          <p class="text-gray-500 text-sm mt-0.5">{{ data.slug }}</p>
        </div>
        <div class="flex gap-2">
          <button
            v-if="data.is_active"
            @click="doDeactivate"
            :disabled="acting"
            class="text-sm border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-50 px-3 py-1.5 rounded-lg transition"
          >{{ $t('tenantDetail.deactivate') }}</button>
          <button
            v-else
            @click="doActivate"
            :disabled="acting"
            class="text-sm border border-green-300 text-green-700 hover:bg-green-50 disabled:opacity-50 px-3 py-1.5 rounded-lg transition"
          >{{ $t('tenantDetail.activate') }}</button>
        </div>
      </div>

      <!-- Info cards -->
      <div class="grid grid-cols-2 gap-4 mb-6">
        <div class="bg-white rounded-xl shadow-sm p-4">
          <p class="text-xs text-gray-500 mb-1">{{ $t('tenantDetail.status') }}</p>
          <span
            :class="data.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
            class="px-2 py-0.5 rounded-full text-xs font-medium"
          >{{ data.is_active ? $t('statuses.active') : $t('statuses.inactive') }}</span>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4">
          <p class="text-xs text-gray-500 mb-1">{{ $t('tenants.businessType') }}</p>
          <p class="text-sm font-medium text-gray-800">{{ $t(`tenants.types.${data.business_type}`) }}</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4">
          <p class="text-xs text-gray-500 mb-1">{{ $t('tenantDetail.phone') }}</p>
          <p class="text-sm font-medium text-gray-800">{{ data.phone }}</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4">
          <p class="text-xs text-gray-500 mb-1">{{ $t('tenantDetail.created') }}</p>
          <p class="text-sm font-medium text-gray-800">{{ formatDate(data.created_at) }}</p>
        </div>
      </div>

      <!-- Subscription -->
      <div v-if="data.subscription" class="bg-white rounded-xl shadow-sm p-4 mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="font-semibold text-gray-700">{{ $t('tenantDetail.subscription') }}</h2>
          <button
            @click="openSubEdit"
            class="text-xs text-indigo-600 hover:underline"
          >{{ $t('common.edit') }}</button>
        </div>

        <!-- Current subscription info -->
        <div class="grid grid-cols-2 gap-3 text-sm mb-4">
          <div>
            <p class="text-xs text-gray-500">{{ $t('tenantDetail.plan') }}</p>
            <p class="font-medium text-gray-800">{{ $t(`plans.${data.subscription.plan}`) }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500">{{ $t('tenantDetail.subStatus') }}</p>
            <span :class="subBadge(data.subscription.status)" class="px-2 py-0.5 rounded-full text-xs font-medium">
              {{ $t(`statuses.${data.subscription.status}`) }}
            </span>
          </div>
          <div>
            <p class="text-xs text-gray-500">{{ $t('tenantDetail.trialEnds') }}</p>
            <p class="font-medium text-gray-800">{{ formatDate(data.subscription.trial_ends_at) }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500">{{ $t('subscription.effectivePrice') }}</p>
            <p class="font-medium text-gray-800">
              <template v-if="data.subscription.monthly_price_usd != null">
                <span v-if="data.subscription.discount_pct">
                  ${{ effectivePrice(data.subscription.monthly_price_usd, data.subscription.discount_pct) }}
                  <span class="text-green-600 text-xs">(-{{ data.subscription.discount_pct }}%)</span>
                </span>
                <span v-else>${{ data.subscription.monthly_price_usd }}/mo</span>
              </template>
              <span v-else class="text-gray-400">—</span>
            </p>
          </div>
        </div>

        <div v-if="data.subscription.notes" class="bg-yellow-50 border border-yellow-100 rounded-lg p-2 text-xs text-yellow-800 mb-4">
          {{ data.subscription.notes }}
        </div>

        <!-- Extend trial -->
        <div class="border-t pt-3 flex items-center gap-2">
          <input
            v-model.number="extendDays"
            type="number"
            min="1"
            max="365"
            class="border rounded-lg px-3 py-1.5 text-sm w-24 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            :placeholder="$t('tenantDetail.extendDays')"
          />
          <button
            @click="doExtendTrial"
            :disabled="acting || !extendDays"
            class="text-sm bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg transition"
          >{{ $t('tenantDetail.extendTrial') }}</button>
          <p v-if="actionMessage" class="text-xs text-green-600">{{ actionMessage }}</p>
        </div>
      </div>

      <!-- WhatsApp config -->
      <div class="bg-white rounded-xl shadow-sm p-4 mb-4">
        <h2 class="font-semibold text-gray-700 mb-3">{{ $t('tenantDetail.credentials360') }}</h2>
        <div class="space-y-3 text-sm">
          <div>
            <p class="text-xs text-gray-500 mb-1">{{ $t('tenantDetail.apiKey') }}</p>
            <p class="font-mono text-xs text-gray-700 break-all">{{ data.d360_api_key ?? '—' }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 mb-1">{{ $t('tenantDetail.channelId') }}</p>
            <p class="font-mono text-xs text-gray-700">{{ data.d360_channel_id ?? '—' }}</p>
          </div>
        </div>
      </div>

      <!-- Languages & Telegram -->
      <div class="bg-white rounded-xl shadow-sm p-4">
        <h2 class="font-semibold text-gray-700 mb-3">{{ $t('tenantDetail.integrations') }}</h2>
        <div class="space-y-3 text-sm">
          <div>
            <p class="text-xs text-gray-500 mb-1">{{ $t('tenantDetail.enabledLanguages') }}</p>
            <div class="flex gap-2 flex-wrap">
              <span
                v-for="lang in (data.enabled_languages ?? ['ar','en'])"
                :key="lang"
                class="px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700"
              >{{ lang.toUpperCase() }}</span>
            </div>
          </div>
          <div>
            <p class="text-xs text-gray-500 mb-1">{{ $t('tenantDetail.telegramBot') }}</p>
            <p class="text-sm">
              <span v-if="data.telegram_bot_token" class="text-green-700 font-medium">✓ {{ $t('tenantDetail.telegramConfigured') }}</span>
              <span v-else class="text-gray-400">{{ $t('tenantDetail.telegramNotSet') }}</span>
            </p>
          </div>
        </div>
      </div>
    </template>

    <!-- Edit subscription modal -->
    <div v-if="subEditOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
        <h2 class="text-lg font-semibold mb-4">{{ $t('subscription.editTitle') }}</h2>
        <form @submit.prevent="saveSubscription" class="space-y-3">
          <div>
            <label class="label">{{ $t('subscription.plan') }}</label>
            <select v-model="subForm.plan" class="input">
              <option value="starter">Starter</option>
              <option value="pro">Pro</option>
              <option value="business">Business</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          <div>
            <label class="label">{{ $t('subscription.status') }}</label>
            <select v-model="subForm.status" class="input">
              <option value="trial">Trial</option>
              <option value="active">Active</option>
              <option value="past_due">Past Due</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          <div>
            <label class="label">{{ $t('subscription.customPrice') }}</label>
            <input
              v-model.number="subForm.monthly_price_usd"
              type="number"
              min="0"
              step="0.01"
              class="input"
              :placeholder="$t('subscription.customPriceHint')"
            />
            <p class="text-xs text-gray-400 mt-0.5">{{ $t('subscription.customPriceHint') }}</p>
          </div>
          <div>
            <label class="label">{{ $t('subscription.discount') }}</label>
            <input
              v-model.number="subForm.discount_pct"
              type="number"
              min="0"
              max="100"
              class="input"
              placeholder="0"
            />
            <p class="text-xs text-gray-400 mt-0.5">{{ $t('subscription.discountHint') }}</p>
          </div>

          <!-- Effective price preview -->
          <div v-if="subForm.monthly_price_usd" class="bg-indigo-50 rounded-lg p-3 text-sm">
            <span class="text-gray-600">{{ $t('subscription.effectivePrice') }}: </span>
            <span class="font-semibold text-indigo-700">
              ${{ effectivePrice(subForm.monthly_price_usd, subForm.discount_pct ?? 0) }}/mo
            </span>
            <span v-if="subForm.discount_pct" class="text-green-600 text-xs ms-1">
              (сохранено ${{ (subForm.monthly_price_usd * (subForm.discount_pct / 100)).toFixed(2) }})
            </span>
          </div>

          <div>
            <label class="label">{{ $t('subscription.notes') }}</label>
            <textarea v-model="subForm.notes" rows="2" class="input resize-none" />
          </div>
          <p v-if="subError" class="text-red-600 text-xs">{{ subError }}</p>
          <div class="flex gap-2 pt-2">
            <button type="submit" :disabled="subSaving"
              class="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition">
              {{ subSaving ? $t('common.loading') : $t('subscription.save') }}
            </button>
            <button type="button" @click="subEditOpen = false"
              class="flex-1 border text-sm font-medium py-2 rounded-lg hover:bg-gray-50 transition">
              {{ $t('common.cancel') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { adminApi } from '@/api/admin'
import { useFormatters } from '@/composables/useFormatters'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const { formatDate } = useFormatters()

const tenantId = route.params.id as string
const acting = ref(false)
const extendDays = ref<number | null>(null)
const actionMessage = ref('')

// Subscription edit
const subEditOpen = ref(false)
const subSaving = ref(false)
const subError = ref('')
const subForm = ref({
  plan: 'starter',
  status: 'trial',
  monthly_price_usd: null as number | null,
  discount_pct: null as number | null,
  notes: '',
})

const { data, isLoading, isError } = useQuery({
  queryKey: ['tenant', tenantId],
  queryFn: () => adminApi.getTenant(tenantId),
})

function openSubEdit() {
  const sub = data.value?.subscription
  subForm.value = {
    plan: sub?.plan ?? 'starter',
    status: sub?.status ?? 'trial',
    monthly_price_usd: sub?.monthly_price_usd ?? null,
    discount_pct: sub?.discount_pct ?? null,
    notes: sub?.notes ?? '',
  }
  subError.value = ''
  subEditOpen.value = true
}

async function saveSubscription() {
  subSaving.value = true
  subError.value = ''
  try {
    await adminApi.updateSubscription(tenantId, {
      plan: subForm.value.plan,
      status: subForm.value.status,
      monthly_price_usd: subForm.value.monthly_price_usd,
      discount_pct: subForm.value.discount_pct,
      notes: subForm.value.notes || null,
    })
    await queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] })
    await queryClient.invalidateQueries({ queryKey: ['tenants'] })
    subEditOpen.value = false
  } catch (e: any) {
    subError.value = e.response?.data?.detail ?? t('common.error')
  } finally {
    subSaving.value = false
  }
}

function effectivePrice(price: number, discountPct: number): string {
  const discounted = price * (1 - discountPct / 100)
  return discounted.toFixed(2)
}

async function doActivate() {
  acting.value = true
  try {
    await adminApi.activateTenant(tenantId)
    await queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] })
    await queryClient.invalidateQueries({ queryKey: ['tenants'] })
  } catch { alert(t('common.failed')) } finally { acting.value = false }
}

async function doDeactivate() {
  acting.value = true
  try {
    await adminApi.deactivateTenant(tenantId)
    await queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] })
    await queryClient.invalidateQueries({ queryKey: ['tenants'] })
  } catch { alert(t('common.failed')) } finally { acting.value = false }
}

async function doExtendTrial() {
  if (!extendDays.value) return
  acting.value = true
  actionMessage.value = ''
  try {
    await adminApi.extendTrial(tenantId, extendDays.value)
    await queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] })
    actionMessage.value = t('common.extended', { days: extendDays.value })
    extendDays.value = null
  } catch { alert(t('common.failed')) } finally { acting.value = false }
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
.input { @apply w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500; }
.label { @apply block text-xs font-medium text-gray-600 mb-1; }
</style>
