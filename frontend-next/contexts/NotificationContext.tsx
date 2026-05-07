'use client'

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react'
import { useAuth } from '@/hooks/useAuth'

interface NotificationMetadata {
  expandable?: boolean
  leadsWithReplies?: Array<{
    leadId: string
    emailId?: string // ✅ NEW: For opening specific email
    companyName: string
    sentiment: 'positive' | 'negative'
    replySubject?: string
    statusChanged?: boolean
  }>
  customersWithEmails?: Array<{
    customerId: string
    emailId?: string // ✅ NEW: For opening specific email
    customerName: string
    emailSubject?: string
  }>
  newReplies?: number
  leadsQualified?: number
  emailsSynced?: number
  provider?: string
  [key: string]: any
}

interface Notification {
  id: string
  type: string
  message: string
  timestamp: Date
  read: boolean
  metadata?: NotificationMetadata
}

interface NotificationContextType {
  notifications: Notification[]
  unreadCount: number
  isOpen: boolean
  addNotification: (type: string, message: string, metadata?: NotificationMetadata) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  removeNotification: (id: string) => void
  clearAll: () => void
  togglePopup: () => void
  closePopup: () => void
}

const NotificationContext = createContext<NotificationContextType | null>(null)

const MAX_NOTIFICATIONS = 50
const MAX_AGE_DAYS = 7

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const { user } = useAuth()

  // Get user-specific storage key
  const getStorageKey = useCallback(() => {
    const userEmail = user?.email || 'anonymous'
    return `prelude_notifications_${userEmail}`
  }, [user?.email])

  // Load notifications from localStorage on mount or when user changes
  useEffect(() => {
    const loadNotifications = () => {
      try {
        // CRITICAL: Clear notifications FIRST to prevent race condition data leak
        // If we don't do this, the save effect might write old user's notifications
        // to new user's localStorage key before load effect completes
        setNotifications([])

        const storageKey = getStorageKey()
        const stored = localStorage.getItem(storageKey)
        if (stored) {
          const parsed = JSON.parse(stored)
          // Convert timestamp strings back to Date objects
          const notifications = parsed.map((n: any) => ({
            ...n,
            timestamp: new Date(n.timestamp),
          }))

          // Remove notifications older than MAX_AGE_DAYS
          const cutoffDate = new Date()
          cutoffDate.setDate(cutoffDate.getDate() - MAX_AGE_DAYS)

          const validNotifications = notifications.filter(
            (n: Notification) => n.timestamp > cutoffDate
          )

          setNotifications(validNotifications)
        }
        // No else needed - already cleared notifications above
      } catch (error) {
        console.error('Error loading notifications from localStorage:', error)
        setNotifications([]) // Ensure notifications are cleared on error
      }
    }

    loadNotifications()
  }, [getStorageKey])

  // Save notifications to localStorage whenever they change
  useEffect(() => {
    try {
      const storageKey = getStorageKey()
      localStorage.setItem(storageKey, JSON.stringify(notifications))
    } catch (error) {
      console.error('Error saving notifications to localStorage:', error)
    }
  }, [notifications, getStorageKey])

  // Calculate unread count
  const unreadCount = notifications.filter((n) => !n.read).length

  /**
   * Add a new notification
   */
  const addNotification = useCallback(
    (type: string, message: string, metadata: NotificationMetadata = {}) => {
      const now = new Date()

      setNotifications((prev) => {
        // Check for duplicate notifications within last 5 seconds (grouping)
        const recentDuplicate = prev.find(
          (n) =>
            n.type === type && n.message === message && now.getTime() - n.timestamp.getTime() < 5000 // 5 seconds
        )

        if (recentDuplicate) {
          // Update existing notification instead of creating duplicate
          return prev.map((n) =>
            n.id === recentDuplicate.id ? { ...n, timestamp: now, read: false, metadata } : n
          )
        }

        // Create new notification
        const newNotification: Notification = {
          id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          type,
          message,
          timestamp: now,
          read: false,
          metadata,
        }

        // Add to beginning of array (newest first)
        let updated = [newNotification, ...prev]

        // Enforce max notifications limit
        if (updated.length > MAX_NOTIFICATIONS) {
          updated = updated.slice(0, MAX_NOTIFICATIONS)
        }

        return updated
      })
    },
    []
  )

  /**
   * Mark a specific notification as read
   */
  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
  }, [])

  /**
   * Mark all notifications as read
   */
  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }, [])

  /**
   * Remove a specific notification
   */
  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id))
  }, [])

  /**
   * Clear all notifications
   */
  const clearAll = useCallback(() => {
    setNotifications([])
  }, [])

  /**
   * Toggle notification popup visibility
   */
  const togglePopup = useCallback(() => {
    setIsOpen((prev) => !prev)
  }, [])

  /**
   * Close notification popup
   */
  const closePopup = useCallback(() => {
    setIsOpen(false)
  }, [])

  const value: NotificationContextType = {
    notifications,
    unreadCount,
    isOpen,
    addNotification,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAll,
    togglePopup,
    closePopup,
  }

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
}

/**
 * Hook to access notification context
 */
export function useNotifications() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider')
  }
  return context
}
