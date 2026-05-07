'use client'

/**
 * V2 mass-email composer — `.compose` two-pane shell.
 *
 * Same shell as EmailComposer.tsx (single). Differences:
 *   - Left pane: <RecipientList> for navigation between generated emails;
 *     5 rows visible without scroll, scrolls if 6-10 (max recipients = 10
 *     per upstream business rule).
 *   - Right pane binds to currentSubject / currentBody from the hook
 *     (active recipient drives the bindings).
 *   - Footer offers Approve all + sends only approved indices.
 *
 * Behavior preserved from legacy:
 *   - Bilingual toggle for zh-CN locale (read-only zh back-translation).
 *   - Per-recipient approval / send-approved-only.
 *   - Schedule popover.
 *
 * See docs/frontend/email-composer-redesign-plan.md.
 */

import './compose.css'
import React, { useEffect, useState } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import { Sparkles, AlertCircle, CheckCircle2, Copy, Bold, Italic, Underline } from 'lucide-react'
import { SafeHtml } from '@/components/ui/safe-html'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import RichTextEditor from './RichTextEditor'
import FactoryDataFields from './EmailContextFields'
import RecipientList, { type RecipientItem } from './RecipientList'
import AttachmentsInline from './AttachmentsInline'
import ComposeFooter from './ComposeFooter'

interface Column {
  id: string
  label: string
  description?: string
}

interface SavedTemplate {
  id: string
  name: string
  description?: string
  subject: string
  body: string
  templateCategory?: 'purpose' | 'user'
  promptInstructions?: string
}

interface Recipient {
  id: string
  name?: string
  email: string
  company?: string
  [key: string]: any
}

export interface MassEmailComposerUIProps {
  title: string
  columns: Column[]
  recipientLabel: string
  userTemplates: SavedTemplate[]
  selectedTemplateId: string | null
  selectTemplate: (templateId: string | null) => void
  customMessage: string
  setCustomMessage: (message: string) => void
  canUseAi: boolean
  hasGeneratedContent: boolean
  currentSubject: string
  currentBody: string
  isGenerating: boolean
  isSending: boolean
  error: string
  success: string
  generationProgress: string
  handleGenerateEmail: () => void
  handleSendEmails: () => Promise<any>
  insertTarget: 'subject' | 'body'
  setInsertTarget: (target: 'subject' | 'body') => void
  personalizedEmails: any[]
  activeEmailIndex: number
  setActiveEmailIndex: (index: number) => void
  handleSubjectChange: (subject: string) => void
  handleBodyChange: (body: string) => void
  truncateCompanyName: (name: string, maxLength?: number) => string
  recipients: Recipient[]
  onTemplateSelect?: (template: SavedTemplate) => void
  onScheduleSend?: (scheduledAt: string) => Promise<void>
  isScheduling?: boolean
  source?: 'buyers' | 'crm'
  approvedEmailIndices?: Set<number>
  approvedCount?: number
  modifiedEmailIndices?: Set<number>
  toggleApproveEmail?: (index: number) => void
  approveAll?: () => void
  translatedEmails?: Record<number, { subject: string; body: string }>
  isTranslating?: boolean
  translateEmail?: (index: number, subject: string, body: string) => Promise<void>
  tradeFields?: {
    variant: 'trade'
    products: { name: string; fobPrice: string; landedPrice: string }[]
    certifications: string[]
    moq?: string
    leadTime?: string
    sampleStatus?: '' | 'ready' | 'in_production' | 'free_sample'
    onProductsChange: (v: { name: string; fobPrice: string; landedPrice: string }[]) => void
    onCertificationsChange: (v: string[]) => void
    onMoqChange?: (v: string) => void
    onLeadTimeChange?: (v: string) => void
    onSampleStatusChange?: (v: '' | 'ready' | 'in_production' | 'free_sample') => void
  }
  bodyEditorRef: React.RefObject<HTMLDivElement>
  onClose: () => void
  onEmailsSent?: (result: any) => void
  getCompanyName: (email: any) => string
  getCompanyEmail: (email: any) => string
  /** Optional preset for the schedule popover's datetime picker. */
  defaultScheduleTime?: string
}

