'use client'

import { useRef, useEffect } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useParams } from 'next/navigation'
import { useTranslations, useFormatter } from 'next-intl'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell, Mail, ChevronRight } from 'lucide-react'
import { useNotifications } from '@/contexts/NotificationContext'

interface NotificationRowProps {
  name: string
  subject?: string
  body?: string
  timestamp: Date
  provider?: string
  source: 'lead' | 'customer'
  sourceLabel: string
  relativeTime: string
  read: boolean
  onClick: () => void
}

/**
 * NotificationRow - Gmail-style notification with subject + body snippet
 */
function NotificationRow({
  name,
  subject,
  body,
  timestamp,
  provider,
  source,
  sourceLabel,
  relativeTime,
  read,
  onClick,
}: NotificationRowProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.15 }}
      onClick={onClick}
      className={`group relative cursor-pointer border-b border-rule p-4 transition-colors duration-150 ${read ? 'bg-bone' : 'bg-paper'} ${read ? 'hover:bg-cream' : 'hover:bg-cream'} `}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="mt-0.5 flex-shrink-0">
          <Mail className="h-4 w-4 text-mute" />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {/* Company name */}
          <p className="truncate text-sm font-semibold text-ink">{name}</p>

          {/* Subject (muted) */}
          {subject && <p className="truncate text-sm text-mute">{subject}</p>}

          {/* Body snippet (normal weight, clamped to 2 lines) */}
          {body && <p className="mt-0.5 line-clamp-2 text-sm text-ink">{body}</p>}

          {/* Meta line */}
          <p className="mt-1.5 text-xs text-mute">
            {sourceLabel} • {relativeTime}
            {provider ? ` • ${provider}` : ''}
          </p>
        </div>

        {/* Arrow */}
        <ChevronRight className="mt-0.5 h-4 w-4 flex-shrink-0 text-mute group-hover:text-ink" />

        {/* Unread indicator dot */}
        {!read && <div className="absolute top-4 right-12 h-2 w-2 rounded-full bg-deep" />}
      </div>
    </motion.div>
  )
}

/**
 * NotificationCenter - Bell button with popup notification panel
 */
export default function NotificationCenter() {
  const router = useRouter()
  const params = useParams()
  const workspaceId = params?.workspaceId as string
  const popupRef = useRef<HTMLDivElement>(null)
  const t = useTranslations('common')
  const format = useFormatter()

  const { notifications, unreadCount, isOpen, togglePopup, closePopup, markAsRead, markAllAsRead } =
    useNotifications()

  // Handle lead click
  const handleLeadClick = (leadId: string, notificationId: string) => {
    markAsRead(notificationId)
    closePopup()
    router.push(`/workspace/${workspaceId}/leads/${leadId}?tab=email`)
  }

  // Handle customer click
  const handleCustomerClick = (customerId: string, notificationId: string) => {
    markAsRead(notificationId)
    closePopup()
    router.push(`/workspace/${workspaceId}/crm/${customerId}?tab=email`)
  }

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(event.target as Node)) {
        const bellButton = (event.target as Element).closest('button[aria-label="Notifications"]')
        if (!bellButton) {
          closePopup()
        }
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [closePopup])

  // Flatten notifications into individual rows
  const notificationRows: Array<{
    id: string
    notificationId: string
    type: 'lead' | 'customer'
    name: string
    subject?: string
    body?: string
    timestamp: Date
    provider?: string
    read: boolean
    targetId: string
  }> = []

  notifications.forEach((notification) => {
    const { id, type, timestamp, read, metadata } = notification

    if (
      type === 'lead-reply' &&
      metadata?.leadsWithReplies &&
      metadata.leadsWithReplies.length > 0
    ) {
      metadata.leadsWithReplies.forEach((lead: any, index: number) => {
        notificationRows.push({
          id: `${id}-lead-${index}`,
          notificationId: id,
          type: 'lead',
          name: lead.companyName,
          subject: lead.replySubject,
          body: lead.replyBody,
          timestamp,
          provider: metadata?.provider,
          read,
          targetId: lead.leadId,
        })
      })
    } else if (
      type === 'crm-sync' &&
      metadata?.customersWithEmails &&
      metadata.customersWithEmails.length > 0
    ) {
      metadata.customersWithEmails.forEach((customer: any, index: number) => {
        notificationRows.push({
          id: `${id}-customer-${index}`,
          notificationId: id,
          type: 'customer',
          name: customer.customerName,
          subject: customer.emailSubject,
          body: customer.emailBody,
          timestamp,
          provider: metadata?.provider,
          read,
          targetId: customer.customerId,
        })
      })
    }
  })

  // Count unread rows (not grouped notifications)
  const unreadRowCount = notificationRows.filter((row) => !row.read).length
  const hasNotifications = unreadRowCount > 0

  return (
    <div className="relative">
      {/* Bell Icon Button */}
      <button
        onClick={togglePopup}
        aria-label="Notifications"
        aria-expanded={isOpen}
        className={`relative rounded-lg p-2 transition-all duration-200 ${
          hasNotifications
            ? 'text-ink hover:bg-cream'
            : 'text-mute opacity-40 hover:bg-cream'
        } ${isOpen ? 'bg-cream' : ''} `}
      >
        <Bell className="h-5 w-5" />

        {/* Badge */}
        <AnimatePresence>
          {hasNotifications && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
              className="absolute -top-1 -right-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-deep px-1"
            >
              <span className="text-[10px] leading-none font-bold text-bone">
                {unreadRowCount > 10 ? '10+' : unreadRowCount}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </button>

      {/* Popup Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            ref={popupRef}
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute left-0 z-50 mt-2 w-96 overflow-hidden rounded-xl border border-rule bg-bone shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-rule bg-paper px-4 py-3">
              <h3 className="title-block">{t('notifications.title')}</h3>
              {unreadRowCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs font-medium text-mute hover:text-ink"
                >
                  {t('notifications.markAllRead')}
                </button>
              )}
            </div>

            {/* Notifications List */}
            <div className="max-h-[400px] overflow-y-auto">
              {notificationRows.length === 0 ? (
                <div className="p-8 text-center">
                  <Bell className="mx-auto mb-2 h-8 w-8 text-mute" />
                  <p className="text-sm text-mute">{t('notifications.noNotifications')}</p>
                </div>
              ) : (
                <AnimatePresence mode="popLayout">
                  {notificationRows.map((row) => (
                    <NotificationRow
                      key={row.id}
                      name={row.name}
                      subject={row.subject}
                      body={row.body}
                      timestamp={row.timestamp}
                      provider={row.provider}
                      source={row.type}
                      sourceLabel={
                        row.type === 'lead' ? t('notifications.lead') : t('notifications.customer')
                      }
                      relativeTime={format.relativeTime(new Date(row.timestamp), new Date())}
                      read={row.read}
                      onClick={() => {
                        if (row.type === 'lead') {
                          handleLeadClick(row.targetId, row.notificationId)
                        } else {
                          handleCustomerClick(row.targetId, row.notificationId)
                        }
                      }}
                    />
                  ))}
                </AnimatePresence>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
