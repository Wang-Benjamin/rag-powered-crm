'use client'

/**
 * V2 single-email composer — `.compose` two-pane shell.
 *
 * Behavior is preserved from the legacy version:
 *   - Bilingual toggle: 'preview' = English (editable), 'zh' = Chinese back-
 *     translation (read-only via SafeHtml).
 *   - Generation increments translationVersionRef so any in-flight translation
 *     fetch is discarded; cache invalidates on next toggle.
 *   - Schedule popover and DirectScheduleSendButton wrapper retained.
 *
 * Visual surface follows tests/Buyer detail.html (compose markup ~lines
 * 2500-2620). Class names match the HTML mock; styles live in compose.css.
 *
 * Phase-1 inert features:
 *   - Attachments rendered, drop-zone disabled (`enabled={false}`); not sent.
 *   - CC/BCC ghost buttons are visible but non-functional (state captured
 *     locally, not sent).
 *   - Tracking pills disabled with "Coming soon" tooltip.
 */

import './compose.css'
import React, { useEffect, useRef, useState } from 'react'
import { Mail, AlertCircle, Copy, Bold, Italic, Underline } from 'lucide-react'
import { toast } from 'sonner'
import { useTranslations, useLocale } from 'next-intl'
import { SafeHtml } from '@/components/ui/safe-html'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { ReplyContext } from '@/types/email'
import RichTextEditor from './RichTextEditor'
import FactoryDataFields from './EmailContextFields'
import AttachmentsInline from './AttachmentsInline'
import ComposeFooter from './ComposeFooter'

export interface GeneratedEmailResult {
  subject: string
  body: string
}

export interface SavedTemplateForComposer {
  id: string
  name: string
  subject: string
  body: string
  description?: string
  promptInstructions?: string
}

export interface FactoryDataProps {
  products: { name: string; fobPrice: string; landedPrice: string }[]
  certifications: string[]
  moq: string
  leadTime: string
  sampleStatus?: '' | 'ready' | 'in_production' | 'free_sample'
  onProductsChange: (v: { name: string; fobPrice: string; landedPrice: string }[]) => void
  onCertificationsChange: (v: string[]) => void
  onMoqChange: (v: string) => void
  onLeadTimeChange: (v: string) => void
  onSampleStatusChange?: (v: '' | 'ready' | 'in_production' | 'free_sample') => void
}

export interface EmailComposerProps {
  entityType: 'customer' | 'lead'
  entityId: string
  entityEmail: string
  entityName: string
  onGenerateEmail: (
    prompt: string,
    templateId?: string | null,
    factoryData?: Record<string, any>
  ) => Promise<GeneratedEmailResult>
  onSendEmail: (
    toEmail: string,
    subject: string,
    body: string,
    replyContext?: ReplyContext
  ) => Promise<void>
  onScheduleSend?: (scheduledAt: string, toEmail: string, subject: string, body: string) => Promise<void>
  onClose: () => void
  onEmailSent?: (data: any) => void
  embedded?: boolean
  userTemplates?: SavedTemplateForComposer[]
  factoryData?: FactoryDataProps
  /** Optional preset for the schedule popover's datetime picker. */
  defaultScheduleTime?: string
}

interface EmailForm {
  message: string
  generatedEmail: { subject: string; body: string; to: string } | null
  editedTo: string
  editedSubject: string
  editedBody: string
}