const MassEmailComposerUI: React.FC<MassEmailComposerUIProps> = ({
  title,
  userTemplates,
  selectedTemplateId,
  selectTemplate,
  customMessage,
  setCustomMessage,
  canUseAi,
  hasGeneratedContent,
  currentSubject,
  currentBody,
  isGenerating,
  isSending,
  error,
  success,
  generationProgress,
  handleGenerateEmail,
  handleSendEmails,
  setInsertTarget,
  personalizedEmails,
  activeEmailIndex,
  setActiveEmailIndex,
  handleSubjectChange,
  handleBodyChange,
  recipients,
  onTemplateSelect,
  onScheduleSend,
  isScheduling = false,
  source,
  approvedEmailIndices,
  approvedCount = 0,
  modifiedEmailIndices,
  toggleApproveEmail,
  approveAll,
  translatedEmails = {},
  isTranslating = false,
  translateEmail,
  bodyEditorRef,
  tradeFields,
  onClose,
  onEmailsSent,
  getCompanyName,
  getCompanyEmail,
  defaultScheduleTime,
}) => {
  const t = useTranslations('email')
  const locale = useLocale()
  const isZhLocale = locale.startsWith('zh')

  const [previewLanguage, setPreviewLanguage] = useState<'zh' | 'preview'>('preview')
  const [attachments, setAttachments] = useState<File[]>([])

  // Trigger zh translation when toggling to it / switching active recipient.
  useEffect(() => {
    if (
      previewLanguage === 'zh' &&
      hasGeneratedContent &&
      isZhLocale &&
      translateEmail &&
      currentSubject &&
      currentBody
    ) {
      translateEmail(activeEmailIndex, currentSubject, currentBody)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewLanguage, activeEmailIndex, hasGeneratedContent])

  // Auto-switch to English preview after generation.
  useEffect(() => {
    if (hasGeneratedContent && isZhLocale) setPreviewLanguage('preview')
  }, [hasGeneratedContent, isZhLocale])

  const handleSend = async () => {
    try {
      const result = await handleSendEmails()
      if (onEmailsSent && result) onEmailsSent(result)
      // Match the legacy ~2s post-send close so users see the success toast.
      setTimeout(() => onClose(), 2000)
    } catch {
      /* error surfaced inside the hook */
    }
  }

  const handleRichTextBodyChange = (html: string) => {
    // Legacy converted HTML → plain text. Keep for now; subject/body persisted
    // as plain text downstream.
    let content = html.replace(/<br\s*\/?>/gi, '\n')
    content = content.replace(/<\/(div|p)>/gi, '\n')
    content = content.replace(/<[^>]*>/g, '')
    const ta = document.createElement('textarea')
    ta.innerHTML = content
    handleBodyChange(ta.value)
  }

  const handleTemplateCardClick = (template: SavedTemplate) => {
    selectTemplate(template.id)
    onTemplateSelect?.(template)
  }

  // Build recipient items: post-generation, drive the list off personalizedEmails;
  // pre-generation, off recipients (no active selection).
  const items: RecipientItem[] = hasGeneratedContent
    ? personalizedEmails.map((email, idx) => {
        const name = getCompanyName(email) || ''
        const addr = getCompanyEmail(email) || ''
        const generationError = email.generationError || email.generation_error
        return {
          id: email.recipientId || email.recipient_id || email.recipient?.id || addr || idx,
          name,
          email: addr,
          error: generationError || (!addr ? t('composer.recipients.noEmail') : undefined),
        }
      })
    : recipients.map((r) => ({
        id: r.id,
        name: r.name || r.company || '',
        email: r.email,
        error: !r.email ? t('composer.recipients.noEmail') : undefined,
      }))

  const currentToEmail =
    personalizedEmails.length > 0 ? getCompanyEmail(personalizedEmails[activeEmailIndex]) : ''

  // Sendable counts: a row with no email cannot be sent. Footer + recipient
  // list both display approved-and-sendable counts so the user isn't told
  // "10/10 approved" when 3 of those rows are unsendable.
  const sendableTotal = items.reduce((n, item) => (item.error ? n : n + 1), 0)
  const approvedSendableCount = items.reduce(
    (n, item, idx) => (!item.error && approvedEmailIndices?.has(idx) ? n + 1 : n),
    0
  )

  // Wrap approveAll so it only flips sendable rows. The hook's approveAll
  // would otherwise mark error rows approved too.
  const handleApproveAllSendable = () => {
    if (!toggleApproveEmail) return
    items.forEach((item, idx) => {
      if (!item.error && !approvedEmailIndices?.has(idx)) toggleApproveEmail(idx)
    })
  }

  const canGenerate = recipients.length > 0 && canUseAi && !isGenerating
  const showZhPreview = isZhLocale && hasGeneratedContent && previewLanguage === 'zh'
  const activeTranslation = translatedEmails[activeEmailIndex]

  const exec = (command: string) => (e: React.MouseEvent) => {
    e.preventDefault()
    bodyEditorRef.current?.focus()
    document.execCommand(command, false)
    if (bodyEditorRef.current) handleRichTextBodyChange(bodyEditorRef.current.innerHTML)
  }

  return (
    <Dialog open={true} onOpenChange={(open) => !open && onClose?.()}>
      <DialogContent className="flex h-[95vh] w-full max-w-full flex-col p-0">
        <DialogHeader className="flex-shrink-0 border-b border-border px-6 py-5">
          <DialogTitle className="title-page">{title}</DialogTitle>
        </DialogHeader>

        <div className="compose" style={{ flex: 1, minHeight: 0 }}>
          {/* LEFT */}
          <aside className="compose-left">
            <div className="bulk-left">
              <RecipientList
                items={items}
                activeIndex={activeEmailIndex}
                onSelect={setActiveEmailIndex}
                approved={approvedEmailIndices ?? new Set()}
                modified={modifiedEmailIndices}
                onToggleApprove={toggleApproveEmail}
              />

              {userTemplates.length > 0 && (
                <div className="prod-disclose" data-open={selectedTemplateId ? 'true' : 'false'}>
                  <button
                    type="button"
                    className="prod-disclose-hd"
                    onClick={() => selectTemplate(selectedTemplateId ? null : userTemplates[0]?.id)}
                  >
                    <span className="tri">▸</span>
                    <span className="label">{t('composer.startFromTemplate')}</span>
                    <span className="sep">·</span>
                    <span className="count">{userTemplates.length}</span>
                  </button>
                  <div className="prod-disclose-body">
                    <select
                      value={selectedTemplateId || ''}
                      onChange={(e) => {
                        const tmpl = userTemplates.find((tmp) => tmp.id === e.target.value)
                        if (tmpl) handleTemplateCardClick(tmpl)
                        else selectTemplate(null)
                      }}
                      className="email-field"
                      style={{ borderBottom: '1px solid var(--rule)' }}
                    >
                      <option value="">{t('composer.noTemplate')}</option>
                      {userTemplates.map((tmpl) => (
                        <option key={tmpl.id} value={tmpl.id}>
                          {tmpl.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {tradeFields && (
                <FactoryDataFields
                  {...tradeFields}
                  eyebrow={t('composer.products.title')}
                />
              )}

              <div className="flex flex-col gap-1.5">
                <Label className="eyebrow-label">{t('composer.emailInstructions')}</Label>
                <Textarea
                  value={customMessage}
                  onChange={(e) => setCustomMessage(e.target.value)}
                  placeholder={t('composer.instructionsPlaceholder')}
                  rows={4}
                />
                {!canUseAi && (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {t('aiMode.aiRecipientLimit', { max: 25, count: recipients.length })}
                  </p>
                )}
              </div>

              <Button
                size="lg"
                onClick={handleGenerateEmail}
                disabled={!canGenerate}
                loading={isGenerating}
                loadingText={generationProgress || t('aiMode.generating')}
                className="w-full"
              >
                {t('composer.generateEmails')} →
              </Button>
            </div>
          </aside>

          {/* RIGHT */}
          <section className="compose-right">
            {error && (
              <div
                role="alert"
                style={{
                  margin: '12px 16px 0',
                  padding: 12,
                  border: '1px solid var(--threat)',
                  borderRadius: 6,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  color: 'var(--threat)',
                  fontSize: 13,
                }}
              >
                <AlertCircle size={16} /> {error}
              </div>
            )}
            {success && (
              <div
                style={{
                  margin: '12px 16px 0',
                  padding: 12,
                  border: '1px solid var(--accent)',
                  borderRadius: 6,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  color: 'var(--accent-hi)',
                  fontSize: 13,
                }}
              >
                <CheckCircle2 size={16} /> {success}
              </div>
            )}

            {hasGeneratedContent ? (
              <>
                {isZhLocale && (
                  <div className="preview-toolbar">
                    <div className="segmented" role="tablist" aria-label="Language">
                      <button
                        role="tab"
                        aria-selected={previewLanguage === 'zh'}
                        className={previewLanguage === 'zh' ? 'on' : ''}
                        onClick={() => setPreviewLanguage('zh')}
                      >
                        {t('compose.myEmailZh')}
                      </button>
                      <button
                        role="tab"
                        aria-selected={previewLanguage === 'preview'}
                        className={previewLanguage === 'preview' ? 'on' : ''}
                        onClick={() => setPreviewLanguage('preview')}
                      >
                        {t('compose.buyerPreview')}
                      </button>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        navigator.clipboard.writeText(
                          `Subject: ${currentSubject}\n\n${currentBody}`
                        )
                      }
                    >
                      <Copy className="mr-1 h-3 w-3" />
                      {t('composer.copy')}
                    </Button>
                  </div>
                )}

                <div className="compose-scroll">
                  <div className="email-head-row">
                    <span className="eyebrow-label">{t('composer.to')}</span>
                    <input className="email-field mono" value={currentToEmail} readOnly />
                  </div>

                  {showZhPreview ? (
                    <>
                      <div className="email-head-row stack">
                        <span className="eyebrow-label">{t('composer.subjectLabel')}</span>
                        <span className="email-field heavy">
                          {isTranslating
                            ? t('compose.translating')
                            : activeTranslation?.subject || currentSubject}
                        </span>
                      </div>
                      <div className="email-body zh">
                        {isTranslating ? (
                          <p style={{ color: 'var(--mute)' }}>{t('compose.translating')}</p>
                        ) : activeTranslation ? (
                          <SafeHtml html={activeTranslation.body.replace(/\n/g, '<br>')} />
                        ) : (
                          <p style={{ color: 'var(--mute)', fontStyle: 'italic' }}>
                            {t('compose.translationUnavailable')}
                          </p>
                        )}
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="email-head-row stack">
                        <span className="eyebrow-label">{t('composer.subjectLabel')}</span>
                        <input
                          className="email-field heavy"
                          value={currentSubject}
                          onChange={(e) => handleSubjectChange(e.target.value)}
                          onFocus={() => setInsertTarget('subject')}
                          lang="en"
                          translate="no"
                        />
                      </div>

                      <div className="compose-editor-wrap">
                        <div className="rt-toolbar">
                          <button
                            type="button"
                            className="rt-btn"
                            onMouseDown={exec('bold')}
                            aria-label={t('richTextEditor.bold')}
                            title={t('richTextEditor.bold')}
                          >
                            <Bold />
                          </button>
                          <button
                            type="button"
                            className="rt-btn"
                            onMouseDown={exec('italic')}
                            aria-label={t('richTextEditor.italic')}
                            title={t('richTextEditor.italic')}
                          >
                            <Italic />
                          </button>
                          <button
                            type="button"
                            className="rt-btn"
                            onMouseDown={exec('underline')}
                            aria-label={t('richTextEditor.underline')}
                            title={t('richTextEditor.underline')}
                          >
                            <Underline />
                          </button>
                        </div>
                        <div lang="en" translate="no">
                          <RichTextEditor
                            ref={bodyEditorRef}
                            value={currentBody}
                            onChange={handleRichTextBodyChange}
                            onFocus={() => setInsertTarget('body')}
                            placeholder={t('composer.bodyPlaceholder')}
                            hideToolbar
                            wrapperClassName=""
                            editorClassName="email-body en"
                            minHeight="300px"
                          />
                        </div>
                      </div>
                    </>
                  )}

                  <AttachmentsInline files={attachments} onChange={setAttachments} enabled={false} />
                </div>

                <ComposeFooter
                  mode="mass"
                  onCancel={onClose}
                  onSend={handleSend}
                  onSchedule={onScheduleSend}
                  sending={isSending}
                  scheduling={isScheduling}
                  approvedCount={approvedSendableCount}
                  totalCount={sendableTotal}
                  onApproveAll={toggleApproveEmail ? handleApproveAllSendable : approveAll}
                  defaultScheduleTime={defaultScheduleTime}
                />
              </>
            ) : (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 48,
                  textAlign: 'center',
                }}
              >
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: '50%',
                    background: 'var(--fog)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: 12,
                    color: 'var(--mute)',
                  }}
                >
                  <Sparkles size={24} />
                </div>
                <h3
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 20,
                    color: 'var(--deep)',
                    marginBottom: 6,
                  }}
                >
                  {t('composer.readyToGenerate')}
                </h3>
                <p style={{ fontSize: 13, color: 'var(--mute)', maxWidth: 360 }}>
                  {recipients.length === 0
                    ? t('composer.addRecipientsAbove')
                    : t('composer.clickGenerate')}
                </p>
              </div>
            )}
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default MassEmailComposerUI
