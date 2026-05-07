'use client'

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'
import leadsApiService from '@/lib/api/leads'
import { crmApiClient } from '@/lib/api/client'
import { useNotifications } from '@/contexts/NotificationContext'
import type { EmailSyncState } from '@/types/email/sync'

const SYNC_ERROR_STORAGE_KEY = 'prelude.syncError.v1'
const SYNC_ERRORS_ENABLED = process.env.NEXT_PUBLIC_SYNC_ERROR_TOASTS !== 'false'

const EmailSyncContext = createContext<EmailSyncState | null>(null)

export const EmailSyncProvider = ({ children }: { children: React.ReactNode }) => {
  const [emailAccounts, setEmailAccounts] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastSyncTime, setLastSyncTime] = useState<Date | null>(null)
  const [syncEnabled, setSyncEnabled] = useState(true)
  const [crmSyncEnabled, setCrmSyncEnabled] = useState(true)

  // Persistent sync error state (survives page reload via localStorage)
  const [syncError, setSyncErrorState] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null
    try {
      return localStorage.getItem(SYNC_ERROR_STORAGE_KEY)
    } catch {
      return null
    }
  })

  const setSyncError = useCallback((msg: string | null) => {
    setSyncErrorState(msg)
    try {
      if (msg) {
        localStorage.setItem(SYNC_ERROR_STORAGE_KEY, msg)
      } else {
        localStorage.removeItem(SYNC_ERROR_STORAGE_KEY)
      }
    } catch {
      // localStorage unavailable — state still held in memory
    }
  }, [])

  const clearSyncError = useCallback(() => {
    setSyncError(null)
  }, [setSyncError])

  const { addNotification } = useNotifications()

  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const crmIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const syncCallbacksRef = useRef<Array<(result: any) => void>>([])
  const crmSyncCallbacksRef = useRef<Array<(result: any) => void>>([])
  const isSyncingRef = useRef(false)
  const isCrmSyncingRef = useRef(false)
  const performSyncRef = useRef<(() => Promise<void>) | null>(null)
  const performCrmSyncRef = useRef<(() => Promise<void>) | null>(null)

  const registerSyncCallback = useCallback((callback: (result: any) => void) => {
    if (!syncCallbacksRef.current.includes(callback)) {
      syncCallbacksRef.current.push(callback)
    }
    return () => {
      syncCallbacksRef.current = syncCallbacksRef.current.filter((cb) => cb !== callback)
    }
  }, [])

  const registerCrmSyncCallback = useCallback((callback: (result: any) => void) => {
    if (!crmSyncCallbacksRef.current.includes(callback)) {
      crmSyncCallbacksRef.current.push(callback)
    }
    return () => {
      crmSyncCallbacksRef.current = crmSyncCallbacksRef.current.filter((cb) => cb !== callback)
    }
  }, [])

  const notifyCallbacks = useCallback((result: any) => {
    syncCallbacksRef.current.forEach((callback) => {
      try {
        callback(result)
      } catch (error) {
        console.error('Error in sync callback:', error)
      }
    })
  }, [])

  const notifyCrmCallbacks = useCallback((result: any) => {
    crmSyncCallbacksRef.current.forEach((callback) => {
      try {
        callback(result)
      } catch (error) {
        console.error('Error in CRM sync callback:', error)
      }
    })
  }, [])

  // Lead reply checking disabled — CRM gmail sync handles reply detection
  const performSync = useCallback(async () => {}, [])

  const performCrmSync = useCallback(async () => {
    if (isCrmSyncingRef.current) {
      return
    }

    const authProvider = localStorage.getItem('auth_provider')
    if (!authProvider || (authProvider !== 'google' && authProvider !== 'microsoft')) {
      return
    }

    const providerKey = authProvider
    const accessToken = localStorage.getItem(`${providerKey}_access_token`)
    if (!accessToken || accessToken === 'undefined' || accessToken === 'null') {
      return
    }

    isCrmSyncingRef.current = true

    try {
      const provider = authProvider === 'google' ? 'gmail' : 'outlook'
      const endpoint = provider === 'gmail' ? '/gmail/sync' : '/outlook/sync'

      // Use longer timeout (2 minutes) for CRM sync - it queries Gmail/Outlook APIs and processes emails
      const result = await crmApiClient.post(
        endpoint,
        {
          includeBody: true,
          includeSent: true,
          includeReceived: true,
        },
        { timeout: 120000 }
      )

      notifyCrmCallbacks(result)

      // Successful sync — clear any persistent error
      if (SYNC_ERRORS_ENABLED) {
        setSyncError(null)
      }

      if (result.status === 'started') {
      } else {
        const emailsSynced = result.emailsSynced || 0

        // Create notification if new emails were synced
        if (emailsSynced > 0 && result.customerEmails && result.customerEmails.length > 0) {
          const providerName = provider === 'gmail' ? 'Gmail' : 'Outlook'
          const message = `Synced ${emailsSynced} new ${emailsSynced === 1 ? 'email' : 'emails'} from ${providerName}`

          // Only show the number of emails that were actually synced (not just attempted)
          // Backend sends up to 4 preview emails, but some may be duplicates that were rejected
          const actualNewEmails = result.customerEmails.slice(0, emailsSynced)

          // Build structured customer objects array for expandable notification
          const customersWithEmails = actualNewEmails
            .filter((email: any) => email.customerId) // Only include if customerId exists
            .map((email: any) => ({
              customerId: email.customerId,
              customerName: email.customerName,
              emailSubject: email.subject,
              emailId: email.emailId,
              emailBody: email.bodySnippet || email.body_snippet,
            }))

          // Add to notification center
          addNotification('crm-sync', message, {
            emailsSynced,
            totalEmails: emailsSynced,
            provider: providerName,
            customerEmails: actualNewEmails,
            customersWithEmails,
            expandable: true,
          })
        }
      }
    } catch (error: any) {
      console.error('[CRM Sync] Error syncing emails:', error)
      if (SYNC_ERRORS_ENABLED) {
        const status = error?.status ?? error?.response?.status
        if (status === 401 || status === 403) {
          setSyncError(error?.response?.data?.detail || error?.detail || error?.message || 'auth_failed')
        }
      }
    } finally {
      isCrmSyncingRef.current = false
    }
  }, [notifyCrmCallbacks, setSyncError])

  performSyncRef.current = performSync
  performCrmSyncRef.current = performCrmSync

  useEffect(() => {
    if (!syncEnabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }

    const authProvider = localStorage.getItem('auth_provider')
    if (authProvider === 'google' || authProvider === 'microsoft') {
      setTimeout(() => {
        performSyncRef.current?.()
      }, 3000)
    }

    intervalRef.current = setInterval(() => {
      performSyncRef.current?.()
    }, 120000)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [syncEnabled])

  useEffect(() => {
    if (!crmSyncEnabled) {
      if (crmIntervalRef.current) {
        clearInterval(crmIntervalRef.current)
        crmIntervalRef.current = null
      }
      return
    }

    const authProvider = localStorage.getItem('auth_provider')
    if (authProvider === 'google' || authProvider === 'microsoft') {
      setTimeout(() => {
        performCrmSyncRef.current?.()
      }, 5000)
    }

    crmIntervalRef.current = setInterval(() => {
      performCrmSyncRef.current?.()
    }, 120000)

    return () => {
      if (crmIntervalRef.current) {
        clearInterval(crmIntervalRef.current)
        crmIntervalRef.current = null
      }
    }
  }, [crmSyncEnabled])

  // Clear syncError when the auth token changes (e.g. user reconnects their account).
  // StorageEvent only fires cross-tab; use a custom event for same-tab clears.
  useEffect(() => {
    const authKeys = ['google_access_token', 'microsoft_access_token', 'auth_provider']
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key && authKeys.includes(e.key)) clearSyncError()
    }
    const handleAuthChanged = () => clearSyncError()
    window.addEventListener('storage', handleStorageChange)
    window.addEventListener('prelude:auth-changed', handleAuthChanged)
    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('prelude:auth-changed', handleAuthChanged)
    }
  }, [clearSyncError])

  const value: EmailSyncState = {
    emailAccounts,
    isLoading,
    isSyncing,
    error,
    lastSyncTime,
    syncEnabled,
    setSyncEnabled,
    crmSyncEnabled,
    setCrmSyncEnabled,
    performSync,
    performCrmSync,
    registerSyncCallback,
    registerCrmSyncCallback,
    syncError,
    clearSyncError,
  }

  return <EmailSyncContext.Provider value={value}>{children}</EmailSyncContext.Provider>
}

export const useEmailSync = () => {
  const context = useContext(EmailSyncContext)
  if (!context) {
    throw new Error('useEmailSync must be used within EmailSyncProvider')
  }
  return context
}
