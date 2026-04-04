<template>
  <div class="p-8">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">{{ $t('plans.title') }}</h1>
      <button
        @click="openCreate"
        class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition"
      >
        + {{ $t('plans.addPlan') }}
      </button>
    </div>

    <div v-if="isLoading" class="text-gray-500 text-sm">{{ $t('common.loading') }}</div>
    <div v-else-if="isError" class="text-red-600 text-sm">{{ $t('common.error') }}</div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="plan in data"
        :key="plan.id"
        :class="['bg-white rounded-xl shadow-sm border-2 p-5', plan.is_active ? 'border-gray-100' : 'border-dashed border-gray-200 opacity-60']"
      >
        <div class="flex items-start justify-between mb-3">
          <div>
            <p class="font-bold text-gray-900">{{ plan.name_en }}</p>
            <p v-if="plan.name_ru" class="text-xs text-gray-400">{{ plan.name_ru }}</p>
            <code class="text-xs bg-gray-100 px-1.5 py-0.5 rounded text-gray-500 mt-1 inline-block">{{ plan.slug }}</code>
          </div>
          <span
            :class="plan.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
            class="text-xs font-medium px-2 py-0.5 rounded-full"
          >{{ plan.is_active ? $t('statuses.active') : $t('plans.archived') }}</span>
        </div>

        <p class="text-2xl font-bold text-indigo-600 mb-3">
          ${{ plan.price_usd }}
          <span class="text-sm font-normal text-gray-400">/ mo</span>
        </p>

        <ul v-if="plan.features?.length" class="space-y-1 mb-4">
          <li v-for="f in plan.features" :key="f" class="flex items-center gap-2 text-sm text-gray-600">
            <span class="text-green-500 text-xs">✓</span>{{ f }}
          </li>
        </ul>
        <p v-else class="text-sm text-gray-400 mb-4 italic">{{ $t('plans.noFeatures') }}</p>

        <div class="flex gap-2">
          <button
            @click="openEdit(plan)"
            class="flex-1 text-xs border border-indigo-200 text-indigo-600 hover:bg-indigo-50 py-1.5 rounded-lg transition"
          >{{ $t('common.edit') }}</button>
          <button
            v-if="plan.is_active"
            @click="archivePlan(plan.id)"
            class="text-xs border border-red-200 text-red-500 hover:bg-red-50 px-3 py-1.5 rounded-lg transition"
          >{{ $t('plans.archive') }}</button>
          <button
            v-else
            @click="restorePlan(plan.id)"
            class="text-xs border border-green-200 text-green-600 hover:bg-green-50 px-3 py-1.5 rounded-lg transition"
          >{{ $t('plans.restore') }}</button>
        </div>
      </div>
    </div>

    <!-- Create / Edit modal -->
    <div v-if="modalOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <h2 class="text-lg font-semibold mb-4">
          {{ editingPlan ? $t('plans.editPlan') : $t('plans.addPlan') }}
        </h2>
        <form @submit.prevent="handleSave" class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="label">Slug</label>
              <input v-model="form.slug" :disabled="!!editingPlan" required class="input" placeholder="pro" />
            </div>
            <div>
              <label class="label">{{ $t('plans.price') }} (USD/mo)</label>
              <input v-model.number="form.price_usd" type="number" min="1" step="0.01" required class="input" />
            </div>
          </div>
          <div>
            <label class="label">Name EN</label>
            <input v-model="form.name_en" required class="input" placeholder="Pro" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="label">Name RU</label>
              <input v-model="form.name_ru" class="input" placeholder="Про" />
            </div>
            <div>
              <label class="label">Name AR</label>
              <input v-model="form.name_ar" class="input" dir="rtl" placeholder="برو" />
            </div>
          </div>
          <div>
            <label class="label">{{ $t('plans.features') }} <span class="text-gray-400 font-normal">({{ $t('plans.onePerLine') }})</span></label>
            <textarea
              v-model="featuresText"
              rows="4"
              class="input resize-none"
              :placeholder="$t('plans.featuresPlaceholder')"
            />
          </div>
          <div>
            <label class="label">{{ $t('plans.sortOrder') }}</label>
            <input v-model.number="form.sort_order" type="number" class="input w-24" />
          </div>
          <p v-if="saveError" class="text-red-600 text-xs">{{ saveError }}</p>
          <div class="flex gap-2 pt-2">
            <button type="submit" :disabled="saving"
              class="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition">
              {{ saving ? $t('common.loading') : $t('common.save') }}
            </button>
            <button type="button" @click="modalOpen = false"
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
import { ref, computed } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { useI18n } from 'vue-i18n'
import { adminApi, type Plan } from '@/api/admin'

const { t } = useI18n()
const queryClient = useQueryClient()

const { data, isLoading, isError } = useQuery({
  queryKey: ['plans'],
  queryFn: adminApi.listPlans,
})

const modalOpen = ref(false)
const saving = ref(false)
const saveError = ref('')
const editingPlan = ref<Plan | null>(null)
const featuresText = ref('')

const form = ref({
  slug: '',
  name_en: '',
  name_ar: '',
  name_ru: '',
  price_usd: 50,
  sort_order: 0,
})

function openCreate() {
  editingPlan.value = null
  form.value = { slug: '', name_en: '', name_ar: '', name_ru: '', price_usd: 50, sort_order: 0 }
  featuresText.value = ''
  saveError.value = ''
  modalOpen.value = true
}

function openEdit(plan: Plan) {
  editingPlan.value = plan
  form.value = {
    slug: plan.slug,
    name_en: plan.name_en,
    name_ar: plan.name_ar ?? '',
    name_ru: plan.name_ru ?? '',
    price_usd: plan.price_usd,
    sort_order: plan.sort_order,
  }
  featuresText.value = plan.features?.join('\n') ?? ''
  saveError.value = ''
  modalOpen.value = true
}

async function handleSave() {
  saving.value = true
  saveError.value = ''
  const features = featuresText.value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)

  try {
    if (editingPlan.value) {
      await adminApi.updatePlan(editingPlan.value.id, {
        name_en: form.value.name_en,
        name_ar: form.value.name_ar || undefined,
        name_ru: form.value.name_ru || undefined,
        price_usd: form.value.price_usd,
        features,
        sort_order: form.value.sort_order,
      })
    } else {
      await adminApi.createPlan({
        slug: form.value.slug,
        name_en: form.value.name_en,
        name_ar: form.value.name_ar || undefined,
        name_ru: form.value.name_ru || undefined,
        price_usd: form.value.price_usd,
        features,
        sort_order: form.value.sort_order,
      })
    }
    await queryClient.invalidateQueries({ queryKey: ['plans'] })
    modalOpen.value = false
  } catch (e: any) {
    saveError.value = e.response?.data?.detail ?? t('common.error')
  } finally {
    saving.value = false
  }
}

async function archivePlan(id: string) {
  await adminApi.updatePlan(id, { is_active: false })
  queryClient.invalidateQueries({ queryKey: ['plans'] })
}

async function restorePlan(id: string) {
  await adminApi.updatePlan(id, { is_active: true })
  queryClient.invalidateQueries({ queryKey: ['plans'] })
}
</script>

<style scoped>
.input { @apply w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500; }
.label { @apply block text-xs font-medium text-gray-600 mb-1; }
</style>
