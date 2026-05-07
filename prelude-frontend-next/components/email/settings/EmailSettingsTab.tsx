'use client'

import React, { useState, useEffect, useRef } from 'react'
import { useTranslations } from 'next-intl'
import {
  CheckCircle,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  Eye,
  Save,
  Upload,
  Trash2,
  Brain,
  Pen,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { PageLoader } from '@/components/ui/page-loader'
import { useAuth } from '@/hooks/useAuth'
import { useEmailProfiles } from '@/contexts/EmailProfilesContext'
import { signatureApi, emailTrainingApi } from '@/lib/api/emailprofiles'
import { SignaturePreview } from './SignaturePreview'
import { SmtpConfigSection } from './SmtpConfigSection'
import type { SignatureFields } from '@/types/email/signature'

interface EmailSample {
  subject: string
  body: string
}

const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5MB
const VALID_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp']

function EmailSettingsTab() {
  const t = useTranslations('email')
  const tc = useTranslations('common')
  const { user } = useAuth()
  const {
    signature: cachedSignature,
    trainingSamples: cachedTraining,
    settingsLoading,
    loadSettings,
    updateSignatureCache,
    updateTrainingSamplesCache,
  } = useEmailProfiles()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const hasInitialized = useRef(false)

  // Email Personality State
  const [currentSampleIndex, setCurrentSampleIndex] = useState(0)
  const [emailSamples, setEmailSamples] = useState<EmailSample[]>([
    { subject: '', body: '' },
    { subject: '', body: '' },
    { subject: '', body: '' },
  ])
  const [sampleStatus, setSampleStatus] = useState({
    loading: false,
    error: null as string | null,
    success: false,
  })

  // Email Signature State
  const [signatureFields, setSignatureFields] = useState<SignatureFields>({})
  const [logoUploading, setLogoUploading] = useState(false)
  const [signatureLoading, setSignatureLoading] = useState(false)
  const [signatureStatus, setSignatureStatus] = useState({
    error: null as string | null,
    success: false,
  })

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  useEffect(() => {
    if (hasInitialized.current) return
    if (cachedTraining) {
      setEmailSamples([
        { subject: cachedTraining.subject1 || '', body: cachedTraining.body1 || '' },
        { subject: cachedTraining.subject2 || '', body: cachedTraining.body2 || '' },
        { subject: cachedTraining.subject3 || '', body: cachedTraining.body3 || '' },
      ])
      setSampleStatus((prev) => ({ ...prev, success: true }))
    }
    if (cachedSignature?.signatureFields) {
      setSignatureFields(cachedSignature.signatureFields)
    } else if (user?.email) {
      // First-time user post-deploy — pre-populate name and email.
      const firstName = (user as any).firstName ?? ''
      const lastName = (user as any).lastName ?? ''
      setSignatureFields({
        name: `${firstName} ${lastName}`.trim() || undefined,
        email: user.email,
      })
    }
    if (cachedTraining && cachedSignature !== undefined) {
      hasInitialized.current = true
    }
  }, [cachedTraining, cachedSignature, user])

  const handleSampleSubmit = async () => {
    const currentSample = emailSamples[currentSampleIndex]
    if (!currentSample.subject.trim() || !currentSample.body.trim()) {
      setSampleStatus({ ...sampleStatus, error: t('personality.fillBothFields') })
      return
    }
    if (currentSampleIndex < 2) {
      setCurrentSampleIndex(currentSampleIndex + 1)
      setSampleStatus({ loading: false, error: null, success: false })
    } else {
      await saveAllSamples()
    }
  }

  const saveAllSamples = async () => {
    for (let i = 0; i < 3; i++) {
      if (!emailSamples[i].subject.trim() || !emailSamples[i].body.trim()) {
        setSampleStatus({
          loading: false,
          error: t('personality.completeSample', { index: i + 1 }),
          success: false,
        })
        return
      }
    }
    if (!user?.email) return
    setSampleStatus({ loading: true, error: null, success: false })
    try {
      const samplesData = {
        subject1: emailSamples[0].subject,
        body1: emailSamples[0].body,
        subject2: emailSamples[1].subject,
        body2: emailSamples[1].body,
        subject3: emailSamples[2].subject,
        body3: emailSamples[2].body,
      }
      await emailTrainingApi.saveTrainingSamples(samplesData)
      updateTrainingSamplesCache(samplesData)
      setSampleStatus({ loading: false, error: null, success: true })
    } catch (error) {
      setSampleStatus({
        loading: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        success: false,
      })
    }
  }

  const handleSampleChange = (field: keyof EmailSample, value: string) => {
    const newSamples = [...emailSamples]
    newSamples[currentSampleIndex][field] = value
    setEmailSamples(newSamples)
  }

  const handleEditSample = (index: number) => {
    setCurrentSampleIndex(index)
    setSampleStatus({ ...sampleStatus, success: false })
  }

  const uploadLogo = async (file: File) => {
    if (!VALID_IMAGE_TYPES.includes(file.type)) {
      setSignatureStatus({ error: t('signatureSettings.invalidImageType'), success: false })
      return
    }
    if (file.size > MAX_FILE_SIZE) {
      setSignatureStatus({ error: t('signatureSettings.fileTooLarge'), success: false })
      return
    }
    if (!user?.email) return
    setLogoUploading(true)
    try {
      const data = await signatureApi.uploadLogo(file)
      setSignatureFields((prev) => ({ ...prev, logoUrl: data.logoUrl }))
      setSignatureStatus({ error: null, success: true })
      setTimeout(() => setSignatureStatus({ error: null, success: false }), 3000)
    } catch (e) {
      setSignatureStatus({
        error: e instanceof Error ? e.message : t('signatureSettings.failedToUpload'),
        success: false,
      })
    } finally {
      setLogoUploading(false)
    }
  }

  const handleRemoveLogo = () => {
    setSignatureFields((prev) => ({ ...prev, logoUrl: undefined }))
  }

  const saveSignature = async () => {
    if (!user?.email) return
    setSignatureLoading(true)
    setSignatureStatus({ error: null, success: false })
    try {
      const updated = await signatureApi.patchSignature(signatureFields)
      setSignatureFields(updated.signatureFields)
      updateSignatureCache(updated)
      setSignatureStatus({ error: null, success: true })
      setTimeout(() => setSignatureStatus({ error: null, success: false }), 3000)
    } catch (e) {
      setSignatureStatus({
        error: e instanceof Error ? e.message : t('signatureSettings.failedToSave'),
        success: false,
      })
    } finally {
      setSignatureLoading(false)
    }
  }

  const isLoading = signatureLoading || logoUploading

  if (settingsLoading && !cachedSignature && !cachedTraining) {
    return (
      <div className="flex h-full items-center justify-center">
        <PageLoader label={t('settingsTab.loadingPreferences')} />
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-10 px-8 py-8">
        {/* ─── Section 1: Email Personality Training ─── */}
        <section>
          <div className="mb-1 flex items-center gap-3">
            <Brain className="h-5 w-5 text-mute" />
            <h2 className="title-panel">
              {t('personality.title')}
            </h2>
          </div>
          <p className="mb-5 ml-8 text-xs text-mute">
            {t('personality.trainedDescription')}
          </p>

          {sampleStatus.success ? (
            <div className="ml-8 space-y-3">
              {/* Status + Update button */}
              <div className="mb-1 flex items-center justify-between">
                <Badge className="border-0 bg-emerald-50 text-xs text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                  <CheckCircle className="mr-1 h-3 w-3" />
                  {t('personality.trainedBadge')}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSampleStatus({ ...sampleStatus, success: false })}
                  className="h-7 text-xs text-mute"
                >
                  <Pen className="mr-1.5 h-3 w-3" />
                  {t('personality.updateButton')}
                </Button>
              </div>

              {/* Saved samples list */}
              {emailSamples.map((sample, index) => (
                <div
                  key={index}
                  onClick={() => handleEditSample(index)}
                  className="group flex cursor-pointer items-center justify-between rounded-lg border border-rule px-4 py-3 transition-colors hover:border-ink"
                >
                  <div className="min-w-0 flex-1">
                    <div className="mb-0.5 flex items-center gap-2">
                      <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-mute">
                        {t('personality.sampleProgress', { current: index + 1, total: 3 })}
                      </span>
                    </div>
                    <p className="truncate text-sm text-ink">
                      {sample.subject || t('personality.noSubject')}
                    </p>
                  </div>
                  <Eye className="ml-3 h-3.5 w-3.5 flex-shrink-0 text-mute opacity-0 transition-opacity group-hover:opacity-100" />
                </div>
              ))}
            </div>
          ) : (
            <div className="ml-8 space-y-5">
              {/* Progress bar */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-medium text-ink">
                    {t('personality.sampleProgress', { current: currentSampleIndex + 1, total: 3 })}
                  </span>
                  <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
                    {currentSampleIndex === 0 && t('personality.gettingStarted')}
                    {currentSampleIndex === 1 && t('personality.oneMoreToGo')}
                    {currentSampleIndex === 2 && t('personality.lastOne')}
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-rule">
                  <div
                    className="h-1.5 rounded-full bg-deep transition-all duration-300"
                    style={{ width: `${((currentSampleIndex + 1) / 3) * 100}%` }}
                  />
                </div>
              </div>

              {/* Sample form */}
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium text-mute">
                    {t('personality.emailSubject')}
                  </Label>
                  <Input
                    value={emailSamples[currentSampleIndex].subject}
                    onChange={(e) => handleSampleChange('subject', e.target.value)}
                    placeholder={t('personality.subjectPlaceholder')}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium text-mute">
                    {t('personality.emailBody')}
                  </Label>
                  <textarea
                    value={emailSamples[currentSampleIndex].body}
                    onChange={(e) => handleSampleChange('body', e.target.value)}
                    placeholder={t('personality.bodyPlaceholder')}
                    rows={8}
                    className="w-full resize-none rounded-lg border border-rule bg-bone px-3.5 py-2.5 text-sm text-ink transition-all placeholder:text-mute focus:border-ink focus:ring-1 focus:ring-ink focus:outline-none"
                  />
                </div>

                {sampleStatus.error && (
                  <div className="flex items-center gap-2 text-xs text-threat">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {sampleStatus.error}
                  </div>
                )}

                <div className="flex items-center justify-between pt-1">
                  {currentSampleIndex > 0 ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCurrentSampleIndex(currentSampleIndex - 1)}
                      disabled={sampleStatus.loading}
                      className="text-xs"
                    >
                      <ChevronDown className="mr-1 h-3.5 w-3.5 rotate-90" />
                      {tc('previous')}
                    </Button>
                  ) : (
                    <div />
                  )}
                  <Button
                    size="sm"
                    onClick={handleSampleSubmit}
                    loading={sampleStatus.loading}
                    loadingText={t('personality.saving')}
                    className="text-xs"
                  >
                    {currentSampleIndex < 2 ? (
                      <>
                        {t('personality.saveContinue')}{' '}
                        <ChevronRight className="ml-1 h-3.5 w-3.5" />
                      </>
                    ) : (
                      <>
                        <CheckCircle className="mr-2 h-3.5 w-3.5" />{' '}
                        {t('personality.completeTraining')}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Divider */}
        <hr className="border-rule" />

        {/* ─── Section 2: Email Signature ─── */}
        <section>
          <div className="mb-1 flex items-center gap-3">
            <Pen className="h-5 w-5 text-mute" />
            <h2 className="title-panel">
              {t('signatureSettings.title')}
            </h2>
          </div>
          <p className="mb-5 ml-8 text-xs text-mute">
            {t('signatureSettings.preview')}
          </p>

          <div className="ml-8 space-y-6">
            {/* Redesign banner — shown when no signature has been saved */}
            {!cachedSignature && (
              <div className="banner-warn rounded-lg border p-4">
                <p className="text-xs font-medium">
                  {t('signatureSettings.redesignBanner')}
                </p>
              </div>
            )}

            {/* Structured field inputs */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs font-medium text-mute">
                  {t('signatureSettings.fields.name')}
                </Label>
                <Input
                  value={signatureFields.name ?? ''}
                  onChange={(e) =>
                    setSignatureFields((p) => ({ ...p, name: e.target.value || undefined }))
                  }
                  placeholder={t('signatureSettings.fields.namePlaceholder')}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium text-mute">
                  {t('signatureSettings.fields.title')}
                </Label>
                <Input
                  value={signatureFields.title ?? ''}
                  onChange={(e) =>
                    setSignatureFields((p) => ({ ...p, title: e.target.value || undefined }))
                  }
                  placeholder={t('signatureSettings.fields.titlePlaceholder')}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium text-mute">
                  {t('signatureSettings.fields.email')}
                </Label>
                <Input
                  type="email"
                  value={signatureFields.email ?? ''}
                  onChange={(e) =>
                    setSignatureFields((p) => ({ ...p, email: e.target.value || undefined }))
                  }
                  placeholder={t('signatureSettings.fields.emailPlaceholder')}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium text-mute">
                  {t('signatureSettings.fields.phone')}
                </Label>
                <Input
                  type="tel"
                  value={signatureFields.phoneNumber ?? ''}
                  onChange={(e) =>
                    setSignatureFields((p) => ({ ...p, phoneNumber: e.target.value || undefined }))
                  }
                  placeholder={t('signatureSettings.fields.phonePlaceholder')}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium text-mute">
                  {t('signatureSettings.fields.location')}
                </Label>
                <Input
                  value={signatureFields.location ?? ''}
                  onChange={(e) =>
                    setSignatureFields((p) => ({ ...p, location: e.target.value || undefined }))
                  }
                  placeholder={t('signatureSettings.fields.locationPlaceholder')}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium text-mute">
                  {t('signatureSettings.fields.link')}
                </Label>
                <Input
                  type="url"
                  value={signatureFields.link ?? ''}
                  onChange={(e) =>
                    setSignatureFields((p) => ({ ...p, link: e.target.value || undefined }))
                  }
                  placeholder={t('signatureSettings.fields.linkPlaceholder')}
                />
              </div>
            </div>

            {/* Logo upload */}
            <div className="space-y-2">
              <Label className="text-xs font-medium text-mute">
                {t('signatureSettings.logoLabel')}
              </Label>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && uploadLogo(e.target.files[0])}
              />
              <div className="flex items-center gap-3">
                {signatureFields.logoUrl && (
                  <div className="rounded-lg border border-rule bg-bone p-2">
                    <img
                      src={signatureFields.logoUrl}
                      alt="Signature logo"
                      className="h-10 w-auto object-contain"
                    />
                  </div>
                )}
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isLoading}
                    className="h-7 text-xs"
                  >
                    <Upload className="mr-1.5 h-3 w-3" />
                    {signatureFields.logoUrl
                      ? t('signatureSettings.changeLogo')
                      : t('signatureSettings.uploadLogo')}
                  </Button>
                  {signatureFields.logoUrl && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleRemoveLogo}
                      disabled={isLoading}
                      className="h-7 text-xs text-threat hover:bg-threat/10 hover:text-threat"
                    >
                      <Trash2 className="mr-1.5 h-3 w-3" />
                      {t('signatureSettings.removeLogo')}
                    </Button>
                  )}
                </div>
              </div>
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
                {t('signatureSettings.supportedFormats')}
              </p>
            </div>

            {/* Live preview */}
            <SignaturePreview fields={signatureFields} />

            {/* Status messages */}
            {signatureStatus.success && (
              <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--accent)' }}>
                <CheckCircle className="h-3.5 w-3.5" />
                <span className="font-medium">{t('signatureSettings.savedSuccess')}</span>
              </div>
            )}
            {signatureStatus.error && (
              <div className="flex items-center gap-2 text-xs text-threat">
                <AlertTriangle className="h-3.5 w-3.5" />
                <span className="font-medium">{signatureStatus.error}</span>
              </div>
            )}

            <Button
              onClick={saveSignature}
              loading={signatureLoading}
              loadingText={t('signatureSettings.savingButton')}
              size="sm"
              className="text-xs"
            >
              <Save className="mr-1.5 h-3.5 w-3.5" />
              {t('signatureSettings.saveButton')}
            </Button>
          </div>
        </section>

        {/* ─── Section 3: SMTP / Custom Email Configuration ─── */}
        <section>
          <SmtpConfigSection />
        </section>
      </div>
    </div>
  )
}

export default EmailSettingsTab
