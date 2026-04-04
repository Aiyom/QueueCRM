import { ar } from './ar'
import { en } from './en'
import { ru } from './ru'

export type Lang = 'ar' | 'en' | 'ru'
export const defaultLang: Lang = 'ar'
export const rtlLangs: Lang[] = ['ar']

export function getLang(url: URL): Lang {
  const [, lang] = url.pathname.split('/')
  if (lang === 'ar' || lang === 'en' || lang === 'ru') return lang
  return defaultLang
}

export function useTranslations(lang: Lang) {
  const translations = { ar, en, ru }
  return function t(key: string): string {
    return key.split('.').reduce((obj: any, k) => obj?.[k], translations[lang]) ?? key
  }
}

export type Translations = typeof ar
