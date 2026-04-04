<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
    <div class="w-full max-w-sm">
      <!-- Header -->
      <div class="text-center mb-8">
        <div class="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <svg class="w-9 h-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <h1 class="text-2xl font-bold text-gray-900">Join the Queue</h1>
        <p class="text-gray-500 text-sm mt-1">via WhatsApp — no app needed</p>
      </div>

      <!-- State: Not accepted yet -->
      <div class="card text-center space-y-4">
        <div class="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto">
          <svg class="w-7 h-7 text-green-600" fill="currentColor" viewBox="0 0 24 24">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/>
            <path d="M12 0C5.373 0 0 5.373 0 12c0 2.127.555 4.129 1.526 5.868L0 24l6.267-1.647A11.938 11.938 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-1.917 0-3.71-.492-5.27-1.355l-.378-.224-3.922 1.029 1.047-3.821-.248-.394A9.961 9.961 0 012 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10z"/>
          </svg>
        </div>

        <div>
          <h2 class="text-lg font-semibold text-gray-900 mb-1">Send us a WhatsApp message</h2>
          <p class="text-sm text-gray-500">Send any message to our number to start the queue process</p>
        </div>

        <a
          :href="whatsappUrl"
          target="_blank"
          rel="noopener"
          class="btn-primary w-full flex items-center justify-center gap-2 py-3"
        >
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/>
          </svg>
          Open WhatsApp
        </a>

        <div class="text-xs text-gray-400 space-y-1">
          <p>✓ No app installation required</p>
          <p>✓ Get your position and wait time instantly</p>
          <p>✓ Receive notification when it's your turn</p>
        </div>
      </div>

      <!-- Steps -->
      <div class="mt-6 space-y-3">
        <div v-for="(step, i) in steps" :key="i" class="flex items-start gap-3">
          <div class="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
            {{ i + 1 }}
          </div>
          <div>
            <p class="text-sm font-medium text-gray-900">{{ step.title }}</p>
            <p class="text-xs text-gray-500">{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

// In production, the tenant phone would be fetched via API using the slug
// For now we show instructions to send any WhatsApp message
const whatsappUrl = computed(() => {
  const text = encodeURIComponent('مرحبا')
  return `https://wa.me/?text=${text}`
})

const steps = [
  { title: 'Send a message', desc: 'Open WhatsApp and send any message to our number' },
  { title: 'Choose a service', desc: 'Reply with the number of the service you need' },
  { title: 'Wait comfortably', desc: "We'll notify you when it's almost your turn" },
]
</script>
