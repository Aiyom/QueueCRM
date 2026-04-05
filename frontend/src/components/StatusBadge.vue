<template>
  <span :class="badgeClass">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const config: Record<string, { label: string; cls: string }> = {
  // Queue statuses
  waiting:    { label: 'Waiting',     cls: 'badge badge-blue' },
  called:     { label: 'Called',      cls: 'badge badge-yellow' },
  in_service: { label: 'In Service',  cls: 'badge badge-green' },
  done:       { label: 'Done',        cls: 'badge badge-gray' },
  cancelled:  { label: 'Cancelled',   cls: 'badge badge-red' },
  no_show:    { label: 'No Show',     cls: 'badge badge-red' },
  // Appointment statuses
  confirmed:  { label: 'Confirmed',   cls: 'badge badge-blue' },
}

const badgeClass = computed(() => config[props.status]?.cls ?? 'badge badge-gray')
const label = computed(() => config[props.status]?.label ?? props.status)
</script>
