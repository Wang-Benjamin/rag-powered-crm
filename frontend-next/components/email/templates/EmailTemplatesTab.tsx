'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ConfirmationToast } from '@/components/ui/confirmation-toast'
import { PageLoader } from '@/components/ui/page-loader'
import { useConfirmationToast } from '@/hooks/useConfirmationToast'
import { TemplateEditor } from './TemplateEditor'
import { SimpleTemplateList } from '../SimpleTemplateList'
import { Plus, Search, Mail, FileText, Copy, Send, Layers, Sparkles, PenLine } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/hooks/useAuth'
import { useEmailProfiles } from '@/contexts/EmailProfilesContext'
import { usePersistedUIState } from '@/hooks/usePersistedState'
import { templateApi } from '@/lib/api/emailprofiles'
import type { EmailTemplate, TemplateType } from '@/types/email'
import { cn } from '@/utils/cn'

interface EmailTemplatesTabProps {
  autoCreateNew?: boolean
}

export function EmailTemplatesTab({ autoCreateNew = false }: EmailTemplatesTabProps = {}) {
  const t = useTranslations('email')
  const tc = useTranslations('common')
  const { user } = useAuth()
  const {
    templates: cachedTemplates,
    templatesLoading,
    loadTemplates: contextLoadTemplates,
    refreshTemplates,
  } = useEmailProfiles()

  // Persisted template type toggle (survives navigation)
  const [templateType, setTemplateType] = usePersistedUIState<TemplateType>(
    'email_template_type',
    'crm'
  )

  // Local UI state (editing session only)
  const [search, setSearch] = useState('')
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [createMode, setCreateMode] = useState<'ai' | 'manual' | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [, setPendingAction] = useState<(() => void) | null>(null)

  // Derived from context
  const templates = cachedTemplates[templateType]
  const isLoading = templatesLoading

  // Aggregate stats
  const crmTemplates = cachedTemplates['crm']
  const leadgenTemplates = cachedTemplates['leadgen']
  const totalSends = useMemo(
    () => templates.reduce((sum, t) => sum + (t.sendCount || 0), 0),
    [templates]
  )

  // Confirmation toast
  const { confirm, toastProps } = useConfirmationToast()

  // Filter templates based on search
  const filteredTemplates = useMemo(() => {
    if (!search.trim()) return templates
    const searchLower = search.toLowerCase()
    return templates.filter(
      (t) =>
        t.name.toLowerCase().includes(searchLower) ||
        t.subject.toLowerCase().includes(searchLower) ||
        t.description?.toLowerCase().includes(searchLower)
    )
  }, [templates, search])

  const handleNewTemplate = useCallback(() => {
    const doNew = () => {
      setSelectedTemplate(null)
      setIsCreating(true)
      setCreateMode(null)
      setIsDirty(false)
    }

    if (isDirty) {
      confirm({
        title: t('templatesTab.unsavedChanges'),
        description: t('templatesTab.discardPrompt'),
        confirmLabel: t('templatesTab.discard'),
        cancelLabel: tc('cancel'),
        variant: 'warning',
        onConfirm: doNew,
      })
    } else {
      doNew()
    }
  }, [isDirty, confirm])

  // Load templates from context (skips fetch if cache is valid)
  useEffect(() => {
    contextLoadTemplates(templateType)
    setSelectedTemplate(null)
    setIsCreating(false)
  }, [templateType, contextLoadTemplates])

  useEffect(() => {
    if (autoCreateNew && !isLoading) {
      handleNewTemplate()
    }
  }, [autoCreateNew, isLoading, handleNewTemplate])

  const handleTemplateSelect = useCallback(
    (template: EmailTemplate) => {
      const doSelect = () => {
        setIsCreating(false)
        setSelectedTemplate(template)
        setIsDirty(false)
      }

      if (isDirty) {
        setPendingAction(() => doSelect)
        confirm({
          title: t('templatesTab.unsavedChanges'),
          description: t('templatesTab.discardPrompt'),
          confirmLabel: t('templatesTab.discard'),
          cancelLabel: tc('cancel'),
          variant: 'warning',
          onConfirm: () => {
            doSelect()
            setPendingAction(null)
          },
          onCancel: () => setPendingAction(null),
        })
      } else {
        doSelect()
      }
    },
    [isDirty, confirm]
  )

  const handleDelete = useCallback(
    (template: EmailTemplate) => {
      confirm({
        title: t('templatesTab.deleteTemplate'),
        description: t('templatesTab.deleteWarning'),
        confirmLabel: tc('delete'),
        cancelLabel: tc('cancel'),
        variant: 'destructive',
        itemName: template.name,
        onConfirm: async () => {
          if (!user?.email) return
          try {
            await templateApi.deleteTemplate(template.id)
            if (selectedTemplate?.id === template.id) {
              setSelectedTemplate(null)
            }
            await refreshTemplates(templateType)
            toast(tc('success'), { description: t('templatesTab.templateDeleted') })
          } catch {
            toast.error(tc('error'), { description: t('templatesTab.deleteFailed') })
          }
        },
      })
    },
    [user?.email, selectedTemplate, confirm, refreshTemplates, templateType]
  )

  const handleDuplicate = useCallback(async () => {
    if (!selectedTemplate || !user?.email) return

    try {
      const newName = `${selectedTemplate.name} - Copy`
      const newTemplate = await templateApi.duplicateTemplate(selectedTemplate.id, newName)
      await refreshTemplates(templateType)
      setSelectedTemplate(newTemplate)
      toast(tc('success'), { description: t('templatesTab.duplicated', { name: newName }) })
    } catch {
      toast.error(tc('error'), { description: t('templatesTab.duplicateFailed') })
    }
  }, [selectedTemplate, user?.email, refreshTemplates, templateType])

  const handleSaveTemplate = () => {
    setIsCreating(false)
    setSelectedTemplate(null)
    setIsDirty(false)
    refreshTemplates(templateType)
    toast(tc('success'), { description: t('templatesTab.templateSaved') })
  }

  const handleCancelEdit = () => {
    setIsCreating(false)
    setCreateMode(null)
    setSelectedTemplate(null)
    setIsDirty(false)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 overflow-hidden">
        {/* ─── Left Column: Template List ─── */}
        <div className="flex w-[340px] flex-shrink-0 flex-col border-r border-zinc-200 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-900/30">
          {/* Header area */}
          <div className="border-b border-zinc-200/70 p-4 pb-3 dark:border-zinc-800">
            {/* Segmented toggle with counts */}
            <div className="mb-3 flex rounded-lg bg-zinc-200/60 p-0.5 dark:bg-zinc-800">
              <button
                onClick={() => setTemplateType('crm')}
                className={cn(
                  'flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all',
                  templateType === 'crm'
                    ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100'
                    : 'text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300'
                )}
              >
                {t('templatesTab.crm')}
                <span
                  className={cn(
                    'rounded-full px-1.5 py-0.5 text-[10px] font-medium tabular-nums',
                    templateType === 'crm'
                      ? 'bg-zinc-100 text-zinc-700 dark:bg-zinc-600 dark:text-zinc-200'
                      : 'bg-zinc-300/60 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-500'
                  )}
                >
                  {crmTemplates.length}
                </span>
              </button>
              <button
                onClick={() => setTemplateType('leadgen')}
                className={cn(
                  'flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all',
                  templateType === 'leadgen'
                    ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100'
                    : 'text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300'
                )}
              >
                {t('templatesTab.leadGen')}
                <span
                  className={cn(
                    'rounded-full px-1.5 py-0.5 text-[10px] font-medium tabular-nums',
                    templateType === 'leadgen'
                      ? 'bg-zinc-100 text-zinc-700 dark:bg-zinc-600 dark:text-zinc-200'
                      : 'bg-zinc-300/60 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-500'
                  )}
                >
                  {leadgenTemplates.length}
                </span>
              </button>
            </div>

            {/* Title row + New button */}
            <div className="mb-3 flex items-center justify-between">
              <h3 className="title-block">
                {t('templatesTab.templates')}
              </h3>
              <Button onClick={handleNewTemplate} size="sm" className="h-7 px-2.5 text-xs">
                <Plus className="mr-1 h-3.5 w-3.5" /> {t('templatesTab.newButton')}
              </Button>
            </div>

            {/* Search */}
            <div className="relative">
              <Search className="absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 transform text-zinc-400" />
              <Input
                placeholder={t('templatesTab.searchPlaceholder')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 border-zinc-200 bg-white pl-8 text-xs dark:border-zinc-700 dark:bg-zinc-800"
              />
            </div>
          </div>

          {/* Template List */}
          <div className="flex-1 overflow-y-auto px-2 py-2">
            {isLoading ? (
              <div className="py-10">
                <PageLoader label={t('templatesTab.loadingTemplates')} className="min-h-[160px]" />
              </div>
            ) : filteredTemplates.length === 0 ? (
              <div className="px-4 py-16 text-center">
                <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-zinc-200/60 dark:bg-zinc-800">
                  <Mail className="h-4 w-4 text-zinc-400" />
                </div>
                <p className="mb-3 text-xs text-zinc-500">
                  {search ? t('templatesTab.noTemplatesFound') : t('templatesTab.noTemplatesYet')}
                </p>
                {!search && (
                  <Button
                    onClick={handleNewTemplate}
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                  >
                    <Plus className="mr-1.5 h-3 w-3" />
                    {t('templatesTab.createFirst')}
                  </Button>
                )}
              </div>
            ) : (
              <SimpleTemplateList
                templates={filteredTemplates}
                selectedTemplate={selectedTemplate}
                onTemplateSelect={handleTemplateSelect}
                onDeleteTemplate={handleDelete}
              />
            )}
          </div>
        </div>

        {/* ─── Right Column: Editor or Empty State ─── */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-white dark:bg-zinc-900">
          {/* Duplicate button when template selected */}
          {selectedTemplate && !isCreating && (
            <div className="flex flex-shrink-0 justify-end p-4 pb-0">
              <Button variant="outline" size="sm" onClick={handleDuplicate} className="h-7 text-xs">
                <Copy className="mr-1 h-3.5 w-3.5" />
                {t('templatesTab.duplicate')}
              </Button>
            </div>
          )}

          {/* Scrollable content area */}
          <div className="flex-1 overflow-y-auto">
            {selectedTemplate ? (
              <TemplateEditor
                template={selectedTemplate}
                onSave={handleSaveTemplate}
                onCancel={handleCancelEdit}
                templateType={templateType}
                onDirtyChange={setIsDirty}
              />
            ) : isCreating && createMode ? (
              <TemplateEditor
                template={null}
                onSave={handleSaveTemplate}
                onCancel={handleCancelEdit}
                templateType={templateType}
                onDirtyChange={setIsDirty}
                initialAiMode={createMode === 'ai'}
              />
            ) : isCreating ? (
              /* ─── Gateway: Choose AI or Manual ─── */
              <div className="flex h-full items-center justify-center">
                <div className="max-w-lg px-8 text-center">
                  <h3 className="mb-1.5 title-block">
                    {t('templatesTab.createNew')}
                  </h3>
                  <p className="mb-8 text-xs text-zinc-500 dark:text-zinc-400">
                    {t('templatesTab.selectOrCreate')}
                  </p>
                  <div className="mx-auto grid max-w-md grid-cols-2 gap-4">
                    <button
                      onClick={() => setCreateMode('ai')}
                      className="group flex flex-col items-center gap-3 rounded-xl border border-zinc-200 bg-white p-6 transition-all hover:border-zinc-400 hover:shadow-md dark:border-zinc-700 dark:bg-zinc-800/50 dark:hover:border-zinc-500"
                    >
                      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100 transition-colors group-hover:bg-zinc-200 dark:bg-zinc-800 dark:group-hover:bg-zinc-700">
                        <Sparkles className="h-5 w-5 text-zinc-600 dark:text-zinc-400" />
                      </div>
                      <div>
                        <p className="mb-0.5 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                          {t('templateEditor.generateWithAi')}
                        </p>
                        <p className="text-[11px] leading-relaxed text-zinc-500">
                          {t('templateEditor.createDescription')}
                        </p>
                      </div>
                    </button>
                    <button
                      onClick={() => setCreateMode('manual')}
                      className="group flex flex-col items-center gap-3 rounded-xl border border-zinc-200 bg-white p-6 transition-all hover:border-zinc-400 hover:shadow-md dark:border-zinc-700 dark:bg-zinc-800/50 dark:hover:border-zinc-500"
                    >
                      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100 transition-colors group-hover:bg-zinc-200 dark:bg-zinc-800 dark:group-hover:bg-zinc-700">
                        <PenLine className="h-5 w-5 text-zinc-600 dark:text-zinc-400" />
                      </div>
                      <div>
                        <p className="mb-0.5 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                          {t('templateEditor.manualTitle')}
                        </p>
                        <p className="text-[11px] leading-relaxed text-zinc-500">
                          {t('templateEditor.manualDescription')}
                        </p>
                      </div>
                    </button>
                  </div>
                  <button
                    onClick={handleCancelEdit}
                    className="mt-6 text-xs text-zinc-400 transition-colors hover:text-zinc-600"
                  >
                    {t('templateEditor.cancel')}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center">
                <div className="max-w-sm px-8 text-center">
                  {/* Stats row */}
                  <div className="mb-8 flex items-center justify-center gap-6">
                    <div className="text-center">
                      <div className="mx-auto mb-1.5 flex h-10 w-10 items-center justify-center rounded-full bg-zinc-100 dark:bg-zinc-800">
                        <Layers className="h-4 w-4 text-zinc-500" />
                      </div>
                      <p className="text-lg font-semibold text-zinc-900 tabular-nums dark:text-zinc-100">
                        {templates.length}
                      </p>
                      <p className="text-[10px] tracking-wider text-zinc-500 uppercase">
                        {t('templatesTab.templates')}
                      </p>
                    </div>
                    <div className="h-10 w-px bg-zinc-200 dark:bg-zinc-700" />
                    <div className="text-center">
                      <div className="mx-auto mb-1.5 flex h-10 w-10 items-center justify-center rounded-full bg-zinc-100 dark:bg-zinc-800">
                        <Send className="h-4 w-4 text-zinc-500" />
                      </div>
                      <p className="text-lg font-semibold text-zinc-900 tabular-nums dark:text-zinc-100">
                        {totalSends}
                      </p>
                      <p className="text-[10px] tracking-wider text-zinc-500 uppercase">
                        {t('templates.sends', { count: totalSends })}
                      </p>
                    </div>
                  </div>

                  {/* CTA */}
                  <h3 className="mb-1.5 title-block">
                    {t('templatesTab.noTemplateSelected')}
                  </h3>
                  <p className="mb-5 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
                    {t('templatesTab.selectOrCreate')}
                  </p>
                  <Button onClick={handleNewTemplate} size="sm" className="h-8 text-xs">
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    {t('templatesTab.createNew')}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Confirmation Toast */}
      <ConfirmationToast {...toastProps} />
    </div>
  )
}