const EmailComposer: React.FC<EmailComposerProps> = ({
  entityType,
  entityEmail,
  entityName,
  onGenerateEmail,
  onSendEmail,
  onScheduleSend,
  onClose,
  onEmailSent,
  embedded = false,
  userTemplates = [],
  factoryData,
  defaultScheduleTime,
}) => {
  const t = useTranslations('email')
  const locale = useLocale()
  const isZhLocale = locale.startsWith('zh')

  const [previewLanguage, setPreviewLanguage] = useState<'zh' | 'preview'>('preview')
  const [translatedEmail, setTranslatedEmail] = useState<{ subject: string; body: string } | null>(
    null
  )
  const [isTranslating, setIsTranslating] = useState(false)
  const translationVersionRef = useRef(0)
  const translatedAtVersionRef = useRef(0)

  const [emailForm, setEmailForm] = useState<EmailForm>({
    message: '',
    generatedEmail: null,
    editedTo: '',
    editedSubject: '',
    editedBody: '',
  })
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [isScheduling, setIsScheduling] = useState(false)
  const [replyContext] = useState<ReplyContext | null>(null)

  const bodyEditorRef = useRef<HTMLDivElement>(null)

  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)

  // Phase 1 inert: attachments captured locally but never sent.
  const [attachments, setAttachments] = useState<File[]>([])

  // CC/BCC: state captured for future backend wire-up; not in payload yet.
  const [ccOpen, setCcOpen] = useState(false)
  const [bccOpen, setBccOpen] = useState(false)
  const [cc, setCc] = useState('')
  const [bcc, setBcc] = useState('')

  const validateEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

  const handleEditedEmailChange = (updates: Partial<EmailForm>) => {
    setEmailForm((prev) => ({ ...prev, ...updates }))
    if ('editedSubject' in updates || 'editedBody' in updates) {
      translationVersionRef.current++
    }
  }

  const translateCurrentEmail = async (subject: string, body: string) => {
    if (translatedEmail && translatedAtVersionRef.current === translationVersionRef.current) return
    const version = ++translationVersionRef.current
    try {
      setIsTranslating(true)
      const { translateEmailContent } = await import('@/lib/i18n/translate-email')
      const { subjectZh, bodyZh } = await translateEmailContent(subject, body)
      if (translationVersionRef.current === version) {
        setTranslatedEmail({ subject: subjectZh, body: bodyZh })
        translatedAtVersionRef.current = version
      }
    } catch (err) {
      console.warn('Translation failed:', err)
    } finally {
      if (translationVersionRef.current === version) setIsTranslating(false)
    }
  }

  const generateEmail = async () => {
    setIsGenerating(true)
    try {
      const validProducts =
        factoryData?.products?.filter((p) => p.name || p.fobPrice || p.landedPrice) || []
      const factoryFields = factoryData
        ? {
            products: validProducts.length ? validProducts : undefined,
            certifications: factoryData.certifications?.length
              ? factoryData.certifications
              : undefined,
            moq: factoryData.moq || undefined,
            leadTime: factoryData.leadTime || undefined,
            sampleStatus: factoryData.sampleStatus || undefined,
          }
        : undefined

      const result = await onGenerateEmail(emailForm.message, selectedTemplateId, factoryFields)
      const fallbackSubject = `Regarding ${entityName}`
      const subject = result.subject || fallbackSubject
      const body = result.body || ''

      setEmailForm({
        ...emailForm,
        generatedEmail: { subject, body, to: entityEmail },
        editedTo: entityEmail,
        editedSubject: subject,
        editedBody: body,
      })
      if (isZhLocale) {
        setPreviewLanguage('preview')
        setTranslatedEmail(null)
      }
    } catch (error: any) {
      toast.error(t('composer.error'), {
        description: error.message || t('composer.generateFailed'),
      })
    } finally {
      setIsGenerating(false)
    }
  }

  const sendEmail = async () => {
    if (!emailForm.generatedEmail) {
      toast.error(t('composer.error'), { description: t('composer.generateFirst') })
      return
    }
    if (!validateEmail(emailForm.editedTo)) {
      toast.error(t('composer.error'), { description: t('composer.invalidEmail') })
      return
    }
    if (!emailForm.editedSubject.trim() || !emailForm.editedBody.trim()) {
      toast.error(t('composer.error'), { description: t('composer.subjectBodyRequired') })
      return
    }
    setIsSending(true)
    try {
      // Phase 1: attachments + cc + bcc captured locally but NOT sent.
      // See docs/leadgen/email-attachments-plan.md for the deferred wiring.
      await onSendEmail(
        emailForm.editedTo,
        emailForm.editedSubject,
        emailForm.editedBody,
        replyContext || undefined
      )
      toast(t('composer.success'), {
        description: t('composer.emailSentTo', { email: emailForm.editedTo }),
      })
      onEmailSent?.({ sentTo: emailForm.editedTo })
      onClose()
    } catch (error: any) {
      toast.error(t('composer.error'), { description: error.message || t('composer.sendFailed') })
    } finally {
      setIsSending(false)
    }
  }

  const handleSchedule = async (scheduledAt: string) => {
    if (!emailForm.generatedEmail) return
    if (!validateEmail(emailForm.editedTo)) {
      toast.error(t('composer.error'), { description: t('composer.invalidEmail') })
      return
    }
    if (!emailForm.editedSubject.trim() || !emailForm.editedBody.trim()) {
      toast.error(t('composer.error'), { description: t('composer.subjectBodyRequired') })
      return
    }
    setIsScheduling(true)
    try {
      await onScheduleSend!(
        scheduledAt,
        emailForm.editedTo,
        emailForm.editedSubject,
        emailForm.editedBody
      )
      toast(t('composer.scheduled'), {
        description: t('composer.emailSentTo', { email: emailForm.editedTo }),
      })
      onClose()
    } catch (error: any) {
      toast.error(t('composer.error'), { description: error.message || t('composer.scheduleFailed') })
    } finally {
      setIsScheduling(false)
    }
  }

  const copyToClipboard = () => {
    navigator.clipboard.writeText(`Subject: ${emailForm.editedSubject}\n\n${emailForm.editedBody}`)
    toast(t('composer.copied'), { description: t('composer.copiedDescription') })
  }

  const validProducts =
    factoryData?.products?.filter((p) => p.name || p.fobPrice || p.landedPrice) || []
  const canGenerate =
    !!entityEmail &&
    !isGenerating &&
    (emailForm.message.trim() || selectedTemplateId || validProducts.length > 0)
  const hasEmail = !!emailForm.generatedEmail

  // External RT toolbar buttons act on the body editor via execCommand.
  const exec = (command: string) => (e: React.MouseEvent) => {
    e.preventDefault()
    bodyEditorRef.current?.focus()
    document.execCommand(command, false)
    if (bodyEditorRef.current) {
      handleEditedEmailChange({ editedBody: bodyEditorRef.current.innerHTML })
    }
  }

  // Trigger zh translation when toggling to it after generation.
  useEffect(() => {
    if (
      previewLanguage === 'zh' &&
      hasEmail &&
      isZhLocale &&
      emailForm.editedSubject &&
      emailForm.editedBody
    ) {
      translateCurrentEmail(emailForm.editedSubject, emailForm.editedBody)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewLanguage, hasEmail])

  const showZhPreview = isZhLocale && hasEmail && previewLanguage === 'zh'

  const content = (
    <div className="compose">
      {/* LEFT: parameters */}
      <aside className="compose-left">
        <div className="bulk-left">
          {/* No recipient chip — recipient identity lives in drawer header + To row */}

          {userTemplates.length > 0 && (
            <div className="prod-disclose" data-open={selectedTemplateId ? 'true' : 'false'}>
              <button
                type="button"
                className="prod-disclose-hd"
                onClick={() =>
                  setSelectedTemplateId((id) => (id ? null : userTemplates[0]?.id ?? null))
                }
              >
                <span className="tri">▸</span>
                <span className="label">{t('composer.startFromTemplate')}</span>
                <span className="sep">·</span>
                <span className="count">{userTemplates.length}</span>
              </button>
              <div className="prod-disclose-body">
                <select
                  value={selectedTemplateId ?? ''}
                  onChange={(e) => setSelectedTemplateId(e.target.value || null)}
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

          {factoryData && (
            <FactoryDataFields
              variant="trade"
              eyebrow={t('composer.products.title')}
              products={factoryData.products}
              certifications={factoryData.certifications}
              moq={factoryData.moq}
              leadTime={factoryData.leadTime}
              sampleStatus={factoryData.sampleStatus}
              onProductsChange={factoryData.onProductsChange}
              onCertificationsChange={factoryData.onCertificationsChange}
              onMoqChange={factoryData.onMoqChange}
              onLeadTimeChange={factoryData.onLeadTimeChange}
              onSampleStatusChange={factoryData.onSampleStatusChange}
            />
          )}

          <div className="flex flex-col gap-1.5">
            <Label className="eyebrow-label">{t('composer.emailInstructions')}</Label>
            <Textarea
              placeholder={t('composer.instructionsPlaceholder')}
              value={emailForm.message}
              onChange={(e) => setEmailForm({ ...emailForm, message: e.target.value })}
              rows={4}
            />
          </div>

          {!entityEmail && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 12,
                color: 'var(--threat)',
              }}
            >
              <AlertCircle size={14} />
              {t('composer.noEmailFound', { entityType })}
            </div>
          )}

          <Button
            size="lg"
            onClick={generateEmail}
            disabled={!canGenerate}
            loading={isGenerating}
            loadingText={t('composer.generatingEmail')}
            className="w-full"
          >
            {t('composer.generateWithAi')} →
          </Button>
        </div>
      </aside>

      {/* RIGHT: editor + preview */}
      <section className="compose-right">
        {hasEmail ? (
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
                <Button variant="ghost" size="sm" onClick={copyToClipboard}>
                  <Copy className="mr-1 h-3 w-3" />
                  {t('composer.copy')}
                </Button>
              </div>
            )}
            {!isZhLocale && (
              <div className="preview-toolbar">
                <span />
                <Button variant="ghost" size="sm" onClick={copyToClipboard}>
                  <Copy className="mr-1 h-3 w-3" />
                  {t('composer.copy')}
                </Button>
              </div>
            )}

            <div className="compose-scroll">
              <div className="email-head-row">
                <span className="eyebrow-label">{t('composer.to')}</span>
                <input
                  className="email-field"
                  type="email"
                  value={emailForm.editedTo}
                  onChange={(e) => setEmailForm({ ...emailForm, editedTo: e.target.value })}
                />
                <span className="cc-row">
                  <Button variant="ghost" size="sm" onClick={() => setCcOpen((v) => !v)}>
                    {t('composer.head.cc')}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setBccOpen((v) => !v)}>
                    {t('composer.head.bcc')}
                  </Button>
                </span>
              </div>
              {ccOpen && (
                <div className="cc-bcc-input-row">
                  <span className="eyebrow-label">{t('composer.head.cc')}</span>
                  <input className="email-field" value={cc} onChange={(e) => setCc(e.target.value)} />
                </div>
              )}
              {bccOpen && (
                <div className="cc-bcc-input-row">
                  <span className="eyebrow-label">{t('composer.head.bcc')}</span>
                  <input
                    className="email-field"
                    value={bcc}
                    onChange={(e) => setBcc(e.target.value)}
                  />
                </div>
              )}

              <div className="email-head-row stack">
                <span className="eyebrow-label">{t('composer.subjectLabel')}</span>
                <input
                  className="email-field heavy"
                  value={emailForm.editedSubject}
                  onChange={(e) => handleEditedEmailChange({ editedSubject: e.target.value })}
                />
              </div>

              {/* Body — zh is read-only (SafeHtml); preview is editable RichTextEditor.
                  RT toolbar visibility driven by .compose-editor-wrap:focus-within. */}
              {showZhPreview ? (
                <div className="email-body zh">
                  {isTranslating ? (
                    <p style={{ color: 'var(--mute)' }}>{t('compose.translating')}</p>
                  ) : translatedEmail ? (
                    <SafeHtml html={translatedEmail.body.replace(/\n/g, '<br>')} />
                  ) : (
                    <p style={{ color: 'var(--mute)', fontStyle: 'italic' }}>
                      {t('compose.translationUnavailable')}
                    </p>
                  )}
                </div>
              ) : (
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
                  <RichTextEditor
                    ref={bodyEditorRef}
                    value={emailForm.editedBody}
                    onChange={(html) => handleEditedEmailChange({ editedBody: html })}
                    placeholder={t('composer.emailContentPlaceholder')}
                    hideToolbar
                    wrapperClassName=""
                    editorClassName="email-body en"
                    minHeight="320px"
                  />
                </div>
              )}

              <AttachmentsInline files={attachments} onChange={setAttachments} enabled={false} />
            </div>

            <ComposeFooter
              mode="single"
              onCancel={onClose}
              onSend={sendEmail}
              onSchedule={onScheduleSend ? handleSchedule : undefined}
              sending={isSending}
              scheduling={isScheduling}
              disabled={!entityEmail}
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
                width: 64,
                height: 64,
                borderRadius: '50%',
                background: 'var(--fog)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 16,
                color: 'var(--mute)',
              }}
            >
              <Mail size={28} />
            </div>
            <h3
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 22,
                color: 'var(--deep)',
                marginBottom: 8,
              }}
            >
              {t('composer.generateYourEmail')}
            </h3>
            <p style={{ fontSize: 13, color: 'var(--mute)', maxWidth: 380 }}>
              {t('composer.generateYourEmailHint')}
            </p>
          </div>
        )}
      </section>
    </div>
  )

  if (embedded) return content

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        className="mx-4 max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-lg shadow-xl"
        style={{ background: 'var(--paper)' }}
      >
        {content}
      </div>
    </div>
  )
}

export default EmailComposer
