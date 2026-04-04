<template>
  <div class="flex gap-1">
    <button
      v-for="lang in ['en', 'ru']"
      :key="lang"
      @click="setLocale(lang)"
      :class="[
        'px-2.5 py-1 text-xs rounded border transition',
        locale === lang
          ? 'border-indigo-300 text-indigo-100 font-medium opacity-100'
          : 'border-indigo-600 text-indigo-400 opacity-60 hover:opacity-90'
      ]"
    >
      {{ lang.toUpperCase() }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()

function setLocale(lang: string) {
  locale.value = lang
  localStorage.setItem('sa_locale', lang)
}
</script>
