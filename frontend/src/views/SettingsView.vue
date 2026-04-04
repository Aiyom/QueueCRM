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

const auth = useAuthStore()
const copied = ref(false)
const qrDataUrl = ref('')

const publicUrl = computed(() => {
  return `${window.location.origin}/q/${auth.tenantId}`
})

async function loadQr() {
  // Use Google Charts QR API (no backend needed for display)
  const encoded = encodeURIComponent(publicUrl.value)
  qrDataUrl.value = `https://api.qrserver.com/v1/create-qr-code/?size=128x128&data=${encoded}`
}

onMounted(loadQr)

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
</script>
