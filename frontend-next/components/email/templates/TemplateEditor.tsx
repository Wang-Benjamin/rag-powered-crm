'use client'

import { useState, useEffect, useRef } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { TokenInserter } from './TokenInserter'
import { TemplateTypeBadge } from '../TemplateTypeBadge'
import { toast } from 'sonner'
import { Save, Sparkles, Users, AlertTriangle } from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import { templateApi } from '@/lib/api/emailprofiles'
import type { TemplateLevel } from '@/types/email'

interface Template {
  id?: string
  name: string
  subject: string
  content?: string
  description?: string
  body?: string
  level?: TemplateLevel
  parentId?: string | null
  isShared?: boolean
}

interface TemplateEditorProps {
  template: Template | null
  onSave: () => void
  onCancel?: () => void
  templateType?: 'crm' | 'leadgen'
  onDirtyChange?: (isDirty: boolean) => void
  initialAiMode?: boolean
}

export function TemplateEditor({
  template,
  onSave,
  onCancel,
  templateType = 'crm',
  onDirtyChange,
  initialAiMode = false,
}: TemplateEditorProps) {
  const t = useTranslations('email.templateEditor')
  const tc = useTranslations('common')

  const [name, setName] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [description, setDescription] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isShared, setIsShared] = useState(false)

  // AI generation state
  const [aiPrompt, setAiPrompt] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [showAiSection, setShowAiSection] = useState(initialAiMode)

  // Track original values for dirty checking
  const [originalValues, setOriginalValues] = useState({
    name: '',
    subject: '',
    body: '',
    description: '',
    isShared: false,
  })

  const subjectRef = useRef<HTMLTextAreaElement>(null)
  const bodyRef = useRef<HTMLTextAreaElement>(null)

  // Load template data when editing
  useEffect(() => {
    if (template) {
      const values = {
        name: template.name || '',
        subject: template.subject || '',
        body: template.body || template.content || '',
        description: template.description || '',
        isShared: template.isShared || false,
      }
      setName(values.name)
      setSubject(values.subject)
      setBody(values.body)
      setDescription(values.description)
      setIsShared(values.isShared)
      setOriginalValues(values)
    } else {
      const values = { name: '', subject: '', body: '', description: '', isShared: false }
      setName('')
      setSubject('')
      setBody('')
      setDescription('')
      setIsShared(false)
      setOriginalValues(values)
    }
  }, [template])

  // Track dirty state
  useEffect(() => {
    const isDirty =
      name !== originalValues.name ||
      subject !== originalValues.subject ||
      body !== originalValues.body ||
      description !== originalValues.description ||
      isShared !== originalValues.isShared
    onDirtyChange?.(isDirty)
  }, [name, subject, body, description, isShared, originalValues, onDirtyChange])

  const insertToken = (textareaRef: React.RefObject<HTMLTextAreaElement>, token: string) => {
    const textarea = textareaRef.current
    if (!textarea) return

    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const text = textarea.value
    const newText = text.substring(0, start) + token + text.substring(end)

    if (textareaRef === subjectRef) {
      setSubject(newText)
    } else {
      setBody(newText)
    }

    setTimeout(() => {
      textarea.focus()
      textarea.selectionStart = textarea.selectionEnd = start + token.length
    }, 0)
  }

  const handleGenerateWithAI = async () => {
    if (!aiPrompt.trim()) {
      toast.error(tc('error'), { description: t('errorPromptRequired') })
      return
    }

    setIsGenerating(true)

    try {
      const result = await templateApi.generateTemplate(aiPrompt, templateType)
      setSubject(result.subject)
      setBody(result.body)
      setShowAiSection(false)
      setAiPrompt('')
      toast(tc('success'), { description: t('successGenerated') })
    } catch {
      toast.error(tc('error'), { description: t('errorGenerateFailed') })
    } finally {
      setIsGenerating(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!name.trim()) {
      toast.error(tc('error'), { description: t('errorNameRequired') })
      return
    }
    if (!subject.trim()) {
      toast.error(tc('error'), { description: t('errorSubjectRequired') })
      return
    }
    if (!body.trim()) {
      toast.error(tc('error'), { description: t('errorBodyRequired') })
      return
    }

    setIsSubmitting(true)

    try {
      if (template?.id) {
        await templateApi.updateTemplate(template.id, {
          name: name.trim(),
          subject: subject.trim(),
          body: body.trim(),
          description: description.trim() || undefined,
          isShared: isShared,
        })
      } else {
        await templateApi.createTemplate({
          name: name.trim(),
          subject: subject.trim(),
          body: body.trim(),
          description: description.trim() || undefined,
          channel: 'email',
          templateType: templateType,
          isShared: isShared,
        })
      }
      onSave()
    } catch {
      toast.error(tc('error'), { description: t('errorSaveFailed') })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex h-full flex-col p-6">
      {/* Header */}
      <div className="mb-8">
        <h3 className="mb-1 title-panel">
          {template ? t('editTitle') : t('createTitle')}
        </h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          {template
            ? t('editDescription')
            : initialAiMode
              ? t('createDescription')
              : t('manualDescription')}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-1 flex-col">
        <div className="flex-1 space-y-8 overflow-y-auto">
          {/* AI Generation Section — shown when AI mode selected from gateway */}
          {showAiSection && (
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-5 dark:border-zinc-700 dark:bg-zinc-800/50">
              <Label
                htmlFor="ai-prompt"
                className="mb-3 flex items-center gap-2 text-sm font-medium text-zinc-900 dark:text-zinc-100"
              >
                <Sparkles className="h-4 w-4" />
                {t('aiGeneration')}
              </Label>
              <p className="mb-3 text-xs text-zinc-500">{t('createDescription')}</p>
              <div className="space-y-3">
                <Textarea
                  id="ai-prompt"
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  placeholder={t('aiPromptPlaceholder')}
                  rows={3}
                  className="bg-white dark:bg-zinc-900"
                  autoFocus
                />
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleGenerateWithAI}
                    disabled={isGenerating || !aiPrompt.trim()}
                    loading={isGenerating}
                    loadingText={t('generating')}
                  >
                    <Sparkles className="mr-2 h-3.5 w-3.5" /> {t('generate')}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowAiSection(false)}
                  >
                    {t('cancel')}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Template Name & Description */}
          <div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_280px]">
            <div className="space-y-2">
              <Label
                htmlFor="name"
                className="text-xs font-medium text-zinc-600 dark:text-zinc-400"
              >
                {t('templateName')} <span className="text-red-400">{t('required')}</span>
              </Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('templateNamePlaceholder')}
                required
              />
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="description"
                className="text-xs font-medium text-zinc-600 dark:text-zinc-400"
              >
                {t('descriptionLabel')}
              </Label>
              <Input
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t('descriptionPlaceholder')}
              />
            </div>
          </div>

          {/* Template Level Badge (for existing templates) */}
          {template?.level !== undefined && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500 dark:text-zinc-400">{t('templateType')}</span>
              <TemplateTypeBadge level={template.level} />
              {template.parentId && (
                <span className="text-xs text-zinc-400">{t('derivedFromParent')}</span>
              )}
            </div>
          )}

          {/* Share Template Option */}
          <div className="rounded-lg border border-zinc-200 bg-zinc-50/50 p-4 dark:border-zinc-700 dark:bg-zinc-800/30">
            <div className="flex items-center gap-3">
              <Checkbox
                id="is-shared"
                checked={isShared}
                onCheckedChange={(checked) => setIsShared(checked as boolean)}
                disabled={!!(template && template.isShared)}
              />
              <Label htmlFor="is-shared" className="mb-0 flex cursor-pointer items-center gap-2">
                <Users className="h-4 w-4 text-zinc-500" />
                <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  {t('shareWithAll')}
                </span>
              </Label>
            </div>
            <p className="mt-2 ml-7 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
              {isShared ? t('shareVisibleAll') : t('shareVisibleYou')}
            </p>
            {template && template.isShared && (
              <p className="mt-2 ml-7 flex items-center gap-1 text-xs text-amber-600">
                <AlertTriangle className="h-3 w-3" />
                {t('cannotChangeSharing')}
              </p>
            )}
          </div>

          {/* Subject */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label
                htmlFor="subject"
                className="text-xs font-medium text-zinc-600 dark:text-zinc-400"
              >
                {t('emailSubject')} <span className="text-red-400">{t('required')}</span>
              </Label>
              <TokenInserter
                onInsertToken={(token) =>
                  insertToken(subjectRef as React.RefObject<HTMLTextAreaElement>, token)
                }
                size="sm"
              />
            </div>
            <Textarea
              ref={subjectRef}
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Hello {{name}}, welcome to our platform!"
              rows={2}
              required
            />
          </div>

          {/* Body */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label
                htmlFor="body"
                className="text-xs font-medium text-zinc-600 dark:text-zinc-400"
              >
                {t('emailBody')} <span className="text-red-400">{t('required')}</span>
              </Label>
              <TokenInserter
                onInsertToken={(token) =>
                  insertToken(bodyRef as React.RefObject<HTMLTextAreaElement>, token)
                }
                size="sm"
              />
            </div>
            <Textarea
              ref={bodyRef}
              id="body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={
                'Dear {{name}},\n\nThank you for joining...\n\nBest regards,\n{{sender_name}}'
              }
              rows={14}
              required
              className="resize-none"
            />
            <p className="mt-1.5 text-[11px] text-zinc-400">
              {templateType === 'crm'
                ? 'Available tokens: {{name}}, {{primary_contact}}, {{email}}, {{phone}}'
                : 'Available tokens: {{company}}, {{location}}, {{website}}, {{phone}}'}
            </p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="mt-6 flex items-center gap-3 border-t border-zinc-200 pt-6 dark:border-zinc-700">
          <Button type="submit" loading={isSubmitting} loadingText={t('saving')} size="sm">
            <Save className="mr-2 h-3.5 w-3.5" /> {t('saveTemplate')}
          </Button>
          {onCancel && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onCancel}
              disabled={isSubmitting}
            >
              {t('cancel')}
            </Button>
          )}
        </div>
      </form>
    </div>
  )
}

