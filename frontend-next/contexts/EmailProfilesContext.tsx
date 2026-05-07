'use client'

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
  ReactNode,
} from 'react'
import { useAuth } from '@/hooks/useAuth'
import { getCachedDataWithTimestamp, setCachedData } from '@/utils/data-cache'
import { templateApi, signatureApi, emailTrainingApi } from '@/lib/api/emailprofiles'
import type { EmailTemplate, TemplateType } from '@/types/email/template'
import type { EmailSignature, EmailTrainingSamples } from '@/types/email/signature'
import type { EmailProfilesContextType } from '@/types/email/context'

const EmailProfilesContext = createContext<EmailProfilesContextType | null>(null)

const CACHE_DURATION = 30 * 60 * 1000 // 30 minutes

export const useEmailProfiles = () => {
  const context = useContext(EmailProfilesContext)
  if (!context) {
    throw new Error('useEmailProfiles must be used within an EmailProfilesProvider')
  }
  return context
}

export function EmailProfilesProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const userEmail = user?.email

  // Load initial data from localStorage cache (user-specific)
  const initialCrmCache = getCachedDataWithTimestamp<EmailTemplate[]>(
    'email_templates_crm',
    CACHE_DURATION,
    userEmail
  )
  const initialLeadgenCache = getCachedDataWithTimestamp<EmailTemplate[]>(
    'email_templates_leadgen',
    CACHE_DURATION,
    userEmail
  )
  const _initialSignatureCache = getCachedDataWithTimestamp<EmailSignature>(
    'email_signature_v2',
    CACHE_DURATION,
    userEmail
  )
  // Shape guard: if the cached object lacks `signatureFields`, treat as cache miss.
  const initialSignatureCache =
    _initialSignatureCache?.data && 'signatureFields' in _initialSignatureCache.data
      ? _initialSignatureCache
      : null
  const initialTrainingCache = getCachedDataWithTimestamp<EmailTrainingSamples>(
    'email_training',
    CACHE_DURATION,
    userEmail
  )

  // Template state
  const [templates, setTemplates] = useState<{ crm: EmailTemplate[]; leadgen: EmailTemplate[] }>({
    crm: initialCrmCache?.data || [],
    leadgen: initialLeadgenCache?.data || [],
  })
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [templatesLastFetch, setTemplatesLastFetch] = useState<{
    crm: number | null
    leadgen: number | null
  }>({
    crm: initialCrmCache?.timestamp || null,
    leadgen: initialLeadgenCache?.timestamp || null,
  })

  // Settings state
  const [signature, setSignature] = useState<EmailSignature | null>(
    initialSignatureCache?.data || null
  )
  const [trainingSamples, setTrainingSamples] = useState<EmailTrainingSamples | null>(
    initialTrainingCache?.data || null
  )
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [settingsLastFetch, setSettingsLastFetch] = useState<number | null>(
    initialSignatureCache?.timestamp || null
  )

  // Refs for stable access in callbacks
  const templatesRef = useRef(templates)
  const templatesLastFetchRef = useRef(templatesLastFetch)
  const settingsLastFetchRef = useRef(settingsLastFetch)

  useEffect(() => {
    templatesRef.current = templates
    templatesLastFetchRef.current = templatesLastFetch
    settingsLastFetchRef.current = settingsLastFetch
  }, [templates, templatesLastFetch, settingsLastFetch])

  const isCacheValid = (lastFetch: number | null): boolean => {
    if (!lastFetch) return false
    return Date.now() - lastFetch < CACHE_DURATION
  }

  // Load templates for a given type
  const loadTemplates = useCallback(
    async (templateType: TemplateType, forceRefresh = false) => {
      const currentTemplates = templatesRef.current[templateType]
      const currentLastFetch = templatesLastFetchRef.current[templateType]

      if (!forceRefresh && currentTemplates.length > 0 && isCacheValid(currentLastFetch)) {
        return
      }

      if (!userEmail) return

      setTemplatesLoading(true)

      try {
        const flatList = await templateApi.listTemplates('email', true, templateType)

        const normalized: EmailTemplate[] = (flatList || []).map((t) => ({
          ...t,
          level: (t.level ?? 0) as 0 | 1,
          parentId: t.parentId ?? null,
          rootId: t.rootId ?? null,
          channel: 'email' as const,
          templateType,
          isShared: t.isShared ?? false,
          isActive: t.isActive ?? true,
          sendCount: t.sendCount ?? 0,
          userEmail: t.userEmail ?? userEmail,
          createdAt: t.createdAt ?? new Date().toISOString(),
          updatedAt: t.updatedAt ?? new Date().toISOString(),
        }))

        setTemplates((prev) => ({ ...prev, [templateType]: normalized }))
        setCachedData(`email_templates_${templateType}`, normalized, userEmail)
        setTemplatesLastFetch((prev) => ({ ...prev, [templateType]: Date.now() }))
      } catch {
        // Keep existing data on error
      } finally {
        setTemplatesLoading(false)
      }
    },
    [userEmail]
  )

  const refreshTemplates = useCallback(
    async (templateType: TemplateType) => {
      await loadTemplates(templateType, true)
    },
    [loadTemplates]
  )

  // Update templates cache after CRUD (avoids re-fetch)
  const updateTemplatesCache = useCallback(
    (templateType: TemplateType, updatedTemplates: EmailTemplate[]) => {
      setTemplates((prev) => ({ ...prev, [templateType]: updatedTemplates }))
      if (userEmail) {
        setCachedData(`email_templates_${templateType}`, updatedTemplates, userEmail)
      }
      setTemplatesLastFetch((prev) => ({ ...prev, [templateType]: Date.now() }))
    },
    [userEmail]
  )

  // Load settings (signature + training)
  const loadSettings = useCallback(
    async (forceRefresh = false) => {
      if (!forceRefresh && isCacheValid(settingsLastFetchRef.current)) {
        return
      }

      if (!userEmail) return

      setSettingsLoading(true)

      try {
        const [sigResult, trainingResult] = await Promise.allSettled([
          signatureApi.getSignature(),
          emailTrainingApi.getTrainingSamples(),
        ])

        if (sigResult.status === 'fulfilled') {
          setSignature(sigResult.value)
          setCachedData('email_signature_v2', sigResult.value, userEmail)
        }

        if (trainingResult.status === 'fulfilled') {
          setTrainingSamples(trainingResult.value)
          setCachedData('email_training', trainingResult.value, userEmail)
        }

        setSettingsLastFetch(Date.now())
      } catch {
        // Keep existing data on error
      } finally {
        setSettingsLoading(false)
      }
    },
    [userEmail]
  )

  // Update caches after saves
  const updateSignatureCache = useCallback(
    (sig: EmailSignature) => {
      setSignature(sig)
      if (userEmail) {
        setCachedData('email_signature_v2', sig, userEmail)
      }
    },
    [userEmail]
  )

  const updateTrainingSamplesCache = useCallback(
    (samples: EmailTrainingSamples) => {
      setTrainingSamples(samples)
      if (userEmail) {
        setCachedData('email_training', samples, userEmail)
      }
    },
    [userEmail]
  )

  // Initialize on auth ready (lazy — only loads when tabs are visited)
  // Templates and settings load on-demand from their respective tab components

  const value: EmailProfilesContextType = {
    templates,
    templatesLoading,
    signature,
    trainingSamples,
    settingsLoading,
    loadTemplates,
    refreshTemplates,
    updateTemplatesCache,
    loadSettings,
    updateSignatureCache,
    updateTrainingSamplesCache,
  }

  return <EmailProfilesContext.Provider value={value}>{children}</EmailProfilesContext.Provider>
}
