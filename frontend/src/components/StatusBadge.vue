<template>
  <span :class="badgeClass">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { QueueStatus } from '@/api/queue'

const props = defineProps<{ status: QueueStatus }>()

const config: Record<QueueStatus, { label: string; cls: string }> = {
  waiting:    { label: 'Waiting',     cls: 'badge badge-blue' },
  called:     { label: 'Called',      cls: 'badge badge-yellow' },
  in_service: { label: 'In Service',  cls: 'badge badge-green' },
  done:       { label: 'Done',        cls: 'badge badge-gray' },
  cancelled:  { label: 'Cancelled',   cls: 'badge badge-red' },
  no_show:    { label: 'No Show',     cls: 'badge badge-red' },
}

const badgeClass = computed(() => config[props.status]?.cls ?? 'badge badge-gray')
const label = computed(() => config[props.status]?.label ?? props.status)
</script>
