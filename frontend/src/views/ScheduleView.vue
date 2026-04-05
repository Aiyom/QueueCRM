<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">Work Schedule</h1>

    <!-- Weekly schedule -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-4">Weekly Hours</h2>
      <div class="space-y-3">
        <div
          v-for="(day, i) in weekDays"
          :key="i"
          class="flex items-center gap-4 flex-wrap"
        >
          <div class="w-28 text-sm font-medium text-gray-700">{{ day.label }}</div>

          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              v-model="schedule[i].is_working"
              class="w-4 h-4 text-blue-600 rounded border-gray-300"
            />
            <span class="text-sm text-gray-600">Working</span>
          </label>

          <template v-if="schedule[i].is_working">
            <input
              type="time"
              v-model="schedule[i].open_time"
              class="input w-32 text-sm"
            />
            <span class="text-gray-400 text-sm">—</span>
            <input
              type="time"
              v-model="schedule[i].close_time"
              class="input w-32 text-sm"
            />
            <div class="flex items-center gap-2">
              <span class="text-sm text-gray-500">Parallel slots:</span>
              <input
                type="number"
                v-model.number="schedule[i].max_parallel"
                min="1"
                max="20"
                class="input w-16 text-sm"
              />
            </div>
          </template>
          <span v-else class="text-sm text-gray-400 italic">Day off</span>
        </div>
      </div>
      <div class="mt-4 flex items-center gap-3">
        <button @click="saveWeekly" :disabled="saving" class="btn-primary text-sm">
          {{ saving ? 'Saving...' : 'Save Schedule' }}
        </button>
        <span v-if="saved" class="text-sm text-green-600">Saved!</span>
      </div>
    </div>

    <!-- Date overrides -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-1">Date Overrides</h2>
      <p class="text-sm text-gray-500 mb-4">Close for a holiday or change hours for a specific date.</p>

      <!-- Existing overrides -->
      <div v-if="overrides.length" class="mb-4 space-y-2">
        <div
          v-for="ov in overrides"
          :key="ov.specific_date!"
          class="flex items-center gap-4 p-3 rounded-lg bg-gray-50 text-sm"
        >
          <span class="font-medium text-gray-800 w-28">{{ ov.specific_date }}</span>
          <span
            :class="ov.is_working ? 'text-green-600' : 'text-red-500'"
            class="font-medium"
          >
            {{ ov.is_working ? `${ov.open_time} — ${ov.close_time}` : 'Closed' }}
          </span>
          <span v-if="ov.notes" class="text-gray-400 flex-1">{{ ov.notes }}</span>
          <button
            @click="removeOverride(ov.specific_date!)"
            class="ml-auto text-red-500 hover:text-red-700 text-xs"
          >
            Remove
          </button>
        </div>
      </div>

      <!-- Add override form -->
      <div class="flex items-end gap-3 flex-wrap border-t border-gray-100 pt-4">
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">Date</label>
          <input type="date" v-model="newOverride.specific_date" class="input text-sm" />
        </div>
        <label class="flex items-center gap-2 self-end pb-2 cursor-pointer">
          <input type="checkbox" v-model="newOverride.is_working" class="w-4 h-4 rounded border-gray-300" />
          <span class="text-sm">Working day</span>
        </label>
        <template v-if="newOverride.is_working">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Open</label>
            <input type="time" v-model="newOverride.open_time" class="input w-32 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Close</label>
            <input type="time" v-model="newOverride.close_time" class="input w-32 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Parallel</label>
            <input type="number" v-model.number="newOverride.max_parallel" min="1" max="20" class="input w-16 text-sm" />
          </div>
        </template>
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">Note (optional)</label>
          <input type="text" v-model="newOverride.notes" placeholder="Holiday, sick day…" class="input text-sm w-40" />
        </div>
        <button @click="addOverride" :disabled="!newOverride.specific_date" class="btn-primary text-sm self-end">
          Add Override
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { appointmentsApi, type WorkScheduleItem } from '@/api/appointments'

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const weekDays = DAYS.map((label, i) => ({ label, dow: i }))

const schedule = ref<WorkScheduleItem[]>(
  DAYS.map((_, i) => ({
    day_of_week: i,
    is_working: i < 5,
    open_time: '09:00',
    close_time: '18:00',
    max_parallel: 1,
  }))
)

const overrides = ref<WorkScheduleItem[]>([])
const saving = ref(false)
const saved = ref(false)

const newOverride = ref<WorkScheduleItem & { specific_date: string }>({
  specific_date: '',
  is_working: false,
  open_time: '09:00',
  close_time: '18:00',
  max_parallel: 1,
  notes: '',
})

onMounted(async () => {
  const data = await appointmentsApi.getSchedule()
  const weekly = data.filter((d) => d.specific_date == null)
  const ovr = data.filter((d) => d.specific_date != null)

  weekly.forEach((ws) => {
    if (ws.day_of_week != null) {
      schedule.value[ws.day_of_week] = { ...ws }
    }
  })
  overrides.value = ovr
})

async function saveWeekly() {
  saving.value = true
  try {
    await appointmentsApi.saveSchedule(schedule.value)
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } finally {
    saving.value = false
  }
}

async function addOverride() {
  if (!newOverride.value.specific_date) return
  const item = await appointmentsApi.addOverride({
    specific_date: newOverride.value.specific_date,
    is_working: newOverride.value.is_working,
    open_time: newOverride.value.is_working ? newOverride.value.open_time : null,
    close_time: newOverride.value.is_working ? newOverride.value.close_time : null,
    max_parallel: newOverride.value.max_parallel,
    notes: newOverride.value.notes || null,
  })
  overrides.value = overrides.value.filter((o) => o.specific_date !== item.specific_date)
  overrides.value.push(item)
  overrides.value.sort((a, b) => (a.specific_date! > b.specific_date! ? 1 : -1))
  newOverride.value = { specific_date: '', is_working: false, open_time: '09:00', close_time: '18:00', max_parallel: 1, notes: '' }
}

async function removeOverride(date: string) {
  await appointmentsApi.deleteOverride(date)
  overrides.value = overrides.value.filter((o) => o.specific_date !== date)
}
</script>
