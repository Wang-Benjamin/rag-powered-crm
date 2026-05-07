'use client'

import React, { useState, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { useRouter } from '@/i18n/navigation'
import { useParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { useNotifications } from '@/contexts/NotificationContext'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogFooter,
} from '@/components/ui/alert-dialog'
import { toast } from 'sonner'
import { useTranslations } from 'next-intl'

import {
  RefreshCw,
  AlertCircle,
  CheckCircle,
  X,
  Mail,
  Trash2,
  Loader2,
} from 'lucide-react'
import CustomersTable from '@/components/crm/customers/CustomersTable'
import { useCRM } from '@/contexts/CRMContext'
import { crmApiClient } from '@/lib/api/client'
import type { Customer } from '@/types/crm'
import { KpiValue } from '@/components/ui/KpiValue'

const CustomerCsvUpload = dynamic(() => import('@/components/crm/import/CustomerCsvUpload'))
const MassEmailComposer = dynamic(() => import('@/components/crm/email/MassEmailComposer'))

interface WsConnection {
  // Define websocket connection properties based on your implementation
  [key: string]: any
}

interface CustomerRelationshipManagementProps {
  wsConnection?: WsConnection
}

interface EmailSyncProgress {
  status: string
  percentage: number
  complete?: boolean
  emailsSynced?: number
  totalEmails?: number
}

const CustomerRelationshipManagement: React.FC<CustomerRelationshipManagementProps> = ({
  wsConnection: _wsConnection,
}) => {
  const router = useRouter()
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  // Get data from CRM context
  const {
    customers,
    customersLoading,
    refreshCustomers,
    addCustomer,
    deleteCustomer,
    loadCustomers,
    hasInitialLoad,
    isLoadedFromCache,
  } = useCRM()

  useEffect(() => {
    loadCustomers()
  }, [loadCustomers])

  const tc = useTranslations('common')
  const t = useTranslations('crm')

  // Use faster animation when data is loaded from cache (50ms vs 300ms)
  const animationDuration = isLoadedFromCache ? 0.05 : 0.3

  // Get notification function
  const { addNotification } = useNotifications()

  // Selection state (lifted from table)
  const [selectedCustomerIds, setSelectedCustomerIds] = useState(new Set<string>())
  const [showMassEmailModal, setShowMassEmailModal] = useState(false)
  const [showMassDeleteModal, setShowMassDeleteModal] = useState(false)
  const [isDeletingMultiple, setIsDeletingMultiple] = useState(false)

  // Non-persisted UI state (modal states, temporary selections)
  const [showCsvUpload, setShowCsvUpload] = useState<boolean>(false)

  // Gmail sync state
  const [emailSyncLoading, setEmailSyncLoading] = useState<boolean>(false)
  const [emailSyncProgress, setEmailSyncProgress] = useState<EmailSyncProgress | null>(null)
  const [emailSyncError, setEmailSyncError] = useState<string | null>(null)

  // Analytics state is now managed by context

  // Handle CSV import completion
  const handleCsvImportComplete = () => {
    setShowCsvUpload(false)
    refreshCustomers()
  }

  // Handle mass delete
  const handleMassDelete = async () => {
    setIsDeletingMultiple(true)
    try {
      for (const customerId of selectedCustomerIds) {
        await deleteCustomer(customerId)
      }
      toast(t('toasts.success'), {
        description: t('toasts.customersDeleted', { count: selectedCustomerIds.size }),
      })
      setSelectedCustomerIds(new Set())
      setShowMassDeleteModal(false)
    } catch (error: any) {
      toast.error(t('toasts.error'), {
        description: error.message || t('toasts.bulkDeleteFailed'),
      })
    } finally {
      setIsDeletingMultiple(false)
    }
  }

  // Email sync function (uses current auth provider)
  const handleEmailSync = async () => {
    setEmailSyncLoading(true)
    setEmailSyncError(null)
    setEmailSyncProgress({ status: t('emailSync.startingSync'), percentage: 0 })

    try {
      const authProvider = localStorage.getItem('auth_provider')

      if (!authProvider) {
        throw new Error(t('emailSync.loginRequired'))
      }

      const providerKey = authProvider === 'google' ? 'google' : 'microsoft'
      const accessToken = localStorage.getItem(`${providerKey}_access_token`)
      const userEmail = localStorage.getItem(`${providerKey}_user_email`)

      if (!accessToken || accessToken === 'undefined' || accessToken === 'null') {
        throw new Error(
          t('emailSync.loginWithProvider', {
            provider: authProvider === 'google' ? 'Google' : 'Microsoft',
          })
        )
      }

      if (!userEmail) {
        throw new Error(t('emailSync.emailNotAvailable'))
      }

      const provider = authProvider === 'google' ? 'gmail' : 'outlook'

      setEmailSyncProgress({
        status: t('emailSync.connectingTo', {
          provider: provider === 'gmail' ? 'Gmail' : 'Outlook',
        }),
        percentage: 25,
      })

      const idToken = localStorage.getItem('id_token')
      const syncEndpoint = provider === 'gmail' ? 'gmail/sync' : 'outlook/sync'

      if (!idToken) {
        const hasGoogleToken = !!localStorage.getItem('google_access_token')
        const hasOutlookToken = !!localStorage.getItem('outlook_access_token')

        if (hasGoogleToken || hasOutlookToken) {
          throw new Error(t('emailSync.connectedButNotLoggedIn'))
        } else {
          throw new Error(t('emailSync.notAuthenticated'))
        }
      }

      setEmailSyncProgress({ status: t('emailSync.syncingEmails'), percentage: 50 })

      const data = await crmApiClient.post(`/${syncEndpoint}`, {
        accessToken: accessToken,
        includeBody: true,
        includeSent: true,
        includeReceived: true,
      })

      if (data) {
        // Individual sync completes immediately (no job monitoring needed)
        setEmailSyncProgress({
          status: t('emailSync.syncSuccess', { count: data.emailsSynced || 0 }),
          percentage: 100,
          complete: true,
          emailsSynced: data.emailsSynced || 0,
          totalEmails: data.totalEmailsSynced || 0,
        })

        // Show success notification
        toast(t('emailSync.syncCompleteTitle'), {
          description: t('emailSync.syncCompleteDescription', { count: data.emailsSynced || 0 }),
        })

        // Add to notification center if new emails were synced
        if (data.emailsSynced > 0) {
          const providerName = provider === 'gmail' ? 'Gmail' : 'Outlook'

          // Only show the number of emails that were actually synced (not just attempted)
          // Backend sends up to 4 preview emails, but some may be duplicates that were rejected
          const allCustomerEmails = data.customerEmails || []
          const customerEmails = allCustomerEmails.slice(0, data.emailsSynced)

          // Build enriched notification message (matching lead_gen format)
          let message = t('emailSync.notificationMessage', {
            provider: providerName,
            count: data.emailsSynced,
          })

          // Add customer emails with subjects (like positive emails in lead_gen)
          if (customerEmails.length > 0) {
            const emailsWithSubjects = customerEmails
              .map((email: any) => `${email.customerName} '${email.subject}'`)
              .join(', ')
            message += `\n• ${emailsWithSubjects}`
          }

          // Build structured customer objects array for expandable notification
          const customersWithEmails = customerEmails
            .filter((email: any) => email.customerId) // Only include if customerId exists
            .map((email: any) => ({
              customerId: email.customerId,
              customerName: email.customerName,
              emailSubject: email.subject,
              emailId: email.emailId,
              emailBody: email.bodySnippet || email.body_snippet,
            }))

          addNotification('crm-sync', message, {
            emailsSynced: data.emailsSynced,
            totalEmails: data.totalEmailsSynced,
            provider: providerName,
            customerEmails,
            customersWithEmails,
            expandable: true,
          })
        }

        // Clear progress state after a short delay
        setTimeout(() => {
          setEmailSyncProgress(null)
        }, 3000)
      }
    } catch (err: any) {
      // Handle API errors - ApiClient throws ApiClientError with status and data
      let errorMessage = err.message || t('emailSync.syncFailed')

      if (err.status === 404) {
        errorMessage = t('emailSync.serviceNotAvailable')
      } else if (err.status === 401) {
        // Check if it's a Gmail token expiration
        if (err.data?.detail?.includes('Gmail access token expired')) {
          errorMessage = t('emailSync.gmailTokenExpired')
        } else if (err.data?.detail && err.data.detail !== 'Not authenticated') {
          errorMessage = err.data.detail
        } else {
          const hasIdToken = !!localStorage.getItem('id_token')
          const hasEmailToken =
            !!localStorage.getItem('google_access_token') ||
            !!localStorage.getItem('outlook_access_token')

          if (!hasIdToken && hasEmailToken) {
            errorMessage = t('emailSync.loginToPreludeFirst')
          } else if (!hasIdToken) {
            errorMessage = t('emailSync.sessionExpired')
          } else {
            errorMessage = t('emailSync.emailAccessExpired')
          }
        }
      } else if (err.status === 500) {
        errorMessage = t('emailSync.serverError')
      }
      setEmailSyncError(errorMessage)
      setEmailSyncProgress(null)
    } finally {
      setEmailSyncLoading(false)
      // Clear progress after 3 seconds if there was an error
      if (emailSyncError) {
        setTimeout(() => setEmailSyncProgress(null), 3000)
      }
    }
  }

  // Customer Management Tab Content
  const renderCustomerManagementTab = () => {
    return (
      <div className="flex flex-col">
        {/* Email Sync Progress */}
        {emailSyncProgress && (
          <div
            className={`mb-3 rounded-lg border p-4 ${
              emailSyncProgress.complete
                ? 'border-accent/30 bg-accent-lo'
                : 'border-info/30 bg-info-lo'
            }`}
          >
            <div className="mb-2 flex items-center gap-2">
              {emailSyncProgress.complete ? (
                <CheckCircle className="h-5 w-5 text-accent" />
              ) : (
                <RefreshCw className="h-5 w-5 animate-spin text-info" />
              )}
              <span
                className={`text-sm font-medium ${
                  emailSyncProgress.complete ? 'text-accent' : 'text-info'
                }`}
              >
                {emailSyncProgress.status}
              </span>
            </div>
            {!emailSyncProgress.complete && (
              <div className="h-2 w-full rounded-full bg-rule">
                <div
                  className="h-2 rounded-full bg-info transition-all duration-500"
                  style={{ width: `${emailSyncProgress.percentage}%` }}
                />
              </div>
            )}
            {emailSyncProgress.complete && emailSyncProgress.emailsSynced !== undefined && (
              <div className="mt-2 text-sm text-accent">
                {t('emailSync.syncedSummary', {
                  synced: emailSyncProgress.emailsSynced,
                  total: emailSyncProgress.totalEmails || 0,
                })}
              </div>
            )}
          </div>
        )}

        {/* Email Sync Error */}
        {emailSyncError && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-threat/30 bg-threat-lo p-3 text-threat">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">{emailSyncError}</span>
            <button
              onClick={() => setEmailSyncError(null)}
              className="ml-auto text-threat hover:opacity-70"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* KPI Strip */}
        {customers.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-4">
            {(() => {
              const now = new Date()
              const daysSince = (dateStr: string | null | undefined) => {
                if (!dateStr) return Infinity
                return Math.floor((now.getTime() - new Date(dateStr).getTime()) / 86400000)
              }
              const hotCount = customers.filter((c) => c.signal?.level === 'red').length
              const engagedCount = customers.filter((c) => c.signal?.level === 'green').length
              const staleCount = customers.filter((c) => daysSince(c.lastActivity) > 30).length
              const kpiCards = [
                {
                  label: t('kpi.total'),
                  value: customers.length,
                  color: 'text-deep',
                  subtitle: t('kpi.totalSubtitle'),
                },
                {
                  label: t('kpi.hot'),
                  value: hotCount,
                  color: hotCount > 0 ? 'text-threat' : 'text-deep',
                  subtitle: t('kpi.hotSubtitle'),
                },
                {
                  label: t('kpi.engaged'),
                  value: engagedCount,
                  color: engagedCount > 0 ? 'text-accent' : 'text-deep',
                  subtitle: t('kpi.engagedSubtitle'),
                },
                {
                  label: t('kpi.stale'),
                  value: staleCount,
                  color: staleCount > 0 ? 'text-gold' : 'text-deep',
                  subtitle: t('kpi.staleSubtitle'),
                },
              ]
              return kpiCards.map((card) => (
                <div
                  key={card.label}
                  className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5"
                >
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                    {card.label}
                  </span>
                  <KpiValue className={card.color}>
                    {card.value.toLocaleString()}
                  </KpiValue>
                  <span className="text-[12px] leading-[1.35] text-mute">{card.subtitle}</span>
                </div>
              ))
            })()}
          </div>
        )}

        {/* Editable Customer Table */}
        <CustomersTable
          onSyncEmails={handleEmailSync}
          isSyncingEmails={emailSyncLoading}
          onCsvUpload={() => setShowCsvUpload(true)}
          selectedCustomerIds={selectedCustomerIds}
          onSelectionChange={setSelectedCustomerIds}
        />
      </div>
    )
  }

  // Show loading only on initial load (before any data has been loaded)
  // Use hasInitialLoad flag to prevent showing loading screen when navigating back to CRM with cached data
  const loading = customersLoading && !hasInitialLoad

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-1/3 rounded bg-paper"></div>
          <div className="grid grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 rounded bg-paper"></div>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-80 rounded bg-paper"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Main Content — page-level scroll lives on this single overflow-y-auto
          container so everything scrolls as one document while the sidebar
          stays fixed. */}
      <div className="flex-1 overflow-y-auto bg-paper p-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: animationDuration }}
        >
          {renderCustomerManagementTab()}
        </motion.div>
      </div>

      {/* CSV Upload Modal */}
      {showCsvUpload && (
        <CustomerCsvUpload
          onImportComplete={handleCsvImportComplete}
          onClose={() => setShowCsvUpload(false)}
        />
      )}

      {/* Mass Email Modal */}
      {showMassEmailModal && (
        <MassEmailComposer
          selectedClientIds={Array.from(selectedCustomerIds)}
          onClose={() => setShowMassEmailModal(false)}
          onEmailsSent={() => {
            loadCustomers()
            setSelectedCustomerIds(new Set())
            setShowMassEmailModal(false)
          }}
        />
      )}

      {/* Mass Delete Confirmation Modal */}
      <AlertDialog open={showMassDeleteModal} onOpenChange={setShowMassDeleteModal}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-threat-lo">
                <Trash2 className="h-6 w-6 text-threat" />
              </div>
              <div>
                <AlertDialogTitle className="title-page">{t('customerList.bulkDeleteConfirm')}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t('customerList.bulkDeleteDescription')}
                </AlertDialogDescription>
              </div>
            </div>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeletingMultiple}>{tc('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleMassDelete}
              disabled={isDeletingMultiple}
              className="bg-threat text-bone hover:bg-threat/90"
            >
              {isDeletingMultiple ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('customerManagement.deleting')}
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 h-4 w-4" />
                  {tc('delete')}
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Floating Selection Actions Bar */}
      {selectedCustomerIds.size > 0 && !showMassEmailModal && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 transform">
          <div className="flex flex-nowrap items-center gap-3 rounded-lg border border-rule bg-bone px-6 py-3 whitespace-nowrap shadow-xl">
            <span className="text-sm font-medium text-ink">
              {tc('selected', { count: selectedCustomerIds.size })}
            </span>
            <button
              onClick={() => setShowMassEmailModal(true)}
              className="inline-flex items-center justify-center rounded-lg bg-deep px-4 py-2 text-sm font-medium text-bone transition-all duration-200 hover:bg-ink active:scale-95"
            >
              <Mail className="mr-2 h-4 w-4" />
              {tc('massEmail')}
            </button>
            <button
              onClick={() => setShowMassDeleteModal(true)}
              className="inline-flex items-center justify-center rounded-lg bg-threat px-4 py-2 text-sm font-medium text-bone transition-all duration-200 hover:bg-threat/90 active:scale-95"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {tc('deleteSelected')} ({selectedCustomerIds.size})
            </button>
            <button
              onClick={() => setSelectedCustomerIds(new Set())}
              className="rounded-lg px-3 py-2 text-sm font-medium text-mute transition-colors hover:bg-cream hover:text-deep"
            >
              {tc('clear')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default CustomerRelationshipManagement
