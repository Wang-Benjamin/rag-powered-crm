'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { settingsApiClient } from '@/lib/api/client'
import type {
  CompanyProfileDraft,
  DraftPayload,
} from '@/components/onboarding/customize-ai/ingestion/types'

const AUTOSAVE_DEBOUNCE_MS = 800

export type ContactInfo = {
  name?: string
  title?: string
  email?: string
  phone?: string
  languages?: string[]
}

export type CompanyProfile = {
  companyNameEn?: string
  companyNameZh?: string
  productDescription?: string
  userRole?: string
  location?: string
  logoUrl?: string
  tagline?: string
  yearFounded?: number
  staff?: string
  exportShare?: string
  contact?: ContactInfo
}

export type ProductRow = {
  name: string
  fobPrice?: string
  landedPrice?: string
}

export type FactoryTerms = {
  moq?: string
  leadTime?: string
  samplePolicy?: string
  shipping?: string
  payment?: string
}

export type FactoryDetails = {
  capacity?: string
  leadTime?: string
  moq?: string
  products?: ProductRow[]
  photoUrls?: string[]
  terms?: FactoryTerms
}

interface FactoryProfileResponse {
  success: boolean
  companyProfile?: CompanyProfile
  factoryDetails?: FactoryDetails
  updatedAt?: string | null
}

interface PhotoUploadResponse {
  success: boolean
  url: string
}

export interface UseFactoryProfileDraft {
  isLoading: boolean
  companyProfile: CompanyProfile
  factoryDetails: FactoryDetails
  updatedAt: string | null

  setCompanyField: <K extends keyof CompanyProfile>(key: K, value: CompanyProfile[K]) => void
  setFactoryField: <K extends keyof FactoryDetails>(key: K, value: FactoryDetails[K]) => void

  autofilledKeys: Set<string>
  applyCompanyProfileDraft: (draft: CompanyProfileDraft) => void
  handleIngestionReady: (payload: DraftPayload, jobId: string) => void
  handleIngestionFailed: (message: string) => void

  saveNow: () => Promise<{ updatedAt: string | null }>

  uploadLogo: (file: File) => Promise<string>
  uploadFactoryPhoto: (file: File) => Promise<string>
}

/**
 * Shared draft state for `tenant_subscription.company_profile` +
 * `factory_details`. Backed by `/factory-profile` (GET + POST /save with
 * shallow-merge JSONB writes). Both the storefront page and the onboarding
 * wizard mount this hook so edits in either surface land on the same blob.
 *
 * Autosave debounces 800ms and posts the full canonical state — combined
 * with backend shallow-merge, last arrival wins per top-level key, which
 * matches user intent under racing requests. Pending timers are cancelled
 * on unmount; the next mount re-hydrates from the server.
 */
