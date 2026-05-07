import Cookies from 'js-cookie'
import * as Sentry from '@sentry/nextjs'
import { settingsApiClient } from '@/lib/api/client'

/**
 * Set the NEXT_LOCALE cookie used by next-intl for SSR locale resolution.
 */
export function setLocaleCookie(locale: string) {
  Cookies.set('NEXT_LOCALE', locale, { path: '/', sameSite: 'lax', expires: 365 })
}

/**
 * Get the current locale from the NEXT_LOCALE cookie.
 */
export function getLocaleCookie(): string {
  return Cookies.get('NEXT_LOCALE') || 'en'
}

/**
 * Sync locale from backend to cookie. Called on login and app init.
 * Only updates cookie on successful backend response — never overwrites on failure.
 * Returns the active locale.
 */
export async function syncLocaleFromBackend(): Promise<string> {
  try {
    const prefs = await settingsApiClient.get<{ preferredLocale: string }>('/profile/locale')
    const locale = prefs.preferredLocale || 'en'
    setLocaleCookie(locale)
    return locale
  } catch (error) {
    Sentry.captureException(error)
    // On failure, preserve existing cookie — don't overwrite with 'en'
    return getLocaleCookie()
  }
}
