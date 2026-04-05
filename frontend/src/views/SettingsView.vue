<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">Settings</h1>

    <!-- QR Code -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-4">Public Queue Page</h2>
      <p class="text-sm text-gray-500 mb-4">
        Share this link or QR code with customers to join the queue via WhatsApp.
      </p>
      <div class="flex items-center gap-4">
        <div class="bg-white border-2 border-gray-200 rounded-lg p-3" v-if="qrDataUrl">
          <img :src="qrDataUrl" alt="QR Code" class="w-32 h-32" />
        </div>
        <div class="flex-1">
          <label class="block text-sm font-medium text-gray-700 mb-1">Queue URL</label>
          <div class="flex gap-2">
            <input :value="publicUrl" readonly class="input flex-1 bg-gray-50" />
            <button @click="copyUrl" class="btn-secondary">
              {{ copied ? 'Copied!' : 'Copy' }}
            </button>
          </div>
          <button @click="downloadQr" class="btn-secondary mt-2 text-sm" v-if="qrDataUrl">
            Download QR
          </button>
        </div>
      </div>
    </div>

    <!-- Languages -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-1">Interface Languages</h2>
      <p class="text-sm text-gray-500 mb-4">Choose which languages are available to your customers.</p>
      <div v-if="loadingSettings" class="text-sm text-gray-400">Loading...</div>
      <div v-else class="space-y-3">
        <label
          v-for="lang in availableLanguages"
          :key="lang.code"
          class="flex items-center gap-3 cursor-pointer"
        >
          <input
            type="checkbox"
            :value="lang.code"
            v-model="selectedLanguages"
            :disabled="selectedLanguages.length === 1 && selectedLanguages.includes(lang.code)"
            class="w-4 h-4 text-blue-600 rounded border-gray-300"
          />
          <span class="text-sm font-medium text-gray-700">{{ lang.label }}</span>
          <span class="text-xs text-gray-400">{{ lang.native }}</span>
        </label>
        <div class="pt-2">
          <button
            @click="saveLanguages"
            :disabled="savingLangs"
            class="btn-primary text-sm"
          >
            {{ savingLangs ? 'Saving...' : 'Save Languages' }}
          </button>
          <span v-if="langsSaved" class="ml-3 text-sm text-green-600">Saved!</span>
        </div>
      </div>
    </div>

    <!-- Telegram -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-1">Telegram Bot</h2>
      <p class="text-sm text-gray-500 mb-4">
        Optional alternative to WhatsApp. Create a bot via
        <a href="https://t.me/BotFather" target="_blank" class="text-blue-600 underline">@BotFather</a>
        and paste the token here.
      </p>
      <div v-if="loadingSettings" class="text-sm text-gray-400">Loading...</div>
      <div v-else class="space-y-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Bot Token</label>
          <input
            v-model="telegramToken"
            type="password"
            placeholder="123456789:AABBccDDeeFFggHH..."
            class="input w-full"
          />
          <p class="text-xs text-gray-400 mt-1">Leave empty to disable Telegram.</p>
        </div>
        <button
          @click="saveTelegram"
          :disabled="savingTelegram"
          class="btn-primary text-sm"
        >
          {{ savingTelegram ? 'Saving...' : 'Save Telegram Token' }}
        </button>
        <span v-if="telegramSaved" class="ml-3 text-sm text-green-600">Saved!</span>
      </div>
    </div>

    <!-- Account info -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-4">Account</h2>
      <div class="space-y-2 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-500">Name</span>
          <span class="font-medium">{{ auth.user?.full_name }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">Email</span>
          <span class="font-medium">{{ auth.user?.email }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">Role</span>
          <span class="font-medium capitalize">{{ auth.user?.role }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getSettings, updateSettings } from '@/api/settings'

const auth = useAuthStore()
const copied = ref(false)
const qrDataUrl = ref('')

// Settings state
const loadingSettings = ref(true)
const selectedLanguages = ref<string[]>(['ar', 'en'])
const telegramToken = ref('')
const savingLangs = ref(false)
const langsSaved = ref(false)
const savingTelegram = ref(false)
const telegramSaved = ref(false)

const availableLanguages = [
  { code: 'ar', label: 'Arabic', native: 'العربية' },
  { code: 'en', label: 'English', native: 'English' },
  { code: 'ru', label: 'Russian', native: 'Русский' },
]

const publicUrl = computed(() => {
  return `${window.location.origin}/q/${auth.tenantId}`
})

async function loadQr() {
  const encoded = encodeURIComponent(publicUrl.value)
  qrDataUrl.value = `https://api.qrserver.com/v1/create-qr-code/?size=128x128&data=${encoded}`
}

async function loadSettings() {
  try {
    const s = await getSettings()
    selectedLanguages.value = s.enabled_languages
    telegramToken.value = s.telegram_bot_token ?? ''
  } finally {
    loadingSettings.value = false
  }
}

onMounted(() => {
  loadQr()
  loadSettings()
})

function copyUrl() {
  navigator.clipboard.writeText(publicUrl.value)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function downloadQr() {
  const a = document.createElement('a')
  a.href = qrDataUrl.value
  a.download = 'queue-qr.png'
  a.click()
}

async function saveLanguages() {
  savingLangs.value = true
  try {
    await updateSettings({ enabled_languages: selectedLanguages.value })
    langsSaved.value = true
    setTimeout(() => { langsSaved.value = false }, 3000)
  } finally {
    savingLangs.value = false
  }
}

async function saveTelegram() {
  savingTelegram.value = true
  try {
    await updateSettings({ telegram_bot_token: telegramToken.value || null })
    telegramSaved.value = true
    setTimeout(() => { telegramSaved.value = false }, 3000)
  } finally {
    savingTelegram.value = false
  }
}
</script>
