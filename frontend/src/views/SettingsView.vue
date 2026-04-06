<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">Settings</h1>

    <!-- QR Code -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-4">Public Queue Page</h2>
      <p class="text-sm text-gray-500 mb-4">
        Share this link or QR code with customers to join the queue via WhatsApp or Telegram.
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

    <!-- WhatsApp (360dialog) -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-1">WhatsApp (360dialog)</h2>
      <p class="text-sm text-gray-500 mb-4">Enter your 360dialog API key and Channel ID to enable WhatsApp bot.</p>
      <div v-if="loadingSettings" class="text-sm text-gray-400">Loading...</div>
      <div v-else class="space-y-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">API Key</label>
          <input v-model="d360ApiKey" type="password" placeholder="d360-api-key..." class="input w-full" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Channel ID</label>
          <input v-model="d360ChannelId" type="text" placeholder="channel_id..." class="input w-full" />
        </div>
        <div class="flex items-center gap-3">
          <button @click="saveWhatsApp" :disabled="savingWhatsApp" class="btn-primary text-sm">
            {{ savingWhatsApp ? 'Saving...' : 'Save WhatsApp' }}
          </button>
          <span v-if="whatsappSaved" class="text-sm text-green-600">Saved!</span>
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
        <div class="flex items-center gap-3 flex-wrap">
          <button
            @click="saveTelegram"
            :disabled="savingTelegram"
            class="btn-primary text-sm"
          >
            {{ savingTelegram ? 'Saving...' : 'Save Token' }}
          </button>
          <button
            v-if="telegramToken"
            @click="registerWebhook"
            :disabled="registeringWebhook"
            class="btn-secondary text-sm"
          >
            {{ registeringWebhook ? 'Registering...' : 'Register Webhook' }}
          </button>
          <span v-if="telegramSaved" class="text-sm text-green-600">Saved!</span>
          <span v-if="webhookRegistered" class="text-sm text-green-600">Webhook registered!</span>
          <span v-if="webhookError" class="text-sm text-red-500">{{ webhookError }}</span>
        </div>
      </div>
    </div>

    <!-- Manager notifications -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-1">Manager Notifications</h2>
      <p class="text-sm text-gray-500 mb-4">
        Receive booking and cancellation alerts via Telegram. Send <code class="bg-gray-100 px-1 rounded">/myid</code> to your bot to get your Chat ID.
      </p>
      <div v-if="loadingSettings" class="text-sm text-gray-400">Loading...</div>
      <div v-else class="space-y-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Manager Telegram Chat ID</label>
          <input
            v-model="managerChatId"
            type="text"
            placeholder="e.g. 123456789"
            class="input w-full"
          />
          <p class="text-xs text-gray-400 mt-1">
            Leave empty to disable. Notifications will fall back to WhatsApp (your business phone) if not set.
          </p>
        </div>
        <div class="flex items-center gap-3">
          <button @click="saveManagerNotif" :disabled="savingManagerNotif" class="btn-primary text-sm">
            {{ savingManagerNotif ? 'Saving...' : 'Save' }}
          </button>
          <span v-if="managerNotifSaved" class="text-sm text-green-600">Saved!</span>
        </div>
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
import api from '@/api/axios'

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
const registeringWebhook = ref(false)
const webhookRegistered = ref(false)
const webhookError = ref('')
const d360ApiKey = ref('')
const d360ChannelId = ref('')
const savingWhatsApp = ref(false)
const whatsappSaved = ref(false)
const managerChatId = ref('')
const savingManagerNotif = ref(false)
const managerNotifSaved = ref(false)

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
    d360ApiKey.value = s.d360_api_key ?? ''
    d360ChannelId.value = s.d360_channel_id ?? ''
    managerChatId.value = s.manager_telegram_chat_id ?? ''
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

async function saveWhatsApp() {
  savingWhatsApp.value = true
  try {
    await updateSettings({
      d360_api_key: d360ApiKey.value || null,
      d360_channel_id: d360ChannelId.value || null,
    })
    whatsappSaved.value = true
    setTimeout(() => { whatsappSaved.value = false }, 3000)
  } finally {
    savingWhatsApp.value = false
  }
}

async function saveManagerNotif() {
  savingManagerNotif.value = true
  try {
    await updateSettings({ manager_telegram_chat_id: managerChatId.value || null })
    managerNotifSaved.value = true
    setTimeout(() => { managerNotifSaved.value = false }, 3000)
  } finally {
    savingManagerNotif.value = false
  }
}

async function registerWebhook() {
  registeringWebhook.value = true
  webhookError.value = ''
  try {
    await api.post('/telegram/setup-webhook')
    webhookRegistered.value = true
    setTimeout(() => { webhookRegistered.value = false }, 4000)
  } catch (e: any) {
    webhookError.value = e?.response?.data?.detail || 'Failed to register webhook'
    setTimeout(() => { webhookError.value = '' }, 5000)
  } finally {
    registeringWebhook.value = false
  }
}
</script>
