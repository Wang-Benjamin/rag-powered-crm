'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  Building,
  Mail,
  Phone,
  RefreshCw,
  User,
  Users,
  Check,
  Star,
  Plus,
  Edit3,
  Trash2,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ConfirmationToast } from '@/components/ui/confirmation-toast'
import InteractionDetailsModal from '../interactions/InteractionDetailsModal'
import NoteDetailsModal from '../interactions/NoteDetailsModal'
import CRMMeetingDetailsModal from '../interactions/CRMMeetingDetailsModal'
import type { Customer, Interaction } from '@/types/crm'

interface Contact {
  id: string
  name: string
  email: string
  phone?: string
  title?: string
  notes?: string
  isPrimary?: boolean
}

interface Note {
  id: string
  title?: string
  body?: string
  content?: string
  date: string
  updatedAt?: string
  isStarred?: boolean
  star?: string
  interactionId?: string
  author?: string
  type?: string
}

interface TimelineEvent {
  type: string
  originalType: string
  title: string
  description?: string
  date: string
  employeeName?: string
  metadata?: {
    noteId?: string
    interactionId?: string
    isStarred?: boolean
    star?: string
    theme?: string
    subject?: string
    direction?: string
    sourceName?: string
    sourceType?: string
    fromEmail?: string
    parsedMeetingData?: any
    [key: string]: any
  }
}

interface CustomerEmployee {
  employeeId: number
  name: string
  email: string
  role: string
  department: string
}

export interface CustomerManagementDialogsProps {
  localCustomer: Customer
  // Contacts dialog
  showContactsModal: boolean
  handleCloseContactsModal: () => void
  contacts: Contact[]
  showContactForm: boolean
  editingContact: Contact | null
  contactFormData: {
    name: string
    email: string
    phone: string
    title: string
    notes: string
  }
  setContactFormData: React.Dispatch<
    React.SetStateAction<{
      name: string
      email: string
      phone: string
      title: string
      notes: string
    }>
  >
  isSavingContact: boolean
  handleAddContactClick: () => void
  handleEditContactClick: (contact: Contact) => void
  handleCancelContactForm: () => void
  handleSaveContact: () => Promise<void>
  handleDeleteContact: (contact: Contact) => void
  handleSetPrimaryContact: (contact: Contact) => Promise<void>
  // Employees dialog
  showEmployeesModal: boolean
  setShowEmployeesModal: (open: boolean) => void
  customerEmployees: CustomerEmployee[]
  employees: any[]
  selectedNewEmployeeId: string
  setSelectedNewEmployeeId: (value: string) => void
  isSavingEmployee: boolean
  handleAddEmployee: () => Promise<void>
  handleRemoveEmployee: (employee: { employeeId: number; name: string }) => void
  // Detail modals
  selectedInteraction: TimelineEvent | null
  isInteractionModalOpen: boolean
  handleInteractionModalClose: () => void
  customerInteractions: Interaction[]
  notes: Note[]
  handleInteractionUpdate: (updatedData: any) => Promise<void>
  selectedNote: Note | null
  showNoteModal: boolean
  handleNoteModalClose: () => void
  handleDeleteNote: (noteId: string) => Promise<void>
  handleNoteUpdate: (updatedNote: any) => Promise<void>
  handleToggleNoteStar: (noteId: string, currentStarStatus?: string) => Promise<void>
  isDeletingNote: string | null
  selectedMeeting: { id: string; data: any } | null
  showMeetingModal: boolean
  handleMeetingModalClose: () => void
  handleMeetingUpdate: () => Promise<void>
  handleMeetingDelete: () => Promise<void>
  // Confirmation toast
  toastProps: any
}

