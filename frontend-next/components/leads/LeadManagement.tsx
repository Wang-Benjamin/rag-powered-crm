'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { useLeadContext } from '@/contexts/LeadContext'
import type { Lead } from '@/types/leads'

import { Trash2, Loader2, Mail, Clock } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
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
import leadsApiService from '@/lib/api/leads'
import MassEmailComposer from './email/MassEmailComposer'
import ScheduledEmailsModal from '@/components/email/shared/ScheduledEmailsModal'
import LeadsTable from './tables/LeadsTable'
import MetricsCards from './MetricsCards'

const LeadManagement: React.FC = () => {
  const router = useRouter()
  const params = useParams()
  const workspaceId = (params?.workspaceId as string) || ''
  const t = useTranslations('leads')
  const tc = useTranslations('common')

  // Use Lead Context
  const { leads, workflowLeads, isLoading, loadLeads, removeLeadFromState } = useLeadContext()

  useEffect(() => {
    loadLeads()
  }, [loadLeads])

  // Modal and selection states
  const [showMassDeleteModal, setShowMassDeleteModal] = useState<boolean>(false)
  const [isDeletingMultiple, setIsDeletingMultiple] = useState<boolean>(false)
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<string | number>>(new Set())
  const [showMassEmailComposer, setShowMassEmailComposer] = useState<boolean>(false)
  const [showScheduledEmailsModal, setShowScheduledEmailsModal] = useState(false)
  const [showAddLeadModal, setShowAddLeadModal] = useState<boolean>(false)
  const [isAddingLead, setIsAddingLead] = useState<boolean>(false)
  const [newLeadData, setNewLeadData] = useState<Record<string, any>>({
    company: '',
    location: '',
    industry: '',
    contactEmail: '',
    contactPhone: '',
    website: '',
    status: 'new',
  })

  // Handle lead click - navigate to detail page
  const handleLeadClick = (lead: Lead) => {
    const leadId = lead.leadId || lead.id
    router.push(`/workspace/${workspaceId}/leads/${leadId}`)
  }

  // Handle refresh
  const handleRefresh = async () => {
    try {
      await loadLeads(true) // Force refresh
      toast(tc('success'), { description: t('toasts.refreshed') })
    } catch (error: any) {
      toast.error(tc('error'), { description: t('leadManagement.refreshFailed', { error: error.message }) })
    }
  }

  // Handle CSV export
  const handleExportCSV = async () => {
    try {
      toast(t('leadManagement.exportingCsv'))
      const csvContent = await leadsApiService.exportLeadsCSV({})

      // Create download link
      const blob = new Blob([csvContent], { type: 'text/csv' })
      const link = document.createElement('a')
      const url = URL.createObjectURL(blob)

      // Generate filename with timestamp
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)
      link.href = url
      link.download = `leads_export_${timestamp}.csv`

      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)

      toast(tc('success'), { description: t('leadManagement.csvExported') })
    } catch (error: any) {
      console.error('Export failed:', error)
      toast.error(tc('error'), { description: t('leadManagement.csvExportFailed', { error: error.message }) })
    }
  }

  // Handle mass delete
  const handleMassDelete = async () => {
    const leadIdsArray = Array.from(selectedLeadIds)
    setIsDeletingMultiple(true)

    try {
      await Promise.all(leadIdsArray.map((id) => leadsApiService.deleteLead(String(id))))

      leadIdsArray.forEach((id) => removeLeadFromState(Number(id)))
      setSelectedLeadIds(new Set())
      setShowMassDeleteModal(false)

      toast(tc('success'), { description: t('leadManagement.leadsDeleted', { count: leadIdsArray.length }) })
    } catch (error: any) {
      toast.error(tc('error'), { description: t('leadManagement.deleteFailed', { error: error.message }) })
    } finally {
      setIsDeletingMultiple(false)
    }
  }

  // Handle add new lead
  const handleAddLead = async () => {
    try {
      setIsAddingLead(true)
      const { contactEmail, contactPhone, ...leadFields } = newLeadData
      const payload: Record<string, any> = { ...leadFields }
      if (contactEmail || contactPhone) {
        payload.personnel = [
          {
            firstName: 'Unknown',
            lastName: '',
            email: contactEmail,
            phone: contactPhone,
            source: 'manual',
          },
        ]
      }
      const result = await leadsApiService.createLead(payload as Lead)
      toast(tc('success'), { description: t('leadManagement.leadAdded') })
      setShowAddLeadModal(false)
      setNewLeadData({
        company: '',
        location: '',
        industry: '',
        contactEmail: '',
        contactPhone: '',
        website: '',
        status: 'new',
      })
      await loadLeads(true)
    } catch (error: any) {
      toast.error(tc('error'), { description: t('leadManagement.addLeadFailed', { error: error.message }) })
    } finally {
      setIsAddingLead(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Main Content — page-level scroll lives on this single overflow-y-auto
          container so the KPI strip + toolbar + table all scroll as one
          document while the sidebar (outside this tree) stays fixed. */}
      <div className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto bg-paper px-6 pt-6 pb-5">
          <MetricsCards />
          <LeadsTable
            onLeadClick={handleLeadClick}
            selectedLeadIds={selectedLeadIds}
            onSelectionChange={setSelectedLeadIds}
            onAddLead={() => setShowAddLeadModal(true)}
            onExportCsv={handleExportCSV}
            onRefresh={handleRefresh}
            isRefreshing={isLoading}
          />
        </div>
      </div>

      {/* Mass Email Composer Modal */}
      {showMassEmailComposer && (
        <MassEmailComposer
          selectedLeadIds={Array.from(selectedLeadIds).map((id) => String(id))}
          allLeads={[...leads, ...workflowLeads] as any}
          onClose={() => {
            setShowMassEmailComposer(false)
            setSelectedLeadIds(new Set())
          }}
          onEmailsSent={(result: any) => {
            loadLeads(true)
            setSelectedLeadIds(new Set())
            if (result?.campaignId) {
              router.push(`/workspace/${workspaceId}/leads/campaigns/${result.campaignId}`)
            }
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
                <AlertDialogTitle className="title-page">
                  {t('leadManagement.deleteTitle', { count: selectedLeadIds.size })}
                </AlertDialogTitle>
                <AlertDialogDescription>{tc('cannotUndo')}</AlertDialogDescription>
              </div>
            </div>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeletingMultiple}>{tc('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleMassDelete}
              disabled={isDeletingMultiple}
              className="bg-threat text-bone hover:bg-threat"
            >
              {isDeletingMultiple ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('leadManagement.deleting')}
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
      {selectedLeadIds.size > 0 && !showMassEmailComposer && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 transform">
          <div className="flex flex-nowrap items-center gap-3 rounded-lg border border-border bg-background px-6 py-3 whitespace-nowrap shadow-xl">
            <span className="text-sm font-medium text-foreground">
              {tc('selected', { count: selectedLeadIds.size })}
            </span>
            <button
              onClick={() => setShowMassEmailComposer(true)}
              className="inline-flex items-center justify-center rounded-lg bg-deep px-4 py-2 text-sm font-medium text-bone transition-all duration-200 hover:bg-deep active:scale-95"
            >
              <Mail className="mr-2 h-4 w-4" />
              {tc('massEmail')}
            </button>
            <button
              onClick={() => setShowMassDeleteModal(true)}
              className="inline-flex items-center justify-center rounded-lg bg-threat px-4 py-2 text-sm font-medium text-bone transition-all duration-200 hover:bg-threat active:scale-95"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {tc('deleteSelected')} ({selectedLeadIds.size})
            </button>
            <button
              onClick={() => setSelectedLeadIds(new Set())}
              className="rounded-lg px-3 py-2 text-sm font-medium text-mute transition-colors hover:bg-muted hover:text-foreground"
            >
              {tc('clear')}
            </button>
          </div>
        </div>
      )}

      {showScheduledEmailsModal && (
        <ScheduledEmailsModal
          open={showScheduledEmailsModal}
          onClose={() => setShowScheduledEmailsModal(false)}
          service="leads"
        />
      )}

      {/* Add Lead Modal */}
      <Dialog open={showAddLeadModal} onOpenChange={setShowAddLeadModal}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle className="title-page">{t('leadManagement.addNewLead')}</DialogTitle>
            <DialogDescription>{t('leadManagement.enterLeadInfo')}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-ink">
                  {t('leadForm.company')} <span className="text-threat">*</span>
                </label>
                <input
                  type="text"
                  value={newLeadData.company}
                  onChange={(e) => setNewLeadData({ ...newLeadData, company: e.target.value })}
                  className="w-full rounded-md border border-rule px-3 py-2 focus:ring-2 focus:ring-accent focus:outline-none"
                  placeholder={t('leadManagement.companyPlaceholder')}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-ink">
                  {t('leadForm.location')}
                </label>
                <input
                  type="text"
                  value={newLeadData.location}
                  onChange={(e) => setNewLeadData({ ...newLeadData, location: e.target.value })}
                  className="w-full rounded-md border border-rule px-3 py-2 focus:ring-2 focus:ring-accent focus:outline-none"
                  placeholder={t('leadManagement.locationPlaceholder')}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-ink">
                  {t('leadForm.industry')}
                </label>
                <input
                  type="text"
                  value={newLeadData.industry}
                  onChange={(e) => setNewLeadData({ ...newLeadData, industry: e.target.value })}
                  className="w-full rounded-md border border-rule px-3 py-2 focus:ring-2 focus:ring-accent focus:outline-none"
                  placeholder={t('leadForm.industryPlaceholder')}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-ink">
                  {t('leadForm.email')}
                </label>
                <input
                  type="email"
                  value={newLeadData.contactEmail}
                  onChange={(e) => setNewLeadData({ ...newLeadData, contactEmail: e.target.value })}
                  className="w-full rounded-md border border-rule px-3 py-2 focus:ring-2 focus:ring-accent focus:outline-none"
                  placeholder="email@example.com"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-ink">
                  {t('leadForm.phone')}
                </label>
                <input
                  type="tel"
                  value={newLeadData.contactPhone}
                  onChange={(e) => setNewLeadData({ ...newLeadData, contactPhone: e.target.value })}
                  className="w-full rounded-md border border-rule px-3 py-2 focus:ring-2 focus:ring-accent focus:outline-none"
                  placeholder="(555) 123-4567"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-ink">
                  {t('leadForm.website')}
                </label>
                <input
                  type="url"
                  value={newLeadData.website}
                  onChange={(e) => setNewLeadData({ ...newLeadData, website: e.target.value })}
                  className="w-full rounded-md border border-rule px-3 py-2 focus:ring-2 focus:ring-accent focus:outline-none"
                  placeholder="https://example.com"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">
                {t('leadForm.status')}
              </label>
              <select
                value={newLeadData.status}
                onChange={(e) => setNewLeadData({ ...newLeadData, status: e.target.value })}
                className="w-full rounded-md border border-rule px-3 py-2 focus:ring-2 focus:ring-accent focus:outline-none"
              >
                <option value="new">{t('status.new')}</option>
                <option value="synced_to_crm">{t('status.synced_to_crm')}</option>
                <option value="qualified">{t('status.qualified')}</option>
                <option value="not_interested">{t('status.not_interested')}</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowAddLeadModal(false)
                setNewLeadData({
                  company: '',
                  location: '',
                  industry: '',
                  contactEmail: '',
                  contactPhone: '',
                  website: '',
                  status: 'new',
                })
              }}
              disabled={isAddingLead}
            >
              {tc('cancel')}
            </Button>
            <Button onClick={handleAddLead} disabled={isAddingLead || !newLeadData.company}>
              {isAddingLead ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('leadManagement.adding')}
                </>
              ) : (
                t('leadList.addButton')
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default LeadManagement
