# Keep-alive для Render Free Tier

Бесплатный план Render засыпает через 15 минут неактивности.
Первый запрос после сна занимает ~30 секунд — плохо для демо.

## Решение: cron-job.org (бесплатно, без карты)

1. Открой https://cron-job.org
2. Sign up (бесплатно)
3. Dashboard → Create cronjob
4. Настройки:
   - Title: QueueCRM Keep-Alive
   - URL: https://qcrm-backend.onrender.com/health
   - Schedule: Every 10 minutes
5. Save

Бэкенд будет отвечать на /health и не засыпать во время демо.