export function useFactoryProfileDraft(): UseFactoryProfileDraft {
  const [isLoading, setIsLoading] = useState(true)
  const [companyProfile, setCompanyProfile] = useState<CompanyProfile>({})
  const [factoryDetails, setFactoryDetails] = useState<FactoryDetails>({})
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [autofilledKeys, setAutofilledKeys] = useState<Set<string>>(new Set())

  const companyRef = useRef(companyProfile)
  const factoryRef = useRef(factoryDetails)
  companyRef.current = companyProfile
  factoryRef.current = factoryDetails

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isMountedRef = useRef(true)

  useEffect(() => {
    isMountedRef.current = true
    let cancelled = false
    async function hydrate() {
      try {
        const res = await settingsApiClient.get<FactoryProfileResponse>('/factory-profile')
        if (cancelled) return
        setCompanyProfile(res.companyProfile ?? {})
        setFactoryDetails(res.factoryDetails ?? {})
        setUpdatedAt(res.updatedAt ?? null)
      } catch (err) {
        console.error('useFactoryProfileDraft: hydrate failed', err)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    hydrate()
    return () => {
      cancelled = true
      isMountedRef.current = false
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
    }
  }, [])

  const flushAutosave = useCallback(async () => {
    try {
      const res = await settingsApiClient.post<FactoryProfileResponse>('/factory-profile/save', {
        companyProfile: companyRef.current,
        factoryDetails: factoryRef.current,
      })
      if (isMountedRef.current && res.updatedAt) {
        setUpdatedAt(res.updatedAt)
      }
    } catch (err) {
      console.error('useFactoryProfileDraft: autosave failed', err)
      toast.error('Failed to save — please try again.')
    }
  }, [])

  const scheduleAutosave = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      debounceRef.current = null
      flushAutosave()
    }, AUTOSAVE_DEBOUNCE_MS)
  }, [flushAutosave])

  const setCompanyField = useCallback(
    <K extends keyof CompanyProfile>(key: K, value: CompanyProfile[K]) => {
      setCompanyProfile((prev) => ({ ...prev, [key]: value }))
      setAutofilledKeys((prev) => {
        if (!prev.has(key as string)) return prev
        const next = new Set(prev)
        next.delete(key as string)
        return next
      })
      scheduleAutosave()
    },
    [scheduleAutosave]
  )

  const setFactoryField = useCallback(
    <K extends keyof FactoryDetails>(key: K, value: FactoryDetails[K]) => {
      setFactoryDetails((prev) => ({ ...prev, [key]: value }))
      scheduleAutosave()
    },
    [scheduleAutosave]
  )

  const applyCompanyProfileDraft = useCallback(
    (draft: CompanyProfileDraft) => {
      const updates: Partial<CompanyProfile> = {}
      const touched = new Set<string>()
      if (draft.companyNameEn) {
        updates.companyNameEn = draft.companyNameEn
        touched.add('companyNameEn')
      }
      if (draft.companyNameLocal) {
        updates.companyNameZh = draft.companyNameLocal
        touched.add('companyNameZh')
      }
      if (draft.productDescription) {
        updates.productDescription = draft.productDescription
        touched.add('productDescription')
      }
      const locationFromDraft = draft.factoryLocation || draft.headquartersLocation
      if (locationFromDraft) {
        updates.location = locationFromDraft
        touched.add('location')
      }
      if (Object.keys(updates).length === 0) return
      setCompanyProfile((prev) => ({ ...prev, ...updates }))
      setAutofilledKeys(touched)
      scheduleAutosave()
    },
    [scheduleAutosave]
  )

  const handleIngestionReady = useCallback(
    (payload: DraftPayload, _jobId: string) => {
      applyCompanyProfileDraft(payload as CompanyProfileDraft)
    },
    [applyCompanyProfileDraft]
  )

  const handleIngestionFailed = useCallback((message: string) => {
    toast.error(message)
  }, [])

  const saveNow = useCallback(async (): Promise<{ updatedAt: string | null }> => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    const res = await settingsApiClient.post<FactoryProfileResponse>('/factory-profile/save', {
      companyProfile: companyRef.current,
      factoryDetails: factoryRef.current,
    })
    const newUpdatedAt = res.updatedAt ?? null
    if (isMountedRef.current) {
      setUpdatedAt(newUpdatedAt)
    }
    return { updatedAt: newUpdatedAt }
  }, [])

  const uploadLogo = useCallback(
    async (file: File): Promise<string> => {
      const fd = new FormData()
      fd.append('file', file)
      const res = await settingsApiClient.upload<PhotoUploadResponse>(
        '/factory-profile/upload-logo',
        fd
      )
      if (!res.success || !res.url) throw new Error('Logo upload failed')
      setCompanyField('logoUrl', res.url)
      return res.url
    },
    [setCompanyField]
  )

  const uploadFactoryPhoto = useCallback(
    async (file: File): Promise<string> => {
      const fd = new FormData()
      fd.append('file', file)
      const res = await settingsApiClient.upload<PhotoUploadResponse>(
        '/factory-profile/upload-photo',
        fd
      )
      if (!res.success || !res.url) throw new Error('Photo upload failed')
      // Functional updater so concurrent / rapid uploads accumulate instead
      // of clobbering each other (factoryRef may lag the latest setState
      // when callers fire multiple uploads in quick succession).
      setFactoryDetails((prev) => ({
        ...prev,
        photoUrls: [...(prev.photoUrls ?? []), res.url],
      }))
      scheduleAutosave()
      return res.url
    },
    [scheduleAutosave]
  )

  return {
    isLoading,
    companyProfile,
    factoryDetails,
    updatedAt,
    setCompanyField,
    setFactoryField,
    autofilledKeys,
    applyCompanyProfileDraft,
    handleIngestionReady,
    handleIngestionFailed,
    saveNow,
    uploadLogo,
    uploadFactoryPhoto,
  }
}
