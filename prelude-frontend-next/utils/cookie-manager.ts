'use client'

import Cookies from 'js-cookie'

/**
 * Cookie Manager - Centralized cookie management for the application
 * Handles all cookie operations with proper configuration and error handling
 * Client-side only due to Next.js SSR considerations
 */

// Cookie configuration
const COOKIE_CONFIG = {
  expires: 365, // 1 year expiration for user preferences
  path: '/', // Make cookies accessible across all routes
  sameSite: 'lax' as const, // Prevents CSRF while allowing normal navigation
  secure: process.env.NODE_ENV === 'production', // Use secure cookies in production
}

// Cookie name prefixes for organization
const COOKIE_PREFIXES = {
  filter: 'prelude_filter_',
  column: 'prelude_column_',
  ui: 'prelude_ui_',
  preference: 'prelude_pref_',
} as const

/**
 * Set a cookie with proper error handling and JSON serialization
 * @param key - Cookie name
 * @param value - Value to store (will be JSON stringified)
 * @param options - Additional cookie options
 */
export const setCookie = (
  key: string,
  value: any,
  options: Cookies.CookieAttributes = {}
): boolean => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    console.warn('setCookie called on server side, skipping')
    return false
  }

  try {
    const serializedValue = JSON.stringify(value)

    // Enforce 4KB limit (4096 bytes to be safe)
    if (serializedValue.length > 4000) {
      console.error(
        `Cookie ${key} exceeds 4KB limit (${serializedValue.length} bytes). Cookie not set.`
      )
      // Try to notify user if toast is available
      if (typeof window !== 'undefined' && (window as any).showToast) {
        ;(window as any).showToast({
          title: 'Settings too large',
          description: 'Your filter settings are too complex. Please simplify them.',
          variant: 'destructive',
        })
      }
      return false
    }

    Cookies.set(key, serializedValue, { ...COOKIE_CONFIG, ...options })
    return true
  } catch (error) {
    console.error(`Failed to set cookie ${key}:`, error)
    return false
  }
}

/**
 * Get a cookie value with JSON parsing and error handling
 * @param key - Cookie name
 * @param defaultValue - Default value if cookie doesn't exist or parsing fails
 */
export const getCookie = <T = any>(key: string, defaultValue: T | null = null): T | null => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return defaultValue
  }

  try {
    const value = Cookies.get(key)
    if (value === undefined) return defaultValue
    return JSON.parse(value)
  } catch (error) {
    console.error(`Failed to get/parse cookie ${key}:`, error)
    return defaultValue
  }
}

/**
 * Remove a cookie
 * @param key - Cookie name
 * @param options - Optional cookie options (should match the options used when setting)
 */
export const removeCookie = (key: string, options: Cookies.CookieAttributes = {}): boolean => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return false
  }

  try {
    // Pass the same options (especially path and domain) that were used when setting the cookie
    Cookies.remove(key, {
      path: COOKIE_CONFIG.path,
      ...options,
    })
    return true
  } catch (error) {
    console.error(`Failed to remove cookie ${key}:`, error)
    return false
  }
}

/**
 * Clear all cookies with a specific prefix
 * @param prefix - Cookie prefix to clear
 */
const clearCookiesByPrefix = (prefix: string): void => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return
  }

  const allCookies = Cookies.get()
  Object.keys(allCookies).forEach((key) => {
    if (key.startsWith(prefix)) {
      // Use our removeCookie function which passes the correct options
      removeCookie(key)
    }
  })
}

/**
 * Get all cookies with a specific prefix
 * @param prefix - Cookie prefix to search for
 */
const getCookiesByPrefix = (prefix: string): Record<string, any> => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return {}
  }

  const allCookies = Cookies.get()
  const result: Record<string, any> = {}
  Object.keys(allCookies).forEach((key) => {
    if (key.startsWith(prefix)) {
      try {
        result[key] = JSON.parse(allCookies[key])
      } catch {
        result[key] = allCookies[key]
      }
    }
  })
  return result
}

// Module-specific cookie helpers
const filterCookies = {
  set: (module: string, filters: any) => setCookie(`${COOKIE_PREFIXES.filter}${module}`, filters),
  get: <T = any>(module: string, defaultValue: T = {} as T) =>
    getCookie(`${COOKIE_PREFIXES.filter}${module}`, defaultValue),
  remove: (module: string) => removeCookie(`${COOKIE_PREFIXES.filter}${module}`),
}

const columnCookies = {
  set: (module: string, columns: any) => setCookie(`${COOKIE_PREFIXES.column}${module}`, columns),
  get: <T = any>(module: string, defaultValue: T = {} as T) =>
    getCookie(`${COOKIE_PREFIXES.column}${module}`, defaultValue),
  remove: (module: string) => removeCookie(`${COOKIE_PREFIXES.column}${module}`),
}

const uiCookies = {
  set: (key: string, value: any) => setCookie(`${COOKIE_PREFIXES.ui}${key}`, value),
  get: <T = any>(key: string, defaultValue: T | null = null) =>
    getCookie(`${COOKIE_PREFIXES.ui}${key}`, defaultValue),
  remove: (key: string) => removeCookie(`${COOKIE_PREFIXES.ui}${key}`),
}

const preferenceCookies = {
  set: (key: string, value: any) => setCookie(`${COOKIE_PREFIXES.preference}${key}`, value),
  get: <T = any>(key: string, defaultValue: T | null = null) =>
    getCookie(`${COOKIE_PREFIXES.preference}${key}`, defaultValue),
  remove: (key: string) => removeCookie(`${COOKIE_PREFIXES.preference}${key}`),
}

// Clear all application cookies (useful for logout)
export const clearAllAppCookies = (): void => {
  Object.values(COOKIE_PREFIXES).forEach((prefix) => {
    clearCookiesByPrefix(prefix)
  })
}

const cookieManager = {
  setCookie,
  getCookie,
  removeCookie,
  clearCookiesByPrefix,
  getCookiesByPrefix,
  filterCookies,
  columnCookies,
  uiCookies,
  preferenceCookies,
  clearAllAppCookies,
}

