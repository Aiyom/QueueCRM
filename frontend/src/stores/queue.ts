import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'
import type { QueueEntry } from '@/api/queue'

export const useQueueStore = defineStore('queue', () => {
  const entries = ref<QueueEntry[]>([])
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)

  function connect(tenantId: string) {
    if (ws.value?.readyState === WebSocket.OPEN) return

    const auth = useAuthStore()
    const token = auth.accessToken
    const wsBase = import.meta.env.VITE_WS_URL
      || (location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host
    const url = `${wsBase}/api/v1/queue/ws/${tenantId}?token=${token}`

    const socket = new WebSocket(url)

    socket.onopen = () => {
      connected.value = true
      // Keepalive ping every 25s
      const ping = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send('ping')
        else clearInterval(ping)
      }, 25_000)
    }

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.event === 'queue_updated' && msg.queue) {
          entries.value = msg.queue
        }
      } catch {}
    }

    socket.onclose = () => {
      connected.value = false
      // Reconnect after 3s
      setTimeout(() => connect(tenantId), 3_000)
    }

    ws.value = socket
  }

  function disconnect() {
    ws.value?.close()
    ws.value = null
    connected.value = false
  }

  return { entries, connected, connect, disconnect }
})