const CustomerManagementDialogs: React.FC<CustomerManagementDialogsProps> = ({
  localCustomer,
  showContactsModal,
  handleCloseContactsModal,
  contacts,
  showContactForm,
  editingContact,
  contactFormData,
  setContactFormData,
  isSavingContact,
  handleAddContactClick,
  handleEditContactClick,
  handleCancelContactForm,
  handleSaveContact,
  handleDeleteContact,
  handleSetPrimaryContact,
  showEmployeesModal,
  setShowEmployeesModal,
  customerEmployees,
  employees,
  selectedNewEmployeeId,
  setSelectedNewEmployeeId,
  isSavingEmployee,
  handleAddEmployee,
  handleRemoveEmployee,
  selectedInteraction,
  isInteractionModalOpen,
  handleInteractionModalClose,
  customerInteractions,
  notes,
  handleInteractionUpdate,
  selectedNote,
  showNoteModal,
  handleNoteModalClose,
  handleDeleteNote,
  handleNoteUpdate,
  handleToggleNoteStar,
  isDeletingNote,
  selectedMeeting,
  showMeetingModal,
  handleMeetingModalClose,
  handleMeetingUpdate,
  handleMeetingDelete,
  toastProps,
}) => {
  const t = useTranslations('crm')
  return (
    <>
      {/* Contacts Modal */}
      <Dialog open={showContactsModal} onOpenChange={(open) => !open && handleCloseContactsModal()}>
        <DialogContent className="flex max-h-[90vh] max-w-3xl flex-col p-0">
          <DialogHeader className="border-b border-rule p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cream">
                <Users className="h-5 w-5 text-deep" />
              </div>
              <div>
                <DialogTitle className="title-page">
                  {t('customerModal.contacts')}
                </DialogTitle>
                <p className="text-sm text-mute">{localCustomer.company}</p>
              </div>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto p-6">
            {!showContactForm ? (
              <>
                <div className="space-y-3">
                  {[...contacts]
                    .sort((a, b) => {
                      if (a.isPrimary && !b.isPrimary) return -1
                      if (!a.isPrimary && b.isPrimary) return 1
                      return 0
                    })
                    .map((contact) => (
                      <div
                        key={contact.id}
                        className="rounded-lg border border-rule bg-paper p-4 transition-colors hover:border-rule"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="mb-2 flex items-center gap-2">
                              <h3 className="font-semibold text-ink">{contact.name}</h3>
                              {contact.isPrimary && (
                                <span className="inline-flex items-center gap-1 rounded bg-cream px-2 py-0.5 text-xs font-medium text-ink">
                                  <Star className="h-3 w-3 fill-current" />
                                  {t('customerModal.primaryBadge')}
                                </span>
                              )}
                            </div>
                            <div className="space-y-1 text-sm">
                              <div className="flex items-center gap-2 text-mute">
                                <Mail className="h-4 w-4" />
                                <span>{contact.email}</span>
                              </div>
                              {contact.phone && (
                                <div className="flex items-center gap-2 text-mute">
                                  <Phone className="h-4 w-4" />
                                  <span>{contact.phone}</span>
                                </div>
                              )}
                              {contact.title && (
                                <div className="flex items-center gap-2 text-mute">
                                  <User className="h-4 w-4" />
                                  <span>{contact.title}</span>
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="ml-4 flex items-center gap-2">
                            <button
                              onClick={() => handleEditContactClick(contact)}
                              className="rounded p-2 text-mute transition-colors hover:bg-cream hover:text-ink"
                            >
                              <Edit3 className="h-4 w-4" />
                            </button>
                            {!contact.isPrimary && (
                              <>
                                <button
                                  onClick={() => handleSetPrimaryContact(contact)}
                                  className="rounded p-2 text-mute transition-colors hover:bg-gold-lo hover:text-gold"
                                >
                                  <Star className="h-4 w-4" />
                                </button>
                                <button
                                  onClick={() => handleDeleteContact(contact)}
                                  className="rounded p-2 text-mute transition-colors hover:bg-threat-lo hover:text-threat"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
                <button
                  onClick={handleAddContactClick}
                  className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-rule py-3 text-mute transition-colors hover:border-rule hover:bg-cream hover:text-ink"
                >
                  <Plus className="h-5 w-5" />
                  <span className="font-medium">{t('customerModal.addContact')}</span>
                </button>
              </>
            ) : (
              <div className="space-y-4">
                <h3 className="mb-4 title-panel">
                  {editingContact ? t('customerModal.editContact') : t('customerModal.addContact')}
                </h3>
                <div>
                  <label className="mb-1 block text-sm font-medium text-ink">
                    {t('customerModal.contactName')} *
                  </label>
                  <input
                    type="text"
                    value={contactFormData.name}
                    onChange={(e) =>
                      setContactFormData({ ...contactFormData, name: e.target.value })
                    }
                    className="w-full rounded border border-rule bg-bone px-3 py-2 focus:ring-2 focus:border-accent focus:outline-none"
                    placeholder={t('customerModal.contactNamePlaceholder')}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-ink">
                    {t('customerModal.contactEmail')} *
                  </label>
                  <input
                    type="email"
                    value={contactFormData.email}
                    onChange={(e) =>
                      setContactFormData({ ...contactFormData, email: e.target.value })
                    }
                    className="w-full rounded border border-rule bg-bone px-3 py-2 focus:ring-2 focus:border-accent focus:outline-none"
                    placeholder={t('customerModal.contactEmailPlaceholder')}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-ink">
                    {t('customerModal.contactPhone')}
                  </label>
                  <input
                    type="tel"
                    value={contactFormData.phone}
                    onChange={(e) =>
                      setContactFormData({ ...contactFormData, phone: e.target.value })
                    }
                    className="w-full rounded border border-rule bg-bone px-3 py-2 focus:ring-2 focus:border-accent focus:outline-none"
                    placeholder={t('customerModal.contactPhonePlaceholder')}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-ink">
                    {t('customerModal.contactTitle')}
                  </label>
                  <input
                    type="text"
                    value={contactFormData.title}
                    onChange={(e) =>
                      setContactFormData({ ...contactFormData, title: e.target.value })
                    }
                    className="w-full rounded border border-rule bg-bone px-3 py-2 focus:ring-2 focus:border-accent focus:outline-none"
                    placeholder={t('customerModal.contactTitlePlaceholder')}
                  />
                </div>
                <div className="flex gap-3 pt-4">
                  <Button
                    variant="outline"
                    onClick={handleCancelContactForm}
                    disabled={isSavingContact}
                    className="flex-1"
                  >
                    {t('interactions.cancel')}
                  </Button>
                  <Button
                    onClick={handleSaveContact}
                    disabled={isSavingContact}
                    className="flex-1"
                  >
                    {isSavingContact ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        <span>{t('customerModal.saving')}</span>
                      </>
                    ) : (
                      <>
                        <Check className="h-4 w-4" />
                        <span>
                          {editingContact
                            ? t('customerModal.updateContact')
                            : t('customerModal.addContact')}
                        </span>
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Employees Modal */}
      <Dialog
        open={showEmployeesModal}
        onOpenChange={(open) => !open && setShowEmployeesModal(false)}
      >
        <DialogContent className="flex max-h-[90vh] max-w-2xl flex-col p-0">
          <DialogHeader className="border-b border-rule p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cream">
                <Users className="h-5 w-5 text-deep" />
              </div>
              <div>
                <DialogTitle className="title-page">
                  {t('customerModal.assignedEmployee')}
                </DialogTitle>
                <p className="text-sm text-mute">{localCustomer.company}</p>
              </div>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto p-6">
            {/* Employee list */}
            <div className="space-y-3">
              {customerEmployees.map((emp) => (
                <div
                  key={emp.employeeId}
                  className="rounded-lg border border-rule bg-paper p-4 transition-colors hover:border-rule"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-semibold text-ink">{emp.name}</h3>
                      <div className="mt-1 space-y-1 text-sm">
                        {emp.role && (
                          <div className="flex items-center gap-2 text-mute">
                            <User className="h-4 w-4" />
                            <span>{emp.role}</span>
                          </div>
                        )}
                        {emp.department && (
                          <div className="flex items-center gap-2 text-mute">
                            <Building className="h-4 w-4" />
                            <span>{emp.department}</span>
                          </div>
                        )}
                        {emp.email && (
                          <div className="flex items-center gap-2 text-mute">
                            <Mail className="h-4 w-4" />
                            <span>{emp.email}</span>
                          </div>
                        )}
                      </div>
                    </div>
                    {customerEmployees.length > 1 && (
                      <button
                        onClick={() => handleRemoveEmployee(emp)}
                        className="ml-4 rounded p-2 text-mute transition-colors hover:bg-threat-lo hover:text-threat"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Add employee section */}
            {(() => {
              const availableEmployees =
                (employees as any[])?.filter(
                  (emp) =>
                    !customerEmployees.some((ce) => ce.employeeId === (emp.employeeId || emp.id))
                ) || []

              if (availableEmployees.length === 0) return null

              return (
                <div className="mt-4 border-t border-rule pt-4">
                  <label className="mb-2 block text-sm font-medium text-ink">
                    {t('customerModal.addEmployee')}
                  </label>
                  <div className="flex gap-2">
                    <select
                      value={selectedNewEmployeeId}
                      onChange={(e) => setSelectedNewEmployeeId(e.target.value)}
                      className="flex-1 rounded-lg border border-rule bg-bone px-3 py-2 text-sm focus:border-accent focus:outline-none"
                      disabled={isSavingEmployee}
                    >
                      <option value="">{t('customerModal.selectEmployee')}</option>
                      {availableEmployees.map((emp: any, index: number) => (
                        <option
                          key={emp.employeeId || emp.id || index}
                          value={emp.employeeId?.toString() || emp.id?.toString()}
                        >
                          {emp.name || `${emp.firstName || ''} ${emp.lastName || ''}`.trim()}
                          {emp.role ? ` — ${emp.role}` : ''}
                        </option>
                      ))}
                    </select>
                    <Button
                      onClick={handleAddEmployee}
                      disabled={!selectedNewEmployeeId || isSavingEmployee}
                      className="px-4"
                    >
                      {isSavingEmployee ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Plus className="h-4 w-4" />
                      )}
                      <span className="ml-1">{t('customerModal.add')}</span>
                    </Button>
                  </div>
                </div>
              )
            })()}
          </div>
        </DialogContent>
      </Dialog>

      {/* Interaction Details Modal */}
      {selectedInteraction && (
        <InteractionDetailsModal
          event={selectedInteraction}
          customer={localCustomer || undefined}
          open={isInteractionModalOpen}
          onOpenChange={(open) => {
            if (!open) handleInteractionModalClose()
          }}
          notes={notes}
          customerInteractions={customerInteractions}
          onUpdate={handleInteractionUpdate}
        />
      )}

      {/* Note Details Modal */}
      {selectedNote && (
        <NoteDetailsModal
          note={selectedNote}
          customer={localCustomer || undefined}
          open={showNoteModal}
          onOpenChange={(open) => {
            if (!open) handleNoteModalClose()
          }}
          onDelete={handleDeleteNote}
          onUpdate={handleNoteUpdate}
          onToggleStar={handleToggleNoteStar}
          isDeletingNote={isDeletingNote || undefined}
        />
      )}

      {/* CRM Meeting Details Modal */}
      {selectedMeeting && (
        <CRMMeetingDetailsModal
          isOpen={showMeetingModal}
          onClose={handleMeetingModalClose}
          meetingId={selectedMeeting.id}
          meeting={selectedMeeting.data}
          onUpdate={handleMeetingUpdate}
          onDelete={handleMeetingDelete}
        />
      )}

      {/* Confirmation Toast */}
      <ConfirmationToast {...toastProps} />
    </>
  )
}

export default CustomerManagementDialogs
