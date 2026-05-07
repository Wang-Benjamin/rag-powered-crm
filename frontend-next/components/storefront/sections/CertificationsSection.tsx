'use client'

import { useCallback, useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { settingsApiClient } from '@/lib/api/client'
import { ingestionApi } from '@/lib/api/ingestion'
import { AutofilledFieldHighlight } from '@/components/onboarding/customize-ai/ingestion/AutofilledFieldHighlight'
import { DocumentDropzone } from '@/components/onboarding/customize-ai/ingestion/DocumentDropzone'
import type {
  CertificationDraft,
  DraftPayload,
} from '@/components/onboarding/customize-ai/ingestion/types'
import { Field, FieldRow, SectionShell, TextInput } from '../primitives'

interface SavedCert {
  certId: string
  certType: string
  issuingBody: string
  expiryDate: string
  status: string
  documentUrl: string | null
}

const CERT_TYPE_OPTIONS = [
  'ISO 9001',
  'ISO 14001',
  'ISO 45001',
  'CE',
  'UL',
  'RoHS',
  'REACH',
  'BSCI',
  'SA8000',
  'Other',
]

const NEW_CERT_DEFAULTS = { certType: 'ISO 9001', issuingBody: '', expiryDate: '' }

export function CertificationsSection() {
  const t = useTranslations('storefront')
  const [savedCerts, setSavedCerts] = useState<SavedCert[]>([])
  const [showAddCert, setShowAddCert] = useState(false)
  const [newCert, setNewCert] = useState(NEW_CERT_DEFAULTS)
  const [addingCert, setAddingCert] = useState(false)
  const [certIngestionFile, setCertIngestionFile] = useState<File | null>(null)
  const [certIngestionJobId, setCertIngestionJobId] = useState<string | null>(null)
  const [certIngestionDraft, setCertIngestionDraft] = useState<CertificationDraft | null>(null)
  const [certAutofilledKeys, setCertAutofilledKeys] = useState<Set<string>>(new Set())

  const fetchCerts = useCallback(async () => {
    try {
      const res = await settingsApiClient.get<{ certifications: SavedCert[] }>('/certifications')
      setSavedCerts(res?.certifications || [])
    } catch {
      /* certs are optional — silent on initial-load failure */
    }
  }, [])

  useEffect(() => {
    fetchCerts()
  }, [fetchCerts])

  const updateCert = (updates: Partial<typeof newCert>) => {
    setNewCert((prev) => ({ ...prev, ...updates }))
    setCertAutofilledKeys((prev) => {
      if (prev.size === 0) return prev
      let next: Set<string> | null = null
      for (const key of Object.keys(updates)) {
        if (prev.has(key)) {
          if (!next) next = new Set(prev)
          next.delete(key)
        }
      }
      return next ?? prev
    })
  }

  const resetCertIngestion = () => {
    setCertIngestionJobId(null)
    setCertIngestionDraft(null)
    setCertIngestionFile(null)
    setCertAutofilledKeys(new Set())
  }

  const handleCertIngestionReady = (payload: DraftPayload, jobId: string) => {
    const draft = payload as CertificationDraft
    setCertIngestionJobId(jobId)
    setCertIngestionDraft(draft)

    const updates: Partial<typeof newCert> = {}
    const touched = new Set<string>()
    if (draft.certType) {
      const match = CERT_TYPE_OPTIONS.find(
        (opt) => opt.toLowerCase() === draft.certType!.toLowerCase()
      )
      // Unknown codes fall back to Other so the <select> can render the value.
      updates.certType = match ?? 'Other'
      touched.add('certType')
    }
    if (draft.issuingBody) {
      updates.issuingBody = draft.issuingBody
      touched.add('issuingBody')
    }
    if (draft.expiryDate) {
      updates.expiryDate = draft.expiryDate
      touched.add('expiryDate')
    }
    setNewCert((prev) => ({ ...prev, ...updates }))
    setCertAutofilledKeys(touched)
    setShowAddCert(true)
  }

  const handleIngestionFailed = (message: string) => {
    toast.error(message)
  }

  const handleAddCert = async () => {
    if (!newCert.issuingBody) {
      toast.error(t('certifications.issuingBodyRequired'))
      return
    }
    try {
      setAddingCert(true)
      const formData = new FormData()
      formData.append('cert_type', newCert.certType)
      formData.append('issuing_body', newCert.issuingBody)
      if (newCert.expiryDate) formData.append('expiry_date', newCert.expiryDate)
      if (certIngestionFile) formData.append('file', certIngestionFile)
      await settingsApiClient.upload('/certifications', formData)
      if (certIngestionJobId) {
        try {
          await ingestionApi.commit(
            certIngestionJobId,
            (certIngestionDraft ?? {}) as DraftPayload
          )
        } catch (e) {
          // Bookkeeping commit is best-effort — the authoritative write
          // (POST /certifications) already succeeded.
          console.warn('ingestion commit (cert) failed:', e)
        }
      }
      setNewCert(NEW_CERT_DEFAULTS)
      resetCertIngestion()
      setShowAddCert(false)
      await fetchCerts()
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : t('certifications.addFailed')
      toast.error(message)
    } finally {
      setAddingCert(false)
    }
  }

  const handleDeleteCert = async (certId: string) => {
    try {
      await settingsApiClient.delete(`/certifications/${certId}`)
      setSavedCerts((prev) => prev.filter((c) => c.certId !== certId))
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : t('certifications.deleteFailed')
      toast.error(message)
    }
  }

  const handleCancelAdd = () => {
    setShowAddCert(false)
    setNewCert(NEW_CERT_DEFAULTS)
    resetCertIngestion()
  }

  return (
    <SectionShell title={t('certifications.sectionTitle')}>
      <p className="mb-2 text-xs text-zinc-500">{t('certifications.dropHelper')}</p>
      <DocumentDropzone
        kind="certification"
        accept="application/pdf,.pdf,image/png,.png,image/jpeg,.jpg,.jpeg"
        acceptLabel="PDF / PNG / JPG"
        maxSizeMB={50}
        label={t('certifications.dropLabel')}
        onReady={handleCertIngestionReady}
        onFailed={handleIngestionFailed}
        onFileStaged={setCertIngestionFile}
      />

      <div className="mt-4 flex items-center justify-between">
        <span className="text-xs font-medium text-zinc-700">
          {t('certifications.savedHeading')}
        </span>
        <button
          type="button"
          onClick={() => setShowAddCert((v) => !v)}
          className="inline-flex items-center gap-1 text-xs font-medium text-zinc-500 hover:text-zinc-900"
        >
          <Plus className="h-3 w-3" /> {t('certifications.add')}
        </button>
      </div>

      {showAddCert && (
        <div className="mt-3 space-y-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3">
          <FieldRow>
            <Field label={t('certifications.fields.certType')} htmlFor="cert-type">
              <AutofilledFieldHighlight active={certAutofilledKeys.has('certType')}>
                <select
                  id="cert-type"
                  value={newCert.certType}
                  onChange={(e) => updateCert({ certType: e.target.value })}
                  className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-zinc-400 focus:ring-2 focus:ring-zinc-900 focus:outline-none"
                >
                  {CERT_TYPE_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </AutofilledFieldHighlight>
            </Field>
            <Field label={t('certifications.fields.issuingBody')} htmlFor="cert-issuer">
              <AutofilledFieldHighlight active={certAutofilledKeys.has('issuingBody')}>
                <TextInput
                  id="cert-issuer"
                  value={newCert.issuingBody}
                  onChange={(e) => updateCert({ issuingBody: e.target.value })}
                  placeholder={t('certifications.fields.issuingBodyPlaceholder')}
                />
              </AutofilledFieldHighlight>
            </Field>
            <Field label={t('certifications.fields.expiryDate')} htmlFor="cert-expiry">
              <AutofilledFieldHighlight active={certAutofilledKeys.has('expiryDate')}>
                <TextInput
                  id="cert-expiry"
                  type="date"
                  value={newCert.expiryDate}
                  onChange={(e) => updateCert({ expiryDate: e.target.value })}
                />
              </AutofilledFieldHighlight>
            </Field>
          </FieldRow>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleAddCert}
              disabled={addingCert || !newCert.issuingBody}
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-50"
            >
              {addingCert ? t('certifications.adding') : t('certifications.save')}
            </button>
            <button
              type="button"
              onClick={handleCancelAdd}
              className="px-3 py-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-900"
            >
              {t('certifications.cancel')}
            </button>
          </div>
        </div>
      )}

      {savedCerts.length > 0 ? (
        <ul className="mt-3 space-y-1.5">
          {savedCerts.map((cert) => (
            <li
              key={cert.certId}
              className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white px-3 py-2"
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="text-xs font-medium text-zinc-900">{cert.certType}</span>
                <span className="text-[10px] text-zinc-500">{cert.issuingBody}</span>
                {cert.expiryDate && (
                  <span className="text-[10px] text-zinc-500">
                    {new Date(cert.expiryDate).toLocaleDateString()}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => handleDeleteCert(cert.certId)}
                aria-label={t('fileChip.removeAriaLabel')}
                className="ml-2 flex-shrink-0 text-zinc-400 transition-colors hover:text-zinc-900"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        !showAddCert && (
          <p className="mt-3 text-[11px] text-zinc-500">{t('certifications.empty')}</p>
        )
      )}
    </SectionShell>
  )
}
