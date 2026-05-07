'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { setCookie, getCookie, removeCookie } from '@/utils/cookie-manager'

interface UsePersistedStateOptions {
  expires?: number
  syncAcrossTabs?: boolean
}

/**
 * Custom hook for persisting state in cookies
 * Automatically syncs state with cookies and handles updates
 */
export const usePersistedState = <T>(
  cookieKey: string,
  defaultValue: T,
  options: UsePersistedStateOptions = {}
): [T, (value: T | ((prev: T) => T)) => void, () => void] => {
  const { expires = 365, syncAcrossTabs = true } = options

  // Initialize state from cookie or default value
  const [state, setState] = useState<T>(() => {
    const cookieValue = getCookie<T>(cookieKey)
    return cookieValue !== null ? cookieValue : defaultValue
  })

  // Track if this is the first render
  const isFirstRender = useRef(true)
  const lastCookieValue = useRef<T>(state)

  // Update cookie when state changes
  useEffect(() => {
    // Skip cookie update on first render (initial load from cookie)
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }

    // Only update cookie if value actually changed
    if (JSON.stringify(state) !== JSON.stringify(lastCookieValue.current)) {
      setCookie(cookieKey, state, { expires })
      lastCookieValue.current = state
    }
  }, [state, cookieKey, expires])

  // Sync across tabs if enabled
  useEffect(() => {
    if (!syncAcrossTabs || typeof window === 'undefined') return

    const checkForCookieChange = () => {
      const currentCookieValue = getCookie<T>(cookieKey)
      if (
        currentCookieValue !== null &&
        JSON.stringify(currentCookieValue) !== JSON.stringify(state)
      ) {
        setState(currentCookieValue)
        lastCookieValue.current = currentCookieValue
      }
    }

    // Check for changes when window regains focus
    const handleFocus = () => {
      checkForCookieChange()
    }

    // Check for changes when tab becomes visible
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        checkForCookieChange()
      }
    }

    window.addEventListener('focus', handleFocus)
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      window.removeEventListener('focus', handleFocus)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [state, cookieKey, syncAcrossTabs])

  // Enhanced setter that handles function updates
  const setValue = useCallback((newValue: T | ((prev: T) => T)) => {
    setState((prevState) => {
      const nextState =
        typeof newValue === 'function' ? (newValue as (prev: T) => T)(prevState) : newValue
      return nextState
    })
  }, [])

  // Clear the persisted value
  const clearValue = useCallback(() => {
    removeCookie(cookieKey)
    setState(defaultValue)
    lastCookieValue.current = defaultValue
  }, [cookieKey, defaultValue])

  return [state, setValue, clearValue]
}

/**
 * Hook for persisting multiple related states (like filters)
 * Stores all values in a single cookie to reduce cookie count
 */
const usePersistedStates = <T extends Record<string, any>>(
  cookieKey: string,
  defaultValues: T,
  options: UsePersistedStateOptions = {}
) => {
  const [states, setStates, clearStates] = usePersistedState(cookieKey, defaultValues, options)

  // Create individual setters for each key
  const setters: Record<keyof T, (value: T[keyof T] | ((prev: T[keyof T]) => T[keyof T])) => void> =
    {} as any

  Object.keys(defaultValues).forEach((key) => {
    setters[key as keyof T] = (value: T[keyof T] | ((prev: T[keyof T]) => T[keyof T])) => {
      setStates((prev) => ({
        ...prev,
        [key]:
          typeof value === 'function'
            ? (value as (prev: T[keyof T]) => T[keyof T])(prev[key as keyof T])
            : value,
      }))
    }
  })

  // Reset specific key to default
  const resetKey = (key: keyof T) => {
    if (key in defaultValues) {
      setStates((prev) => ({
        ...prev,
        [key]: defaultValues[key],
      }))
    }
  }

  // Reset all to defaults
  const resetAll = () => {
    setStates(defaultValues)
  }

  return {
    values: states,
    setters,
    setMultiple: (updates: Partial<T>) => setStates((prev) => ({ ...prev, ...updates })),
    resetKey,
    resetAll,
    clearAll: clearStates,
  }
}

// Specialized hooks for common use cases

/**
 * Hook specifically for table column visibility
 */
export const usePersistedColumns = (moduleId: string, defaultColumns: Record<string, boolean>) => {
  const cookieKey = `prelude_column_${moduleId}`
  return usePersistedState(cookieKey, defaultColumns, { expires: 365 })
}

/**
 * Hook specifically for filter states
 */
export const usePersistedFilters = (moduleId: string, defaultFilters: Record<string, string>) => {
  const cookieKey = `prelude_filter_${moduleId}`
  return usePersistedState(cookieKey, defaultFilters, { expires: 365 })
}

/**
 * Hook for search preferences (search term, search columns)
 */
export const usePersistedSearch = <T extends Record<string, boolean>>(
  moduleId: string,
  defaultSearch: { term: string; columns: T }
) => {
  const cookieKey = `prelude_search_${moduleId}`
  const [search, setSearch, clearSearch] = usePersistedState(cookieKey, defaultSearch, {
    expires: 30,
  })

  return {
    searchTerm: search.term,
    searchColumns: search.columns,
    setSearchTerm: (term: string) => setSearch((prev) => ({ ...prev, term })),
    setSearchColumns: (columns: T) => setSearch((prev) => ({ ...prev, columns })),
    clearSearch,
  }
}

/**
 * Hook for UI preferences (collapsed panels, view modes, etc.)
 */
export const usePersistedUIState = <T>(componentId: string, defaultState: T) => {
  const cookieKey = `prelude_ui_${componentId}`
  return usePersistedState(cookieKey, defaultState, { expires: 365 })
}

