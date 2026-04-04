import { useI18n } from 'vue-i18n'

export function useFormatters() {
  const { locale } = useI18n()

  function formatDate(date: string | Date): string {
    return new Intl.DateTimeFormat(locale.value === 'ru' ? 'ru-RU' : 'en-US', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(new Date(date))
  }

  function formatMoney(amount: number): string {
    return new Intl.NumberFormat(locale.value === 'ru' ? 'ru-RU' : 'en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(amount)
  }

  return { formatDate, formatMoney }
}
