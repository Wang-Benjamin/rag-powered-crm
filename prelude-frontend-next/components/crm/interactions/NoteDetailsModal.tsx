import React, { useState, useEffect } from 'react'
import {
  Calendar,
  Clock,
  User,
  FileText,
  Star,
  Trash2,
  RefreshCw,
  Edit3,
  Save,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { crmApiClient } from '@/lib/api/client'
import { useLocale, useTranslations } from 'next-intl'
import { toast } from 'sonner'
import type { Customer } from '@/types/crm'
import {
  isNoteStarred,
  getStarDisplayText as getStarDisplayTextHelper,
} from '../utils/activity-helpers'

interface Note {
  id: string
  title?: string
  body?: string
  content?: string
  date: string
  updatedAt?: string
  author?: string
  star?: string
}

interface NoteDetailsModalProps {
  note: Note
  customer?: Customer
  open?: boolean
  isOpen?: boolean
  onOpenChange?: (open: boolean) => void
  onClose?: () => void
  onDelete?: (noteId: string) => void
  onUpdate?: (note: Note) => Promise<void>
  onToggleStar?: (noteId: string, currentStar?: string) => void
  isDeletingNote?: string
}

/**
 * NoteDetailsModal - Enhanced with shadcn Dialog primitive
 *
 * Now uses shadcn's Dialog for better accessibility and consistency.
 * Supports both old (isOpen/onClose) and new (open/onOpenChange) prop names for backward compatibility.
 */
const NoteDetailsModal: React.FC<NoteDetailsModalProps> = ({
  note,
  customer,
  open,
  isOpen,
  onOpenChange,
  onClose,
  onDelete,
  onUpdate,
  onToggleStar,
  isDeletingNote,
}) => {
  const locale = useLocale()
  const t = useTranslations('crm')

  // Support both new (open) and legacy (isOpen) prop names
  const modalOpen = open !== undefined ? open : (isOpen ?? false)

  // Edit state
  const [isEditing, setIsEditing] = useState(false)
  const [editedTitle, setEditedTitle] = useState('')
  const [editedBody, setEditedBody] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const MAX_TITLE_LENGTH = 200
  const MAX_NOTE_LENGTH = 2000

  // Support both new (onOpenChange) and legacy (onClose) callbacks
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !isSaving && !isEditing) {
      if (onOpenChange) {
        onOpenChange(newOpen)
      } else if (onClose) {
        onClose()
      }
    }
  }

  // Initialize edit fields when note changes
  useEffect(() => {
    if (note && modalOpen) {
      setEditedTitle(note.title || '')
      setEditedBody(note.body || note.content || '')
      setIsEditing(false)
    }
  }, [note, modalOpen])

  // Early returns AFTER all hooks
  if (!note) return null

  // Validate note object has required fields
  if (!note.id) {
    console.error('Note object missing required id field:', note)
    return null
  }

  // Format date and time
  const formatDateTime = (dateString: string) => {
    if (!dateString)
      return { date: t('noteDetail.notApplicable'), time: t('noteDetail.notApplicable') }
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return { date: t('noteDetail.invalidDate'), time: '' }

    return {
      date: date.toLocaleDateString(locale, {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      }),
      time: date.toLocaleTimeString(locale, {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }),
    }
  }

  const getStarDisplayText = (star?: string): string => getStarDisplayTextHelper(star, t)

  const dateTime = formatDateTime(note.date)
  const updatedDateTime = note.updatedAt ? formatDateTime(note.updatedAt) : null
  const noteAuthor = note.author || t('noteDetail.defaultAuthor')
  const noteTitle = note.title || t('noteDetail.defaultTitle')
  const noteBody = note.body || note.content || ''
  const noteStar = note.star || undefined

  // Handle save edit
  const handleSaveEdit = async () => {
    if (!editedBody.trim()) {
      toast.error(t('noteDetailValidation.contentEmpty'))
      return
    }

    if (editedBody.length > MAX_NOTE_LENGTH) {
      toast.error(t('noteDetailValidation.contentMax', { max: MAX_NOTE_LENGTH }))
      return
    }

    if (editedTitle.length > MAX_TITLE_LENGTH) {
      toast.error(t('noteDetailValidation.titleMax', { max: MAX_TITLE_LENGTH }))
      return
    }

    setIsSaving(true)

    try {
      const updatedNote = await crmApiClient.put(`/notes/${note.id}`, {
        title: editedTitle.trim() || null,
        body: editedBody.trim(),
      })

      if (onUpdate) {
        await onUpdate(updatedNote)
      }
      setIsEditing(false)
      toast.success(t('noteDetail.noteUpdated'))
    } catch (err: any) {
      console.error('Error updating note:', err)
      toast.error(t('noteDetailValidation.updateFailed'))
    } finally {
      setIsSaving(false)
    }
  }

  // Handle cancel edit
  const handleCancelEdit = () => {
    setEditedTitle(note.title || '')
    setEditedBody(note.body || note.content || '')
    setIsEditing(false)
  }

  return (
    <Dialog open={modalOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <div>
            <div className="flex items-center gap-2">
              <DialogTitle className="title-page truncate">{noteTitle}</DialogTitle>
              {isNoteStarred(noteStar) && (
                <div className="flex flex-shrink-0 items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs text-yellow-800">
                  <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                  {getStarDisplayText(noteStar)}
                </div>
              )}
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-sm text-zinc-500">
              <FileText className="h-3.5 w-3.5" />
              <span className="font-medium text-zinc-700">{noteAuthor}</span>
              <span className="mx-1 text-zinc-300">·</span>
              <span className="text-zinc-400">{dateTime.date} {dateTime.time}</span>
              {updatedDateTime &&
                note.updatedAt &&
                new Date(note.updatedAt).getTime() !== new Date(note.date).getTime() && (
                  <>
                    <span className="mx-1 text-zinc-300">·</span>
                    <span className="text-zinc-400">
                      {t('noteDetail.lastUpdated', { date: updatedDateTime.date, time: updatedDateTime.time })}
                    </span>
                  </>
                )}
            </div>
          </div>
        </DialogHeader>

        {/* Content */}
        <div className="space-y-6">
          {/* Note Content */}
          <div className="space-y-3">
            {!isEditing && (
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsEditing(true)}
                  className="flex items-center gap-2"
                >
                  <Edit3 className="h-4 w-4" />
                  {t('noteDetail.editButton')}
                </Button>
              </div>
            )}
            <div className="border-t border-zinc-100" />

            {isEditing ? (
              <div className="space-y-4">
                {/* Title Input */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-zinc-700">
                    {t('noteDetail.titleLabel')}{' '}
                    <span className="text-zinc-400">{t('noteDetail.titleOptional')}</span>
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={editedTitle}
                      onChange={(e) => setEditedTitle(e.target.value)}
                      placeholder={t('noteDetail.titlePlaceholder')}
                      className="w-full rounded-lg border border-zinc-300 px-3 py-2 pr-20 text-sm focus:ring-2 focus:ring-zinc-900 focus:outline-none"
                      maxLength={MAX_TITLE_LENGTH}
                      disabled={isSaving}
                    />
                    <div className="absolute right-3 bottom-2 text-xs text-zinc-400">
                      {editedTitle.length}/{MAX_TITLE_LENGTH}
                    </div>
                  </div>
                </div>

                {/* Body Textarea */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-zinc-700">
                    {t('noteDetail.contentLabel')} <span className="text-red-500">*</span>
                  </label>
                  <div className="relative">
                    <textarea
                      value={editedBody}
                      onChange={(e) => setEditedBody(e.target.value)}
                      placeholder={t('noteDetail.contentPlaceholder')}
                      className="h-48 w-full resize-none rounded-lg border border-zinc-300 px-3 py-2 pr-20 text-sm focus:ring-2 focus:ring-zinc-900 focus:outline-none"
                      maxLength={MAX_NOTE_LENGTH}
                      disabled={isSaving}
                    />
                    <div className="absolute right-3 bottom-3 text-xs text-zinc-400">
                      {editedBody.length}/{MAX_NOTE_LENGTH}
                    </div>
                  </div>
                </div>

                {/* Edit Actions */}
                <div className="flex gap-2">
                  <Button
                    onClick={handleSaveEdit}
                    disabled={!editedBody.trim() || isSaving}
                    className="flex items-center gap-2 bg-zinc-900 text-white hover:bg-zinc-800"
                  >
                    {isSaving ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        {t('noteDetail.saving')}
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4" />
                        {t('noteDetail.saveButton')}
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleCancelEdit}
                    disabled={isSaving}
                    className="flex items-center gap-2"
                  >
                    <XCircle className="h-4 w-4" />
                    {t('noteDetail.cancelButton')}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="rounded-lg bg-zinc-50 p-4">
                {noteTitle && noteTitle !== 'Note' && (
                  <h4 className="mb-2 title-block">{noteTitle}</h4>
                )}
                <p className="text-sm leading-relaxed whitespace-pre-wrap text-zinc-700">
                  {noteBody || t('noteDetail.noContent')}
                </p>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="flex items-center justify-between gap-3">
          <div className="flex gap-2">
            {/* Toggle Star Button */}
            <Button
              variant="outline"
              onClick={() => onToggleStar && onToggleStar(note.id, noteStar)}
              disabled={isEditing || isSaving}
              className={`flex items-center gap-2 ${
                isNoteStarred(noteStar)
                  ? 'border-yellow-300 bg-yellow-50 text-yellow-700 hover:bg-yellow-100'
                  : 'hover:bg-zinc-50'
              }`}
            >
              <Star
                className={`h-4 w-4 ${isNoteStarred(noteStar) ? 'fill-yellow-400 text-yellow-400' : ''}`}
              />
              {isNoteStarred(noteStar) ? t('noteDetail.removeStar') : t('noteDetail.markImportant')}
            </Button>
          </div>

          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={isSaving}>
            {t('noteDetail.closeButton')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default NoteDetailsModal
