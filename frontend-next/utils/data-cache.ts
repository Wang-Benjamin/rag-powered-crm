'use client'

/**
 * Data Cache Manager
 * Provides localStorage-based caching for API data with TTL support
 * Client-side only due to Next.js SSR considerations
 */

const CACHE_PREFIX = 'prelude_data_cache_'
const DEFAULT_TTL = 30 * 60 * 1000 // 30 minutes

interface CacheEntry {
  data: any
  timestamp: number
}

interface CacheInfo {
  count: number
  totalSize: number
  entries: Array<{
    key: string
    size: number
    age: number
    timestamp: number
  }>
}

/**
 * Get cached data from localStorage
 * @param key - Cache key
 * @param ttl - Time to live in milliseconds (default: 30 minutes)
 * @param userEmail - Optional user email for user-specific caching
 * @returns Cached data or null if expired/not found
 */
export const getCachedData = <T = any>(
  key: string,
  ttl: number = DEFAULT_TTL,
  userEmail: string | null = null
): T | null => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const cacheKey = userEmail ? `${CACHE_PREFIX}${key}_${userEmail}` : `${CACHE_PREFIX}${key}`
    const cached = localStorage.getItem(cacheKey)

    if (!cached) {
      return null
    }

    const { data, timestamp }: CacheEntry = JSON.parse(cached)
    const now = Date.now()

    // Check if cache is still valid
    if (now - timestamp > ttl) {
      localStorage.removeItem(cacheKey)
      return null
    }

    return data
  } catch (error) {
    console.error(`[Cache] Error reading ${key}:`, error)
    return null
  }
}

/**
 * Get cached data with timestamp from localStorage
 * @param key - Cache key
 * @param ttl - Time to live in milliseconds (default: 30 minutes)
 * @param userEmail - Optional user email for user-specific caching
 * @returns Object with data and timestamp, or null if expired/not found
 */
export const getCachedDataWithTimestamp = <T = any>(
  key: string,
  ttl: number = DEFAULT_TTL,
  userEmail: string | null = null
): { data: T; timestamp: number } | null => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const cacheKey = userEmail ? `${CACHE_PREFIX}${key}_${userEmail}` : `${CACHE_PREFIX}${key}`
    const cached = localStorage.getItem(cacheKey)

    if (!cached) {
      return null
    }

    const { data, timestamp }: CacheEntry = JSON.parse(cached)
    const now = Date.now()

    // Check if cache is still valid
    if (now - timestamp > ttl) {
      localStorage.removeItem(cacheKey)
      return null
    }

    return { data, timestamp }
  } catch (error) {
    console.error(`[Cache] Error reading ${key}:`, error)
    return null
  }
}

/**
 * Set cached data in localStorage
 * @param key - Cache key
 * @param data - Data to cache
 * @param userEmail - Optional user email for user-specific caching
 */
export const setCachedData = (key: string, data: any, userEmail: string | null = null): void => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return
  }

  try {
    const cacheKey = userEmail ? `${CACHE_PREFIX}${key}_${userEmail}` : `${CACHE_PREFIX}${key}`
    const cacheEntry: CacheEntry = {
      data,
      timestamp: Date.now(),
    }

    localStorage.setItem(cacheKey, JSON.stringify(cacheEntry))
  } catch (error) {
    console.error(`[Cache] Error writing ${key}:`, error)
    // If localStorage is full, clear old cache entries
    if (error instanceof Error && error.name === 'QuotaExceededError') {
      clearOldCache()
      // Try again
      try {
        const cacheKey = userEmail ? `${CACHE_PREFIX}${key}_${userEmail}` : `${CACHE_PREFIX}${key}`
        localStorage.setItem(cacheKey, JSON.stringify({ data, timestamp: Date.now() }))
      } catch (retryError) {
        console.error(`[Cache] Failed to write even after clearing:`, retryError)
      }
    }
  }
}

/**
 * Clear cache for a specific key
 * @param key - Cache key
 * @param userEmail - Optional user email for user-specific caching
 */
export const clearCachedData = (key: string, userEmail: string | null = null): void => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return
  }

  try {
    const cacheKey = userEmail ? `${CACHE_PREFIX}${key}_${userEmail}` : `${CACHE_PREFIX}${key}`
    localStorage.removeItem(cacheKey)
  } catch (error) {
    console.error(`[Cache] Error clearing ${key}:`, error)
  }
}

/**
 * Clear all cache entries
 */
const clearAllCache = (): void => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return
  }

  try {
    const keys = Object.keys(localStorage)
    keys.forEach((key) => {
      if (key.startsWith(CACHE_PREFIX)) {
        localStorage.removeItem(key)
      }
    })
  } catch (error) {
    console.error('[Cache] Error clearing all cache:', error)
  }
}

/**
 * Clear cache entries older than specified age
 * @param maxAge - Maximum age in milliseconds (default: 24 hours)
 */
const clearOldCache = (maxAge: number = 24 * 60 * 60 * 1000): void => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return
  }

  try {
    const keys = Object.keys(localStorage)
    const now = Date.now()
    let clearedCount = 0

    keys.forEach((key) => {
      if (key.startsWith(CACHE_PREFIX)) {
        try {
          const cached = localStorage.getItem(key)
          if (cached) {
            const { timestamp }: CacheEntry = JSON.parse(cached)

            if (now - timestamp > maxAge) {
              localStorage.removeItem(key)
              clearedCount++
            }
          }
        } catch (error) {
          // Invalid cache entry, remove it
          localStorage.removeItem(key)
          clearedCount++
        }
      }
    })
  } catch (error) {
    console.error('[Cache] Error clearing old cache:', error)
  }
}

/**
 * Get cache info (size, count, etc.)
 */
const getCacheInfo = (): CacheInfo => {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return { count: 0, totalSize: 0, entries: [] }
  }

  try {
    const keys = Object.keys(localStorage)
    const cacheKeys = keys.filter((key) => key.startsWith(CACHE_PREFIX))

    let totalSize = 0
    const entries: CacheInfo['entries'] = []

    cacheKeys.forEach((key) => {
      try {
        const value = localStorage.getItem(key)
        if (value) {
          const size = new Blob([value]).size
          totalSize += size

          const { timestamp }: CacheEntry = JSON.parse(value)
          const age = Date.now() - timestamp

          entries.push({
            key: key.replace(CACHE_PREFIX, ''),
            size,
            age: Math.round(age / 1000), // in seconds
            timestamp,
          })
        }
      } catch (error) {
        // Ignore invalid entries
      }
    })

    return {
      count: entries.length,
      totalSize,
      entries: entries.sort((a, b) => b.size - a.size), // Sort by size descending
    }
  } catch (error) {
    console.error('[Cache] Error getting cache info:', error)
    return { count: 0, totalSize: 0, entries: [] }
  }
}

// Initialize cache cleanup on module load (only in browser)
if (typeof window !== 'undefined') {
  clearOldCache()
}

const dataCache = {
  get: getCachedData,
  set: setCachedData,
  clear: clearCachedData,
  clearAll: clearAllCache,
  clearOld: clearOldCache,
  info: getCacheInfo,
}

