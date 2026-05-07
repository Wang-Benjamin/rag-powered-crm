import { getRequestConfig } from 'next-intl/server'
import { cookies, headers } from 'next/headers'
import * as Sentry from '@sentry/nextjs'
import { routing } from './routing'

const { locales, defaultLocale } = routing

function resolveLocaleFromAcceptLanguage(acceptLanguage: string | null): string | null {
  if (!acceptLanguage) return null

  const preferred = acceptLanguage
    .split(',')
    .map((part) => {
      const [lang, q] = part.trim().split(';q=')
      const quality = q ? parseFloat(q) : 1
      return { lang: lang.trim(), q: isNaN(quality) ? 1 : quality }
    })
    .sort((a, b) => b.q - a.q)

  for (const { lang } of preferred) {
    const exact = locales.find((l) => l.toLowerCase() === lang.toLowerCase())
    if (exact) return exact
    const prefix = locales.find((l) => l.toLowerCase().startsWith(lang.split('-')[0].toLowerCase()))
    if (prefix) return prefix
  }
  return null
}

async function loadNamespace(locale: string, ns: string) {
  try {
    return (await import(`../messages/${locale}/${ns}.json`)).default
  } catch (error) {
    Sentry.captureException(error, { tags: { locale, namespace: ns } })
    return {}
  }
}

function deepMerge(base: Record<string, any>, override: Record<string, any>): Record<string, any> {
  const result = { ...base }
  for (const key of Object.keys(override)) {
    if (
      override[key] &&
      typeof override[key] === 'object' &&
      !Array.isArray(override[key]) &&
      base[key] &&
      typeof base[key] === 'object' &&
      !Array.isArray(base[key])
    ) {
      result[key] = deepMerge(base[key], override[key])
    } else {
      result[key] = override[key]
    }
  }
  return result
}

const namespaces = ['common', 'navigation', 'auth', 'crm', 'leads', 'email', 'settings', 'storefront'] as const

export default getRequestConfig(async ({ requestLocale }) => {
  // Fix #3: Honor requestLocale from next-intl (e.g. getTranslations({locale: 'zh-CN'}))
  let locale = await requestLocale

  // Fall back to cookie → Accept-Language → default
  if (!locale || !locales.includes(locale as any)) {
    const cookieStore = await cookies()
    locale = cookieStore.get('NEXT_LOCALE')?.value
  }

  if (!locale || !locales.includes(locale as any)) {
    const headerStore = await headers()
    const acceptLang = headerStore.get('accept-language')
    locale = resolveLocaleFromAcceptLanguage(acceptLang) || defaultLocale
  }

  // Load all English namespaces as base
  const enModules = await Promise.all(namespaces.map((ns) => loadNamespace('en', ns)))
  const enAll: Record<string, any> = {}
  namespaces.forEach((ns, i) => {
    enAll[ns] = enModules[i]
  })

  let messages = enAll

  if (locale !== 'en') {
    const localeModules = await Promise.all(namespaces.map((ns) => loadNamespace(locale!, ns)))
    messages = {}
    namespaces.forEach((ns, i) => {
      // Fix #2: Deep merge so partially translated nested objects preserve English fallback keys
      messages[ns] = deepMerge(enAll[ns], localeModules[i])
    })
  }

  return { locale, messages }
})
