'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronLeft,
  Check,
  X,
  Loader2,
  Upload,
  Plus,
  Trash2,
  Sparkles,
  Package,
  Hash,
  Shield,
  Factory,
  ArrowRight,
  Mail,
} from 'lucide-react'
import { useTranslations, useMessages } from 'next-intl'
import { toast } from 'sonner'
import { settingsApiClient } from '@/lib/api/client'
import { settingsService } from '@/lib/api/settings'
import { invitationsApi } from '@/lib/api/invitationsApi'
import leadsApiService from '@/lib/api/leads'
import { useAuth } from '@/hooks/useAuth'
import { DocumentDropzone } from '@/components/onboarding/customize-ai/ingestion/DocumentDropzone'
import { AutofilledFieldHighlight } from '@/components/onboarding/customize-ai/ingestion/AutofilledFieldHighlight'
import { ProductCatalogReviewDialog } from '@/components/onboarding/customize-ai/ingestion/ProductCatalogReviewDialog'
import { ingestionApi } from '@/lib/api/ingestion'
import type {
  CertificationDraft,
  CompanyProfileDraft,
  DraftPayload,
} from '@/components/onboarding/customize-ai/ingestion/types'

interface HsCode {
  code: string
  description: string
  confidence: number
  selected: boolean
}

interface SmtpConfig {
  host: string
  port: number
  label: string
}

const SMTP_PROVIDERS: Record<string, SmtpConfig> = {
  '163.com': { host: 'smtp.163.com', port: 465, label: '163 邮箱' },
  '126.com': { host: 'smtp.126.com', port: 465, label: '126 邮箱' },
  'qq.com': { host: 'smtp.qq.com', port: 465, label: 'QQ 邮箱' },
  'foxmail.com': { host: 'smtp.qq.com', port: 465, label: 'Foxmail' },
  'sina.com': { host: 'smtp.sina.com', port: 465, label: '新浪邮箱' },
  'sohu.com': { host: 'smtp.sohu.com', port: 465, label: '搜狐邮箱' },
  'yeah.net': { host: 'smtp.yeah.net', port: 465, label: 'Yeah 邮箱' },
  'aliyun.com': { host: 'smtp.aliyun.com', port: 465, label: '阿里邮箱' },
  'outlook.com': { host: 'smtp.office365.com', port: 587, label: 'Outlook' },
  'hotmail.com': { host: 'smtp.office365.com', port: 587, label: 'Hotmail' },
  'yahoo.com': { host: 'smtp.mail.yahoo.com', port: 465, label: 'Yahoo' },
}

function detectSmtp(email: string): SmtpConfig | null {
  const domain = email.split('@')[1]?.toLowerCase()
  if (!domain) return null
  return SMTP_PROVIDERS[domain] || null
}

interface QuestionnaireData {
  emailChoice: 'own' | 'prelude' | ''
  ownEmail: string
  smtpAuthCode: string
  smtpHost: string
  smtpPort: number
  preludeUsername: string
  productDescription: string
  companyNameEn: string
  companyNameZh: string
  yourRole: string
  location: string
  logo: File | null
  logoPreview: string | null
  hsCodes: HsCode[]
  manualHsCode: string
  topicsToAvoid: string[]
  hardRestrictions: string[]
  prohibitedStatements: string[]
  additionalContext: string
  capacity: string
  leadTime: string
  moq: string
  products: { name: string; fobPrice: string; landedPrice: string }[]
  factoryPhotos: File[]
  factoryPhotosPreviews: string[]
}

interface SavedCert {
  certId: string
  certType: string
  issuingBody: string
  expiryDate: string
  status: string
  documentUrl: string | null
}

const defaultData: QuestionnaireData = {
  emailChoice: '',
  ownEmail: '',
  smtpAuthCode: '',
  smtpHost: '',
  smtpPort: 465,
  preludeUsername: '',
  productDescription: '',
  companyNameEn: '',
  companyNameZh: '',
  yourRole: '',
  location: '',
  logo: null,
  logoPreview: null,
  hsCodes: [],
  manualHsCode: '',
  topicsToAvoid: [],
  hardRestrictions: [],
  prohibitedStatements: [],
  additionalContext: '',
  capacity: '',
  leadTime: '',
  moq: '',
  products: [{ name: '', fobPrice: '', landedPrice: '' }],
  factoryPhotos: [],
  factoryPhotosPreviews: [],
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

const STEP_IDS = [
  'email_setup',
  'guardrails',
  'company_profile',
  'hs_codes',
  'factory_details',
] as const
const COMPANY_STEPS = new Set([2, 3, 4])

const contentVariants = {
  enter: { opacity: 0, x: 20 },
  center: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
}

interface CustomizeAIQuestionnaireProps {
  userEmail?: string
  initialStep?: number
  onboardingStatus?: string
  companyDataExists?: boolean
  onComplete?: () => void
  onSkip?: () => void
}

export function CustomizeAIQuestionnaire({
  userEmail,
  initialStep = 0,
  onboardingStatus,
  companyDataExists = false,
  onComplete,
  onSkip,
}: CustomizeAIQuestionnaireProps) {
  const t = useTranslations('settings.customizeAi')
  const messages = useMessages()
  const { logout } = useAuth()

  const authProvider = typeof window !== 'undefined' ? localStorage.getItem('auth_provider') : null
  const isOAuthEmail = authProvider === 'google' || authProvider === 'microsoft'

  const STEPS = useMemo(
    () => [
      {
        id: 'email_setup',
        title: 'Email Setup',
        icon: Mail,
        hint: 'Set up your business email for sending and receiving',
      },
      {
        id: 'guardrails',
        title: t('wizard.stepGuardrails'),
        icon: Shield,
        hint: t('wizard.hintGuardrails'),
      },
      {
        id: 'company_profile',
        title: t('wizard.stepProducts'),
        icon: Package,
        hint: t('wizard.hintProducts'),
      },
      { id: 'hs_codes', title: t('wizard.stepHsCodes'), icon: Hash, hint: t('wizard.hintHsCodes') },
      {
        id: 'factory_details',
        title: t('wizard.stepFactory'),
        icon: Factory,
        hint: t('wizard.hintFactory'),
      },
    ],
    [t]
  )

  const clampedStep = Math.min(initialStep, STEPS.length - 1)
  const [currentStep, setCurrentStep] = useState(clampedStep)
  const [editMode, setEditMode] = useState(false)
  const [data, setData] = useState<QuestionnaireData>(defaultData)
  const [isComplete, setIsComplete] = useState(false)
  const [isSkipped, setIsSkipped] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isSuggestingHs, setIsSuggestingHs] = useState(false)
  const [showSetupTransition, setShowSetupTransition] = useState(false)
  const [setupAnimationPhase, setSetupAnimationPhase] = useState(0)
  const [setupSaving, setSetupSaving] = useState(false)
  const [setupDone, setSetupDone] = useState(companyDataExists)
  const [setupFailed, setSetupFailed] = useState(false)
  const [visitedCompanyStep, setVisitedCompanyStep] = useState(false)
  const [isKickingOff, setIsKickingOff] = useState(false)
  const [kickoffMessage, setKickoffMessage] = useState<string>('')

  // Document-ingestion state (M3): when the user drops a company profile PDF,
  // we extract the fields server-side and pre-fill the wizard. `autofilledKeys`
  // drives the soft-amber highlight on each touched field; keys clear as the
  // user edits. `ingestionJobId` is used for the commit/bookkeeping call after
  // the wizard's own save.
  const [ingestionJobId, setIngestionJobId] = useState<string | null>(null)
  const [autofilledKeys, setAutofilledKeys] = useState<Set<string>>(new Set())
  const [ingestionDraft, setIngestionDraft] = useState<CompanyProfileDraft | null>(null)

  // Certification CRUD state
  const [savedCerts, setSavedCerts] = useState<SavedCert[]>([])
  const [newCert, setNewCert] = useState({ certType: 'ISO 9001', issuingBody: '', expiryDate: '' })
  const [addingCert, setAddingCert] = useState(false)
  const [showAddCert, setShowAddCert] = useState(false)
  // M4: ingestion state for the Add Certification panel. Mirrors the company-
  // profile wiring on step 2 (`ingestionJobId` / `autofilledKeys`) but scoped
  // to the cert panel so the two lanes don't fight over the same highlight.
  const [certIngestionJobId, setCertIngestionJobId] = useState<string | null>(null)
  const [certIngestionDraft, setCertIngestionDraft] = useState<CertificationDraft | null>(null)
  const [certIngestionFile, setCertIngestionFile] = useState<File | null>(null)
  const [certAutofilledKeys, setCertAutofilledKeys] = useState<Set<string>>(new Set())

  // M5/M6: product catalog import dialog. Two entry points — one for PDF
  // brochures (M5) and one for CSV/XLSX spreadsheets (M6) — share the same
  // dialog component via a `kind` prop.
  const [productCatalogOpen, setProductCatalogOpen] = useState(false)
  const [productCatalogKind, setProductCatalogKind] = useState<
    'product_pdf' | 'product_csv'
  >('product_pdf')
  const [productCatalogCount, setProductCatalogCount] = useState(0)

  const logoInputRef = useRef<HTMLInputElement>(null)
  const photosInputRef = useRef<HTMLInputElement>(null)

  const totalSteps = STEPS.length
  const progress = ((currentStep + 1) / totalSteps) * 100

  // Load existing data on mount (for edit mode and resuming onboarding)
  useEffect(() => {
    const loadExistingData = async () => {
      try {
        const [profileRes, prefsRes] = await Promise.all([
          settingsApiClient.get<{
            success: boolean
            companyProfile?: Record<string, any>
            factoryDetails?: Record<string, any>
            hsCodes?: Array<{
              code: string
              description: string
              confidence?: number
              confirmed?: boolean
            }>
          }>('/factory-profile'),
          userEmail ? settingsService.getAIPreferences(userEmail) : Promise.resolve(null),
        ])

        const updates: Partial<QuestionnaireData> = {}

        if (profileRes?.companyProfile) {
          const cp = profileRes.companyProfile
          if (cp.companyNameEn) updates.companyNameEn = cp.companyNameEn
          if (cp.companyNameZh) updates.companyNameZh = cp.companyNameZh
          if (cp.productDescription) updates.productDescription = cp.productDescription
          if (cp.userRole) updates.yourRole = cp.userRole
          if (cp.location) updates.location = cp.location
          if (cp.logoUrl) updates.logoPreview = cp.logoUrl
        }

        if (profileRes?.factoryDetails) {
          const fd = profileRes.factoryDetails
          if (fd.capacity) updates.capacity = fd.capacity
          if (fd.leadTime) updates.leadTime = fd.leadTime
          if (fd.moq) updates.moq = String(fd.moq)
          if (fd.products?.length) {
            updates.products = fd.products.map((p: any) => ({
              name: p.name || '',
              fobPrice: p.fobPrice || '',
              landedPrice: p.landedPrice || '',
            }))
          }
        }

        if (profileRes?.hsCodes?.length) {
          updates.hsCodes = profileRes.hsCodes.map((hs) => ({
            code: hs.code,
            description: hs.description || '',
            confidence: hs.confidence ?? 100,
            selected: true,
          }))
        }

        if (prefsRes?.preferences) {
          const g = prefsRes.preferences.guardrails
          if (g?.topicsToAvoid) updates.topicsToAvoid = g.topicsToAvoid
          if (g?.hardRestrictions) updates.hardRestrictions = g.hardRestrictions
          if (g?.prohibitedStatements) updates.prohibitedStatements = g.prohibitedStatements
          const ac = prefsRes.preferences.additionalContext
          if (ac?.additionalContext) updates.additionalContext = ac.additionalContext
        }

        if (Object.keys(updates).length > 0) {
          setData((prev) => ({ ...prev, ...updates }))
          // Mark setup as done if company profile was already saved
          if (updates.companyNameEn) setSetupDone(true)
        }
      } catch {
        // Silent — data loading is best-effort
      }
    }

    loadExistingData()
  }, [userEmail])

  const persistStep = useCallback(
    async (step: number, stepsCompleted: string[]) => {
      if (!userEmail || editMode) return
      try {
        await invitationsApi.updateOnboarding(userEmail, {
          onboardingStatus: 'in_progress',
          onboardingStep: step,
          onboardingProgress: {
            stepsCompleted,
            ...(companyDataExists ? { companyDataExists: true } : {}),
          },
        })
      } catch {
        // Don't block navigation on persistence failure
      }
    },
    [userEmail, editMode, companyDataExists]
  )

  const handleNext = () => {
    if (currentStep < totalSteps - 1) {
      // After HS codes (step 3), run workspace setup transition before advancing
      if (currentStep === 3 && !setupDone) {
        setShowSetupTransition(true)
        return
      }
      let nextStep = currentStep + 1
      // Skip company steps when navigating from non-company steps (invited users)
      if (companyDataExists && !COMPANY_STEPS.has(currentStep)) {
        while (nextStep < totalSteps && COMPANY_STEPS.has(nextStep)) {
          nextStep++
        }
      }
      if (nextStep >= totalSteps) {
        handleSave()
        return
      }
      const completed = STEP_IDS.slice(0, nextStep)
      setCurrentStep(nextStep)
      persistStep(nextStep, [...completed])
    }
  }

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleSkip = async () => {
    if (userEmail) {
      try {
        await invitationsApi.updateOnboarding(userEmail, {
          onboardingStatus: 'skipped',
          onboardingStep: currentStep,
          onboardingProgress: {
            stepsCompleted: [...STEP_IDS.slice(0, currentStep)],
            skippedSteps: [...STEP_IDS.slice(currentStep)],
            ...(companyDataExists ? { companyDataExists: true } : {}),
          },
        })
      } catch {
        // Don't block skip on persistence failure
      }
    }
    setIsSkipped(true)
    onSkip?.()
  }

  const updateData = (updates: Partial<QuestionnaireData>) => {
    setData((prev) => ({ ...prev, ...updates }))
    // Any key the user touches is no longer "auto-filled" — drop the highlight.
    setAutofilledKeys((prev) => {
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

  // Map a CompanyProfileDraft onto the wizard's data shape. Keeps the
  // field-mapping in one place so the commit bookkeeping uses the same view.
  const applyCompanyProfileDraft = (draft: CompanyProfileDraft) => {
    const updates: Partial<QuestionnaireData> = {}
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
    setData((prev) => ({ ...prev, ...updates }))
    setAutofilledKeys(touched)
  }

  const handleIngestionReady = (payload: DraftPayload, jobId: string) => {
    const draft = payload as CompanyProfileDraft
    setIngestionJobId(jobId)
    setIngestionDraft(draft)
    applyCompanyProfileDraft(draft)
  }

  const handleIngestionFailed = (message: string) => {
    toast.error(message)
  }

  // Cert-panel equivalent of updateData: strips any touched key from
  // certAutofilledKeys so the amber highlight clears as soon as the user edits.
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
        (opt) => opt.toLowerCase() === draft.certType!.toLowerCase(),
      )
      // Unknown codes fall back to "Other" rather than writing a value the
      // <select> can't render. Still counts as auto-filled.
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
  }

  const isStep1Valid = data.productDescription.trim() !== '' && data.companyNameEn.trim() !== ''
  const isStep2Valid = data.hsCodes.some((hs) => hs.selected)

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const preview = URL.createObjectURL(file)
      updateData({ logo: file, logoPreview: preview })
    }
  }

  const removeLogo = () => {
    if (data.logoPreview) URL.revokeObjectURL(data.logoPreview)
    updateData({ logo: null, logoPreview: null })
  }

  const suggestHsCodes = async () => {
    if (!data.productDescription.trim()) {
      toast.error(t('productDescriptionRequired'))
      return
    }
    setIsSuggestingHs(true)
    try {
      const response = await settingsApiClient.post<{
        hsCodes: Array<{ code: string; description: string; confidence: number }>
      }>('/hs-codes/suggest', { productDescription: data.productDescription })
      const codes = (response.hsCodes || []).map((hs) => ({ ...hs, selected: hs.confidence >= 70 }))
      updateData({ hsCodes: codes })
    } catch (error: any) {
      console.error('Error suggesting HS codes:', error)
      toast.error(error.message || t('hsCodeSuggestionFailed'))
    } finally {
      setIsSuggestingHs(false)
    }
  }

  const toggleHsCode = (index: number) => {
    const updated = [...data.hsCodes]
    updated[index] = { ...updated[index], selected: !updated[index].selected }
    updateData({ hsCodes: updated })
  }

  const addManualHsCode = () => {
    if (!data.manualHsCode.trim()) return
    updateData({
      hsCodes: [
        ...data.hsCodes,
        { code: data.manualHsCode.trim(), description: '', confidence: 100, selected: true },
      ],
      manualHsCode: '',
    })
  }

  // Certification CRUD via API
  const fetchCerts = useCallback(async () => {
    try {
      const res = await settingsApiClient.get<{ certifications: SavedCert[] }>('/certifications')
      setSavedCerts(res?.certifications || [])
    } catch {
      /* silent — certs are optional */
    }
  }, [])

  useEffect(() => {
    fetchCerts()
  }, [fetchCerts])

  const handleAddCert = async () => {
    if (!newCert.issuingBody) {
      toast.error(t('issuingBodyRequired'))
      return
    }
    try {
      setAddingCert(true)
      const formData = new FormData()
      formData.append('cert_type', newCert.certType)
      formData.append('issuing_body', newCert.issuingBody)
      if (newCert.expiryDate) formData.append('expiry_date', newCert.expiryDate)
      // The dropzone's file is the source of truth — same PDF the extractor
      // ran against gets attached to factory_certifications.document_url.
      if (certIngestionFile) formData.append('file', certIngestionFile)
      await settingsApiClient.upload('/certifications', formData)
      // Bookkeeping: mark the ingestion job committed now that the authoritative
      // write to factory_certifications succeeded. Best-effort — a commit
      // failure must not block the user.
      if (certIngestionJobId) {
        try {
          await ingestionApi.commit(
            certIngestionJobId,
            (certIngestionDraft ?? {}) as DraftPayload,
          )
        } catch (e) {
          console.warn('ingestion commit (cert) failed:', e)
        }
      }
      setNewCert({ certType: 'ISO 9001', issuingBody: '', expiryDate: '' })
      resetCertIngestion()
      setShowAddCert(false)
      await fetchCerts()
    } catch (error: any) {
      toast.error(error.message || t('addCertificationFailed'))
    } finally {
      setAddingCert(false)
    }
  }

  const handleDeleteCert = async (certId: string) => {
    try {
      await settingsApiClient.delete(`/certifications/${certId}`)
      setSavedCerts((prev) => prev.filter((c) => c.certId !== certId))
    } catch (error: any) {
      toast.error(error.message || t('deleteCertificationFailed'))
    }
  }

  const handlePhotosChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length > 0) {
      const previews = files.map((f) => URL.createObjectURL(f))
      updateData({
        factoryPhotos: [...data.factoryPhotos, ...files],
        factoryPhotosPreviews: [...data.factoryPhotosPreviews, ...previews],
      })
    }
    e.target.value = ''
  }

  const removePhoto = (index: number) => {
    URL.revokeObjectURL(data.factoryPhotosPreviews[index])
    const updatedPhotos = [...data.factoryPhotos]
    const updatedPreviews = [...data.factoryPhotosPreviews]
    updatedPhotos.splice(index, 1)
    updatedPreviews.splice(index, 1)
    updateData({ factoryPhotos: updatedPhotos, factoryPhotosPreviews: updatedPreviews })
  }

  const runSetupAnimation = useCallback(async () => {
    if (setupSaving || setupDone) return
    setSetupSaving(true)
    setSetupAnimationPhase(1)
    await new Promise((r) => setTimeout(r, 800))
    setSetupAnimationPhase(2)
    await new Promise((r) => setTimeout(r, 800))
    setSetupAnimationPhase(3)
    try {
      const selectedHsCodes = data.hsCodes.filter((hs) => hs.selected)
      await Promise.all([
        settingsApiClient.post('/factory-profile/save', {
          companyProfile: {
            companyNameEn: data.companyNameEn,
            companyNameZh: data.companyNameZh,
            location: data.location,
            productDescription: data.productDescription,
            userRole: data.yourRole,
          },
          factoryDetails: {},
        }),
        settingsApiClient.post('/hs-codes/confirm', {
          hsCodes: selectedHsCodes.map((hs) => ({ code: hs.code, description: hs.description })),
        }),
      ])
      if (data.logo) {
        const formData = new FormData()
        formData.append('file', data.logo)
        await settingsApiClient.upload('/factory-profile/upload-logo', formData)
      }
      // Bookkeeping: if this save was seeded from a document upload, mark the
      // ingestion job `committed` with the reviewed draft. Best-effort — the
      // factory-profile write has already landed, so we don't want to fail the
      // wizard flow on this call.
      if (ingestionJobId) {
        try {
          await ingestionApi.commit(ingestionJobId, (ingestionDraft ?? {}) as DraftPayload)
        } catch (e) {
          console.warn('ingestion commit bookkeeping failed:', e)
        }
      }
      await new Promise((r) => setTimeout(r, 600))
      setSetupDone(true)
      setSetupSaving(false)
      // Auto-advance to factory details (step 4)
      setShowSetupTransition(false)
      const nextStep = 4
      setCurrentStep(nextStep)
      persistStep(nextStep, [...STEP_IDS.slice(0, nextStep)])
    } catch (error: any) {
      console.error('Error saving workspace setup:', error)
      toast.error(error.message || t('saveWorkspaceFailed'))
      setSetupSaving(false)
      setSetupFailed(true)
      setSetupAnimationPhase(0)
    }
  }, [data, setupSaving, setupDone, persistStep, ingestionJobId, ingestionDraft])

  // Trigger setup animation when transition overlay is shown
  useEffect(() => {
    if (showSetupTransition && !setupDone && !setupSaving && !setupFailed) {
      runSetupAnimation()
    }
  }, [showSetupTransition, setupDone, setupSaving, setupFailed, runSetupAnimation])

  const handleSave = async () => {
    if (isSaving) return
    try {
      if (!userEmail) {
        toast.error(t('userEmailRequired'))
        return
      }
      setIsSaving(true)
      const promises: Promise<any>[] = []

      // Save email configuration based on user's choice
      if (data.emailChoice === 'prelude' && data.preludeUsername.trim()) {
        promises.push(
          settingsApiClient.post('/outreach/create-alias', {
            username: data.preludeUsername.trim(),
            displayName: data.companyNameEn || data.preludeUsername.trim(),
          })
        )
      } else if (data.emailChoice === 'own' && data.ownEmail && data.smtpAuthCode) {
        const detected = detectSmtp(data.ownEmail)
        promises.push(
          settingsApiClient.post('/smtp/config', {
            providerName: detected?.label?.toLowerCase().replace(/\s+/g, '_') || 'custom',
            smtpHost: data.smtpHost || detected?.host || '',
            smtpPort: data.smtpPort || detected?.port || 465,
            smtpUser: data.ownEmail,
            smtpPassword: data.smtpAuthCode,
            imapHost: '',
            imapPort: 993,
            fromName: data.companyNameEn || '',
          })
        )
      }

      promises.push(
        settingsService.saveAIPreferences({
          email: userEmail,
          tone: {
            formality: '',
            conciseness: '',
            proactiveness: '',
            onBrandPhrases: '',
            avoidPhrases: '',
          },
          guardrails: {
            topicsToAvoid: data.topicsToAvoid,
            hardRestrictions: data.hardRestrictions,
            prohibitedStatements: data.prohibitedStatements,
          },
          audience: { idealCustomers: '', roles: '', products: '' },
          additionalContext: { additionalContext: data.additionalContext },
        })
      )
      // Only save company data if user visited company steps or no existing data
      if (!companyDataExists || visitedCompanyStep) {
        // Company profile + HS codes (normally saved in setup animation, which is skipped for invited users)
        promises.push(
          settingsApiClient.post('/factory-profile/save', {
            companyProfile: {
              companyNameEn: data.companyNameEn,
              companyNameZh: data.companyNameZh,
              location: data.location,
              productDescription: data.productDescription,
              userRole: data.yourRole,
            },
            factoryDetails: {
              capacity: data.capacity,
              leadTime: data.leadTime,
              moq: data.moq,
              products: data.products.filter((p) => p.name || p.fobPrice || p.landedPrice),
            },
          })
        )
        const selectedHsCodes = data.hsCodes.filter((hs) => hs.selected)
        if (selectedHsCodes.length) {
          promises.push(
            settingsApiClient.post('/hs-codes/confirm', {
              hsCodes: selectedHsCodes.map((hs) => ({
                code: hs.code,
                description: hs.description,
              })),
            })
          )
        }
        if (data.logo) {
          const logoFormData = new FormData()
          logoFormData.append('file', data.logo)
          promises.push(settingsApiClient.upload('/factory-profile/upload-logo', logoFormData))
        }
        for (const file of data.factoryPhotos) {
          const photosFormData = new FormData()
          photosFormData.append('file', file)
          promises.push(settingsApiClient.upload('/factory-profile/upload-photo', photosFormData))
        }
      }
      await Promise.all(promises)
      if (ingestionJobId && (!companyDataExists || visitedCompanyStep)) {
        try {
          await ingestionApi.commit(ingestionJobId, (ingestionDraft ?? {}) as DraftPayload)
        } catch (e) {
          console.warn('ingestion commit bookkeeping failed:', e)
        }
      }
      await invitationsApi.updateOnboarding(userEmail, {
        onboardingStatus: 'completed',
        onboardingStep: STEPS.length,
        onboardingProgress: {
          stepsCompleted: [...STEP_IDS],
          ...(companyDataExists ? { companyDataExists: true } : {}),
        },
      })

      // Trigger the one-shot BoL onboarding fetch (100 buyers + 10 deep enrich
      // + 30 competitors). Blocking — the user stays on this screen until the
      // backend completes. The kickoff endpoint is idempotent across retries.
      setIsKickingOff(true)
      setKickoffMessage(t('wizard.kickoffFetching'))
      try {
        const kickoff = await leadsApiService.csvKickoffOnboarding()
        if (kickoff.status === 'already_running') {
          // Another session holds the claim — poll until its run finishes.
          // Hard-fail on timeout so the user isn't silently routed forward
          // before their data is ready.
          setKickoffMessage(t('wizard.kickoffWaiting'))
          const deadline = Date.now() + 3 * 60 * 1000
          let settled = false
          while (Date.now() < deadline) {
            await new Promise((r) => setTimeout(r, 2500))
            try {
              const sub = await leadsApiService.getSubscription()
              if (sub?.onboardingStatus === 'complete') {
                settled = true
                break
              }
              if (sub?.onboardingStatus === 'failed') {
                throw new Error(t('wizard.kickoffFailed'))
              }
            } catch (pollErr) {
              if (pollErr instanceof Error && pollErr.message === t('wizard.kickoffFailed')) {
                throw pollErr
              }
              /* swallow transient network errors — keep polling */
            }
          }
          if (!settled) {
            throw new Error(t('wizard.kickoffFailed'))
          }
        }
      } catch (kickoffErr: any) {
        console.error('Onboarding kickoff failed:', kickoffErr)
        toast.error(kickoffErr?.message || t('wizard.kickoffFailed'))
        setIsKickingOff(false)
        setIsSaving(false)
        return
      }
      setIsKickingOff(false)

      toast.success(t('preferencesSaved'))
      setIsComplete(true)
      onComplete?.()
    } catch (error: any) {
      console.error('Error saving preferences:', error)
      toast.error(error.message || t('savePreferencesFailed'))
    } finally {
      setIsSaving(false)
    }
  }

  const canSkipCurrentStep = currentStep === 0 || currentStep === 1
  const isEmailStepValid =
    data.emailChoice === 'own'
      ? data.ownEmail.includes('@') && data.smtpAuthCode.trim().length > 0
      : data.emailChoice === 'prelude'
        ? data.preludeUsername.trim().length > 0
        : isOAuthEmail
  const canProceed = () => {
    if (currentStep === 0) return isEmailStepValid
    if (currentStep === 1) return true // guardrails are optional
    if (currentStep === 2) return isStep1Valid
    if (currentStep === 3) return isStep2Valid
    return true
  }

  const selectedPrimaryHsCode = data.hsCodes.find((hs) => hs.selected)?.code || '---'

  // --- Shared input classes ---
  const inputClass =
    'w-full px-3.5 py-2.5 bg-bone border border-rule rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-all placeholder:text-fog'
  const textareaClass = `${inputClass} resize-none`
  const labelClass = 'block text-xs font-medium text-mute uppercase tracking-wider mb-1.5'

  // --- Terminal states ---
  if (isSkipped) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center"
        >
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-cream">
            <X className="h-6 w-6 text-mute" />
          </div>
          <h2 className="mb-2 title-panel">{t('skipped.title')}</h2>
          <p className="mb-6 max-w-sm text-sm text-mute">{t('skipped.message')}</p>
          <button
            onClick={() => setIsSkipped(false)}
            className="rounded-lg bg-deep px-5 py-2.5 text-sm font-medium text-bone transition-colors hover:bg-deep/90"
          >
            {t('skipped.goBack')}
          </button>
        </motion.div>
      </div>
    )
  }

  if (isComplete) {
    return (
      <div className="flex min-h-[500px] items-center justify-center overflow-hidden rounded-2xl border border-rule/80 bg-deep shadow-lg">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-lg px-8 text-center"
        >
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
            className="mx-auto mb-8 flex h-16 w-16 items-center justify-center rounded-full bg-bone"
          >
            <Check className="h-7 w-7 text-deep" />
          </motion.div>
          <motion.h2
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mb-3 text-2xl font-bold tracking-tight text-bone"
          >
            {t('wizard.ready')}
          </motion.h2>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mb-8 text-sm leading-relaxed text-bone/60"
          >
            {t('wizard.readyDesc', { company: data.companyNameEn || 'Your company' })}
          </motion.p>
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.7 }}
            onClick={() => onComplete?.()}
            className="inline-flex items-center gap-2 rounded-lg bg-bone px-6 py-3 text-sm font-semibold text-deep transition-colors hover:bg-cream"
          >
            {t('wizard.goToDashboard')} <ArrowRight className="h-4 w-4" />
          </motion.button>
        </motion.div>
      </div>
    )
  }

  // Completed users returning from sidebar — show summary card with edit links
  if (onboardingStatus === 'completed' && !isComplete && !editMode) {
    return (
      <div className="flex h-[min(680px,85vh)] items-center justify-center overflow-hidden rounded-2xl border border-rule/80 bg-deep shadow-lg">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md px-8 text-center"
        >
          <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-bone">
            <Check className="h-6 w-6 text-deep" />
          </div>
          <h2 className="mb-2 text-xl font-bold tracking-tight text-bone">
            {t('wizard.configured')}
          </h2>
          <p className="mb-8 text-sm text-bone/50">{t('wizard.configuredDesc')}</p>

          <div className="mb-8 space-y-2 text-left">
            <button
              onClick={() => {
                setEditMode(true)
                setCurrentStep(2)
              }}
              className="group flex w-full items-center justify-between rounded-lg border border-bone/10 bg-bone/5 px-4 py-3 transition-colors hover:border-bone/20"
            >
              <div className="flex items-center gap-3">
                <Package className="h-4 w-4 text-bone/40" />
                <span className="text-sm text-bone/70">{t('wizard.editProduct')}</span>
              </div>
              <ArrowRight className="h-4 w-4 text-bone/30 transition-colors group-hover:text-bone/60" />
            </button>
            <button
              onClick={() => {
                setEditMode(true)
                setCurrentStep(3)
              }}
              className="group flex w-full items-center justify-between rounded-lg border border-bone/10 bg-bone/5 px-4 py-3 transition-colors hover:border-bone/20"
            >
              <div className="flex items-center gap-3">
                <Hash className="h-4 w-4 text-bone/40" />
                <span className="text-sm text-bone/70">{t('wizard.editHsCodes')}</span>
              </div>
              <ArrowRight className="h-4 w-4 text-bone/30 transition-colors group-hover:text-bone/60" />
            </button>
            <button
              onClick={() => {
                setEditMode(true)
                setCurrentStep(1)
              }}
              className="group flex w-full items-center justify-between rounded-lg border border-bone/10 bg-bone/5 px-4 py-3 transition-colors hover:border-bone/20"
            >
              <div className="flex items-center gap-3">
                <Shield className="h-4 w-4 text-bone/40" />
                <span className="text-sm text-bone/70">{t('wizard.editGuardrails')}</span>
              </div>
              <ArrowRight className="h-4 w-4 text-bone/30 transition-colors group-hover:text-bone/60" />
            </button>
            <button
              onClick={() => {
                setEditMode(true)
                setCurrentStep(4)
              }}
              className="group flex w-full items-center justify-between rounded-lg border border-bone/10 bg-bone/5 px-4 py-3 transition-colors hover:border-bone/20"
            >
              <div className="flex items-center gap-3">
                <Factory className="h-4 w-4 text-bone/40" />
                <span className="text-sm text-bone/70">{t('wizard.editFactoryProfile')}</span>
              </div>
              <ArrowRight className="h-4 w-4 text-bone/30 transition-colors group-hover:text-bone/60" />
            </button>
          </div>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="relative flex h-[min(680px,85vh)] overflow-hidden rounded-2xl border border-rule/80 shadow-lg">
      {/* ─── Onboarding Kickoff Overlay (blocking fetch) ─── */}
      <AnimatePresence>
        {isKickingOff && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-[60] flex items-center justify-center rounded-2xl bg-deep"
          >
            <div className="flex max-w-md flex-col items-center gap-8 px-8 text-center">
              <Loader2 className="h-12 w-12 animate-spin text-bone" />
              <div className="space-y-3">
                <h2 className="text-2xl font-bold tracking-tight text-bone">
                  {t('wizard.kickoffTitle') || 'Preparing your buyer data'}
                </h2>
                <p className="text-sm leading-relaxed text-bone/70">
                  {kickoffMessage
                    || t('wizard.kickoffFetching')
                    || 'Fetching buyers, enriching top matches, and pulling competitor context. This takes about a minute.'}
                </p>
                <p className="pt-2 text-xs text-bone/40">
                  {t('wizard.kickoffHint')
                    || 'Please keep this tab open. You will be redirected automatically when everything is ready.'}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Workspace Setup Transition Overlay ─── */}
      <AnimatePresence>
        {showSetupTransition && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 flex items-center justify-center rounded-2xl bg-deep"
          >
            <div className="text-center">
              <div className="mb-10">
                <h2 className="text-2xl font-bold tracking-tight text-bone">
                  {t('wizard.settingUpWorkspace')}
                </h2>
              </div>
              <div className="mx-auto w-full max-w-sm space-y-5 text-left">
                {[
                  {
                    phase: 1,
                    label: t('wizard.productMappedToHs', { code: selectedPrimaryHsCode }),
                  },
                  { phase: 2, label: t('wizard.marketUs') },
                  { phase: 3, label: t('wizard.dealRoomsReady') },
                ].map(({ phase, label }) => (
                  <motion.div
                    key={phase}
                    initial={{ opacity: 0, y: 10 }}
                    animate={setupAnimationPhase >= phase ? { opacity: 1, y: 0 } : {}}
                    transition={{ duration: 0.4, delay: 0.1 }}
                    className="flex items-center gap-3"
                  >
                    <div
                      className={`flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-300 ${
                        setupAnimationPhase >= phase ? 'bg-bone' : 'bg-deep'
                      }`}
                    >
                      <Check
                        className={`h-4 w-4 transition-colors duration-300 ${
                          setupAnimationPhase >= phase ? 'text-ink' : 'text-mute'
                        }`}
                      />
                    </div>
                    <span
                      className={`text-sm transition-colors duration-300 ${
                        setupAnimationPhase >= phase ? 'text-bone' : 'text-mute'
                      }`}
                    >
                      {label}
                    </span>
                  </motion.div>
                ))}
                {!setupDone && !setupFailed && (
                  <div className="flex items-center justify-center pt-4">
                    <Loader2 className="h-5 w-5 animate-spin text-mute" />
                  </div>
                )}
                {setupFailed && (
                  <div className="flex flex-col items-center gap-2 pt-4">
                    <p className="text-xs text-threat">{t('wizard.setupFailed')}</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setSetupFailed(false)
                          setSetupSaving(false)
                          setSetupAnimationPhase(0)
                        }}
                        className="rounded-lg bg-bone px-4 py-2 text-xs font-medium text-ink transition-colors hover:bg-cream"
                      >
                        {t('wizard.retry')}
                      </button>
                      <button
                        onClick={() => {
                          setShowSetupTransition(false)
                          setSetupFailed(false)
                          setSetupSaving(false)
                          setSetupAnimationPhase(0)
                        }}
                        className="px-4 py-2 text-xs font-medium text-mute transition-colors hover:text-rule"
                      >
                        {t('wizard.back')}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Left Panel: Dark navigation ─── */}
      <div className="hidden w-[260px] flex-shrink-0 flex-col bg-deep p-6 md:flex">
        {/* Brand */}
        <div className="mb-10">
          <h1 className="text-sm font-bold tracking-[0.2em] text-bone uppercase">Prelude</h1>
          <p className="mt-1 text-[11px] tracking-wider text-mute">{t('wizard.setup')}</p>
        </div>

        {/* Vertical step indicators */}
        <nav className="flex-1 space-y-0">
          {STEPS.map((step, i) => {
            const isPreFilled = companyDataExists && COMPANY_STEPS.has(i)
            const isCompleted = isPreFilled || i < currentStep
            const isCurrent = i === currentStep
            const StepIcon = step.icon
            return (
              <button
                key={step.id}
                onClick={() => {
                  if (companyDataExists && COMPANY_STEPS.has(i)) setVisitedCompanyStep(true)
                  setCurrentStep(i)
                }}
                className="flex w-full gap-3 text-left"
              >
                {/* Indicator column */}
                <div className="flex flex-col items-center">
                  <div
                    className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full transition-all duration-300 ${
                      isCompleted || isCurrent ? 'bg-bone' : 'border border-ink'
                    }`}
                  >
                    {isCompleted && !isCurrent ? (
                      <Check className="h-3.5 w-3.5 text-ink" />
                    ) : isCurrent ? (
                      <StepIcon className="h-3.5 w-3.5 text-ink" />
                    ) : (
                      <span className="text-[10px] font-medium text-mute">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                    )}
                  </div>
                  {i < STEPS.length - 1 && (
                    <div
                      className={`h-7 w-px transition-colors duration-300 ${isCompleted ? 'bg-mute' : 'bg-deep'}`}
                    />
                  )}
                </div>
                {/* Label */}
                <div className="pt-1">
                  <span
                    className={`text-[13px] font-medium transition-colors duration-300 ${
                      isCurrent ? 'text-bone' : isCompleted ? 'text-mute' : 'text-mute'
                    }`}
                  >
                    {step.title}
                  </span>
                </div>
              </button>
            )
          })}
        </nav>

        {/* Contextual hint */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="mt-auto border-t border-ink pt-6"
          >
            <p className="text-[12px] leading-relaxed text-mute">{STEPS[currentStep]?.hint}</p>
          </motion.div>
        </AnimatePresence>

        {/* Skip for now */}
        {currentStep >= 1 && (
          <button
            onClick={handleSkip}
            className="mt-4 text-left text-[11px] text-mute transition-colors hover:text-mute"
          >
            {t('wizard.skipForNow')}
          </button>
        )}

        {/* Sign out */}
        <button
          onClick={logout}
          className="mt-2 text-left text-[11px] text-mute transition-colors hover:text-rule"
        >
          {t('wizard.signInDifferentAccount')}
        </button>
      </div>

      {/* ─── Right Panel: Content ─── */}
      <div className="flex flex-1 flex-col bg-bone">
        {/* Mobile progress bar */}
        <div className="p-4 pb-0 md:hidden">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] text-mute">
              {t('stepOf', { current: currentStep + 1, total: totalSteps })}
            </span>
            <span className="text-[11px] text-mute">{Math.round(progress)}%</span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-cream">
            <motion.div
              className="h-full rounded-full bg-deep"
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-6 md:p-10">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              variants={contentVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25, ease: 'easeOut' }}
              className="h-full"
            >
              {/* ─── Company data override warning ─── */}
              {companyDataExists && COMPANY_STEPS.has(currentStep) && (
                <div className="mb-6 rounded-lg border border-gold-lo bg-gold-lo p-4">
                  <p className="text-sm font-medium text-gold">
                    {t('wizard.teamDataWarning')}
                  </p>
                  <p className="mt-1 text-xs text-gold">{t('wizard.teamDataWarningDesc')}</p>
                </div>
              )}

              {/* ─── Step 0: Email Setup ─── */}
              {currentStep === 0 && (
                <div>
                  <div className="mb-8">
                    <p className="mb-2 text-[11px] font-semibold tracking-[0.15em] text-mute uppercase">
                      01
                    </p>
                    <h2 className="title-panel">
                      Set Up Your Business Email
                    </h2>
                    <p className="mt-1.5 text-sm text-mute">
                      Choose how you want to send and receive emails through Prelude
                    </p>
                  </div>

                  {isOAuthEmail && (
                    <div className="mb-6 rounded-lg border border-accent-lo bg-accent-lo p-4">
                      <div className="mb-1 flex items-center gap-2">
                        <Check className="h-4 w-4 text-accent" />
                        <p className="text-sm font-medium text-accent">
                          Connected via {authProvider === 'google' ? 'Gmail' : 'Outlook'}
                        </p>
                      </div>
                      <p className="ml-6 text-xs text-accent">
                        {userEmail} is already linked for sending and receiving emails.
                      </p>
                    </div>
                  )}

                  <div className="space-y-3">
                    {!isOAuthEmail && (
                      <button
                        onClick={() => updateData({ emailChoice: 'own' })}
                        className={`w-full rounded-lg border-2 p-4 text-left transition-all ${data.emailChoice === 'own' ? 'border-deep bg-paper' : 'border-rule hover:border-rule'}`}
                      >
                        <div className="flex items-center gap-3">
                          <Mail className="h-5 w-5 text-mute" />
                          <div>
                            <p className="text-sm font-medium text-ink">Use my own email</p>
                            <p className="text-xs text-mute">
                              Connect via SMTP — supports QQ, 163, 126, Sina, Aliyun, Yahoo,
                              Outlook, and more
                            </p>
                          </div>
                        </div>
                      </button>
                    )}

                    <button
                      onClick={() => updateData({ emailChoice: 'prelude' })}
                      className={`w-full rounded-lg border-2 p-4 text-left transition-all ${data.emailChoice === 'prelude' ? 'border-deep bg-paper' : 'border-rule hover:border-rule'}`}
                    >
                      <div className="flex items-center gap-3">
                        <Sparkles className="h-5 w-5 text-mute" />
                        <div>
                          <p className="text-sm font-medium text-ink">
                            {isOAuthEmail ? 'Also get' : 'Get'} a @preludeos.com email
                          </p>
                          <p className="text-xs text-mute">
                            We'll create a professional Prelude email for your outreach
                          </p>
                        </div>
                      </div>
                    </button>
                  </div>

                  {data.emailChoice === 'own' &&
                    !isOAuthEmail &&
                    (() => {
                      const detected = detectSmtp(data.ownEmail)
                      return (
                        <div className="mt-5 space-y-4">
                          <div>
                            <label className={labelClass}>
                              Your email address <span className="text-threat">*</span>
                            </label>
                            <input
                              type="email"
                              value={data.ownEmail}
                              onChange={(e) => {
                                const email = e.target.value
                                const smtp = detectSmtp(email)
                                updateData({
                                  ownEmail: email,
                                  smtpHost: smtp?.host || data.smtpHost,
                                  smtpPort: smtp?.port || data.smtpPort,
                                })
                              }}
                              placeholder="you@163.com"
                              className={inputClass}
                            />
                          </div>

                          {detected && (
                            <div className="rounded-lg border border-accent-lo bg-accent-lo p-3">
                              <div className="flex items-center gap-1.5">
                                <Check className="h-3.5 w-3.5 text-accent" />
                                <p className="text-xs font-medium text-accent">
                                  Detected: {detected.label}
                                </p>
                              </div>
                              <p className="mt-0.5 ml-5 text-xs text-accent">
                                SMTP server auto-configured: {detected.host}:{detected.port}
                              </p>
                            </div>
                          )}

                          {!data.ownEmail.includes('@') && (
                            <div className="rounded-lg border border-rule bg-paper p-3">
                              <p className="mb-1.5 text-xs font-medium text-mute">
                                Supported email providers (auto-detected):
                              </p>
                              <div className="flex flex-wrap gap-1.5">
                                {Object.entries(SMTP_PROVIDERS).map(([domain, cfg]) => (
                                  <span
                                    key={domain}
                                    className="rounded border border-rule bg-bone px-2 py-0.5 text-[11px] text-mute"
                                  >
                                    @{domain}
                                  </span>
                                ))}
                                <span className="rounded border border-dashed border-rule bg-bone px-2 py-0.5 text-[11px] text-mute">
                                  + any SMTP
                                </span>
                              </div>
                            </div>
                          )}

                          <div>
                            <label className={labelClass}>
                              SMTP Authorization Code <span className="text-threat">*</span>
                            </label>
                            <input
                              type="password"
                              value={data.smtpAuthCode}
                              onChange={(e) => updateData({ smtpAuthCode: e.target.value })}
                              placeholder="Enter your SMTP authorization code"
                              className={inputClass}
                            />
                            <div className="mt-2 rounded-lg border border-gold-lo bg-gold-lo p-3">
                              <p className="text-xs font-medium text-gold">
                                How to get your authorization code:
                              </p>
                              <ul className="mt-1 ml-3 list-disc space-y-0.5 text-xs text-gold">
                                <li>QQ: Settings → Account → POP3/SMTP → Enable → Generate code</li>
                                <li>
                                  163: Settings → POP3/SMTP/IMAP → Enable SMTP → Generate code
                                </li>
                              </ul>
                              <p className="mt-1 text-xs text-gold">
                                This is NOT your login password — it's a separate authorization
                                code.
                              </p>
                            </div>
                          </div>

                          {!detected && data.ownEmail.includes('@') && (
                            <div className="space-y-3">
                              <div>
                                <label className={labelClass}>SMTP Server</label>
                                <input
                                  type="text"
                                  value={data.smtpHost}
                                  onChange={(e) => updateData({ smtpHost: e.target.value })}
                                  placeholder="smtp.yourprovider.com"
                                  className={inputClass}
                                />
                              </div>
                              <div>
                                <label className={labelClass}>SMTP Port</label>
                                <input
                                  type="number"
                                  value={data.smtpPort}
                                  onChange={(e) =>
                                    updateData({ smtpPort: parseInt(e.target.value) || 465 })
                                  }
                                  className={inputClass}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })()}

                  {data.emailChoice === 'prelude' && (
                    <div className="mt-5 space-y-4">
                      <div>
                        <label className={labelClass}>
                          Choose your Prelude email <span className="text-threat">*</span>
                        </label>
                        <div className="flex items-center gap-0">
                          <input
                            type="text"
                            value={data.preludeUsername}
                            onChange={(e) =>
                              updateData({
                                preludeUsername: e.target.value
                                  .toLowerCase()
                                  .replace(/[^a-z0-9._-]/g, ''),
                              })
                            }
                            placeholder="yourname"
                            className={`${inputClass} rounded-r-none border-r-0`}
                          />
                          <span className="rounded-r-lg border border-rule bg-cream px-3.5 py-2.5 text-sm whitespace-nowrap text-mute">
                            @preludeos.com
                          </span>
                        </div>
                        {data.preludeUsername && (
                          <p className="mt-1.5 text-xs text-mute">
                            Your email will be:{' '}
                            <span className="font-medium text-ink">
                              {data.preludeUsername}@preludeos.com
                            </span>
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {isOAuthEmail && !data.emailChoice && (
                    <p className="mt-4 text-xs text-mute">
                      You can skip this step — your{' '}
                      {authProvider === 'google' ? 'Gmail' : 'Outlook'} is already connected.
                    </p>
                  )}
                </div>
              )}

              {/* ─── Step 2: Products ─── */}
              {currentStep === 2 && (
                <div>
                  <div className="mb-8">
                    <p className="mb-2 text-[11px] font-semibold tracking-[0.15em] text-mute uppercase">
                      03
                    </p>
                    <h2 className="title-panel">
                      {t('wizard.whatDoYouManufacture')}
                    </h2>
                    <p className="mt-1.5 text-sm text-mute">
                      {t('wizard.tellUsAboutProducts')}
                    </p>
                  </div>
                  <div className="space-y-5">
                    <DocumentDropzone
                      kind="company_profile"
                      accept="application/pdf,.pdf"
                      acceptLabel="PDF"
                      maxSizeMB={50}
                      onReady={handleIngestionReady}
                      onFailed={handleIngestionFailed}
                    />
                    <div>
                      <label className={labelClass}>{t('wizard.productDescription')}</label>
                      <AutofilledFieldHighlight active={autofilledKeys.has('productDescription')}>
                        <textarea
                          value={data.productDescription}
                          onChange={(e) => updateData({ productDescription: e.target.value })}
                          placeholder={t('wizard.productDescriptionPlaceholder')}
                          className={`${textareaClass} min-h-[100px]`}
                        />
                      </AutofilledFieldHighlight>
                    </div>
                    {/* Products + FOB Prices */}
                    <div>
                      <div className="mb-2 flex items-center justify-between">
                        <label className={labelClass}>{t('wizard.productsAndPricing')}</label>
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={() => {
                              setProductCatalogKind('product_pdf')
                              setProductCatalogOpen(true)
                            }}
                            className="flex items-center gap-1 text-xs font-medium text-mute underline-offset-2 hover:text-ink hover:underline"
                          >
                            {t('ingestion.productReview.openButton')}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setProductCatalogKind('product_csv')
                              setProductCatalogOpen(true)
                            }}
                            className="flex items-center gap-1 text-xs font-medium text-mute underline-offset-2 hover:text-ink hover:underline"
                          >
                            {t('ingestion.productReview.openCsvButton')}
                            {productCatalogCount > 0 ? (
                              <span className="ml-1 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-800">
                                +{productCatalogCount}
                              </span>
                            ) : null}
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              updateData({
                                products: [
                                  ...data.products,
                                  { name: '', fobPrice: '', landedPrice: '' },
                                ],
                              })
                            }
                            className="flex items-center gap-1 text-xs font-medium text-mute transition-colors hover:text-ink"
                          >
                            <Plus className="h-3 w-3" /> {t('wizard.addProduct')}
                          </button>
                        </div>
                      </div>
                      <div className="space-y-2">
                        {data.products.map((product, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <input
                              type="text"
                              value={product.name}
                              onChange={(e) => {
                                const updated = [...data.products]
                                updated[idx] = { ...updated[idx], name: e.target.value }
                                updateData({ products: updated })
                              }}
                              placeholder={t('wizard.productNamePlaceholder')}
                              className="min-w-0 flex-1 rounded-lg border border-rule bg-bone px-3.5 py-2.5 text-sm transition-all placeholder:text-rule focus:border-deep focus:ring-1 focus:ring-deep focus:outline-none"
                            />
                            <input
                              type="text"
                              value={product.fobPrice}
                              onChange={(e) => {
                                const updated = [...data.products]
                                updated[idx] = { ...updated[idx], fobPrice: e.target.value }
                                updateData({ products: updated })
                              }}
                              placeholder={t('wizard.fobPricePlaceholder')}
                              className="w-44 shrink-0 rounded-lg border border-rule bg-bone px-3.5 py-2.5 text-sm transition-all placeholder:text-rule focus:border-deep focus:ring-1 focus:ring-deep focus:outline-none"
                            />
                            <input
                              type="text"
                              value={product.landedPrice}
                              onChange={(e) => {
                                const updated = [...data.products]
                                updated[idx] = { ...updated[idx], landedPrice: e.target.value }
                                updateData({ products: updated })
                              }}
                              placeholder={t('wizard.landedPricePlaceholder')}
                              className="w-44 shrink-0 rounded-lg border border-rule bg-bone px-3.5 py-2.5 text-sm transition-all placeholder:text-rule focus:border-deep focus:ring-1 focus:ring-deep focus:outline-none"
                            />
                            {data.products.length > 1 && (
                              <button
                                type="button"
                                onClick={() =>
                                  updateData({
                                    products: data.products.filter((_, i) => i !== idx),
                                  })
                                }
                                className="px-1 text-sm text-mute hover:text-mute"
                              >
                                ×
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                      <div>
                        <label className={labelClass}>
                          {t('wizard.companyNameEn')} <span className="text-threat">*</span>
                        </label>
                        <AutofilledFieldHighlight active={autofilledKeys.has('companyNameEn')}>
                          <input
                            type="text"
                            value={data.companyNameEn}
                            onChange={(e) => updateData({ companyNameEn: e.target.value })}
                            placeholder={t('wizard.companyNameEnPlaceholder')}
                            className={inputClass}
                          />
                        </AutofilledFieldHighlight>
                      </div>
                      <div>
                        <label className={labelClass}>{t('wizard.companyNameZh')}</label>
                        <AutofilledFieldHighlight active={autofilledKeys.has('companyNameZh')}>
                          <input
                            type="text"
                            value={data.companyNameZh}
                            onChange={(e) => updateData({ companyNameZh: e.target.value })}
                            placeholder={t('wizard.companyNameZhPlaceholder')}
                            className={inputClass}
                          />
                        </AutofilledFieldHighlight>
                      </div>
                    </div>
                    <div>
                      <label className={labelClass}>{t('wizard.yourRole')}</label>
                      <input
                        type="text"
                        value={data.yourRole}
                        onChange={(e) => updateData({ yourRole: e.target.value })}
                        placeholder={t('wizard.yourRolePlaceholder')}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className={labelClass}>{t('wizard.locationLabel')}</label>
                      <AutofilledFieldHighlight active={autofilledKeys.has('location')}>
                        <input
                          type="text"
                          value={data.location}
                          onChange={(e) => updateData({ location: e.target.value })}
                          placeholder={t('wizard.locationPlaceholder')}
                          className={inputClass}
                        />
                      </AutofilledFieldHighlight>
                    </div>
                    <div>
                      <label className={labelClass}>
                        {t('wizard.companyLogo')}{' '}
                        <span className="font-normal text-rule">({t('wizard.optional')})</span>
                      </label>
                      {data.logoPreview ? (
                        <div className="flex items-center gap-3">
                          <img
                            src={data.logoPreview}
                            alt="Logo preview"
                            className="h-14 w-14 rounded-lg border border-rule bg-paper object-contain p-1"
                          />
                          <button
                            onClick={removeLogo}
                            className="flex items-center gap-1 text-xs text-threat transition-colors hover:text-threat"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> {t('wizard.remove')}
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => logoInputRef.current?.click()}
                          className="flex items-center gap-2 rounded-lg border border-dashed border-rule px-3.5 py-2.5 text-sm text-mute transition-colors hover:border-mute hover:text-mute"
                        >
                          <Upload className="h-4 w-4" /> {t('wizard.uploadLogo')}
                        </button>
                      )}
                      <input
                        ref={logoInputRef}
                        type="file"
                        accept="image/*"
                        onChange={handleLogoChange}
                        className="hidden"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* ─── Step 3: HS Codes ─── */}
              {currentStep === 3 && (
                <div>
                  <div className="mb-8">
                    <p className="mb-2 text-[11px] font-semibold tracking-[0.15em] text-mute uppercase">
                      04
                    </p>
                    <h2 className="title-panel">
                      {t('wizard.confirmHsCodes')}
                    </h2>
                    <p className="mt-1.5 text-sm text-mute">{t('wizard.hsCodesDesc')}</p>
                  </div>
                  <div className="space-y-5">
                    <button
                      onClick={suggestHsCodes}
                      disabled={isSuggestingHs || !data.productDescription.trim()}
                      className="flex items-center gap-2 rounded-lg bg-deep px-4 py-2.5 text-sm font-medium text-bone transition-all hover:bg-deep disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isSuggestingHs ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" /> {t('wizard.analyzing')}
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" /> {t('wizard.suggestHsCodes')}
                        </>
                      )}
                    </button>

                    {data.hsCodes.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-medium tracking-wider text-mute uppercase">
                          {t('wizard.selectApplicableCodes')}
                        </p>
                        {data.hsCodes.map((hs, index) => (
                          <button
                            key={`${hs.code}-${index}`}
                            onClick={() => toggleHsCode(index)}
                            className={`flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-all ${
                              hs.selected
                                ? 'border-deep bg-paper'
                                : 'border-rule hover:border-rule'
                            }`}
                          >
                            <div
                              className={`mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border transition-colors ${
                                hs.selected ? 'border-deep bg-deep' : 'border-rule'
                              }`}
                            >
                              {hs.selected && <Check className="h-3 w-3 text-bone" />}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-sm font-semibold text-ink">
                                  {hs.code}
                                </span>
                                <span
                                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                                    hs.confidence >= 80
                                      ? 'bg-accent-lo text-accent'
                                      : hs.confidence >= 50
                                        ? 'bg-gold-lo text-gold'
                                        : 'bg-cream text-mute'
                                  }`}
                                >
                                  {hs.confidence}%
                                </span>
                              </div>
                              <p className="mt-0.5 text-xs text-mute">{hs.description}</p>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}

                    <div className="border-t border-rule pt-4">
                      <p className="mb-2 text-xs font-medium tracking-wider text-mute uppercase">
                        {t('wizard.addManually')}
                      </p>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={data.manualHsCode}
                          onChange={(e) => updateData({ manualHsCode: e.target.value })}
                          placeholder="7323.93"
                          className={`flex-1 ${inputClass} font-mono`}
                        />
                        <button
                          onClick={addManualHsCode}
                          disabled={!data.manualHsCode.trim()}
                          className="flex items-center gap-1 rounded-lg bg-cream px-3 py-2 text-sm font-medium text-ink transition-colors hover:bg-fog disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <Plus className="h-3.5 w-3.5" /> {t('wizard.add')}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ─── Step 1: Guardrails ─── */}
              {currentStep === 1 && (
                <div>
                  <div className="mb-8">
                    <p className="mb-2 text-[11px] font-semibold tracking-[0.15em] text-mute uppercase">
                      02
                    </p>
                    <h2 className="title-panel">
                      {t('wizard.aiGuardrails')}
                    </h2>
                    <p className="mt-1.5 text-sm text-mute">{t('wizard.guardrailsDesc')}</p>
                  </div>
                  <div className="space-y-5">
                    {([
                      { field: 'topicsToAvoid' as const, labelKey: 'wizard.topicsToAvoid', chipPath: 'topicsToAvoid' },
                      { field: 'hardRestrictions' as const, labelKey: 'wizard.hardRestrictions', chipPath: 'hardRestrictions' },
                      { field: 'prohibitedStatements' as const, labelKey: 'wizard.claimsNotToMake', chipPath: 'prohibitedStatements' },
                    ] as const).map(({ field, labelKey, chipPath }) => {
                      const predefined: Record<string, string> =
                        (messages as any)?.settings?.customizeAi?.wizard?.guardrailChips?.[chipPath] ?? {}
                      const values: string[] = data[field]
                      return (
                        <div key={field}>
                          <label className={labelClass}>{t(labelKey)}</label>
                          <div className="flex flex-wrap gap-2 mt-2">
                            {Object.entries(predefined).map(([key, label]) => {
                              const selected = values.includes(key)
                              return (
                                <button
                                  key={key}
                                  type="button"
                                  onClick={() =>
                                    updateData({
                                      [field]: selected
                                        ? values.filter((k) => k !== key)
                                        : [...values, key],
                                    })
                                  }
                                  className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
                                    selected
                                      ? 'bg-deep text-bone'
                                      : 'bg-cream text-mute hover:bg-fog'
                                  }`}
                                >
                                  {label}
                                </button>
                              )
                            })}
                          </div>
                          {values.filter((v) => v.startsWith('custom:')).length > 0 && (
                            <div className="flex flex-wrap gap-2 mt-2">
                              {values
                                .filter((v) => v.startsWith('custom:'))
                                .map((v) => (
                                  <span
                                    key={v}
                                    className="inline-flex items-center gap-1 rounded-full bg-deep px-3 py-1.5 text-sm text-bone"
                                  >
                                    {v.replace('custom:', '')}
                                    <button
                                      type="button"
                                      onClick={() =>
                                        updateData({ [field]: values.filter((k) => k !== v) })
                                      }
                                      className="ml-0.5 text-mute hover:text-bone"
                                    >
                                      ×
                                    </button>
                                  </span>
                                ))}
                            </div>
                          )}
                          <div className="mt-2 flex gap-2">
                            <input
                              type="text"
                              placeholder={t('wizard.guardrailChips.addCustom')}
                              className="flex-1 rounded-lg border border-rule bg-bone px-3 py-1.5 text-sm text-ink placeholder:text-mute focus:border-mute focus:outline-none"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' && e.currentTarget.value.trim()) {
                                  e.preventDefault()
                                  updateData({
                                    [field]: [...values, `custom:${e.currentTarget.value.trim()}`],
                                  })
                                  e.currentTarget.value = ''
                                }
                              }}
                            />
                          </div>
                        </div>
                      )
                    })}
                    <div>
                      <label className={labelClass}>{t('wizard.additionalContextLabel')}</label>
                      <textarea
                        value={data.additionalContext}
                        onChange={(e) => updateData({ additionalContext: e.target.value })}
                        placeholder={t('wizard.additionalContextPlaceholder')}
                        className={`${textareaClass} min-h-[80px]`}
                      />
                    </div>
                    <p className="text-[11px] text-mute">
                      {t('wizard.optionalConfigureLater')}
                    </p>
                  </div>
                </div>
              )}

              {/* ─── Step 4: Factory Details ─── */}
              {currentStep === 4 && (
                <div>
                  <div className="mb-8">
                    <p className="mb-2 text-[11px] font-semibold tracking-[0.15em] text-mute uppercase">
                      05
                    </p>
                    <h2 className="title-panel">
                      {t('wizard.factoryProfile')}
                    </h2>
                    <p className="mt-1.5 text-sm text-mute">{t('wizard.factoryProfileDesc')}</p>
                  </div>
                  <div className="space-y-5">
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                      <div>
                        <label className={labelClass}>{t('wizard.productionCapacity')}</label>
                        <input
                          type="text"
                          value={data.capacity}
                          onChange={(e) => updateData({ capacity: e.target.value })}
                          placeholder={t('wizard.productionCapacityPlaceholder')}
                          className={inputClass}
                        />
                      </div>
                      <div>
                        <label className={labelClass}>{t('wizard.leadTime')}</label>
                        <input
                          type="text"
                          value={data.leadTime}
                          onChange={(e) => updateData({ leadTime: e.target.value })}
                          placeholder={t('wizard.leadTimePlaceholder')}
                          className={inputClass}
                        />
                      </div>
                      <div>
                        <label className={labelClass}>{t('wizard.moq')}</label>
                        <input
                          type="number"
                          value={data.moq}
                          onChange={(e) => updateData({ moq: e.target.value })}
                          placeholder="1000"
                          min="0"
                          className={inputClass}
                        />
                      </div>
                    </div>
                    {/* Certification management */}
                    <div>
                      <div className="mb-2 flex items-center justify-between">
                        <label className={labelClass}>{t('wizard.certifications')}</label>
                        <button
                          onClick={() => setShowAddCert(!showAddCert)}
                          className="flex items-center gap-1 text-xs font-medium text-mute transition-colors hover:text-ink"
                        >
                          <Plus className="h-3 w-3" /> {t('wizard.add')}
                        </button>
                      </div>

                      {showAddCert && (
                        <div className="mb-3 space-y-2.5 rounded-lg border border-rule bg-paper p-3">
                          <DocumentDropzone
                            kind="certification"
                            accept="application/pdf,.pdf,image/png,.png,image/jpeg,.jpg,.jpeg"
                            acceptLabel="PDF / PNG / JPG"
                            maxSizeMB={50}
                            size="compact"
                            onReady={handleCertIngestionReady}
                            onFailed={handleIngestionFailed}
                            onFileStaged={setCertIngestionFile}
                          />
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="mb-1 block text-[10px] font-medium tracking-wider text-mute uppercase">
                                {t('wizard.certType')}
                              </label>
                              <AutofilledFieldHighlight active={certAutofilledKeys.has('certType')}>
                                <select
                                  value={newCert.certType}
                                  onChange={(e) => updateCert({ certType: e.target.value })}
                                  className={inputClass}
                                >
                                  {CERT_TYPE_OPTIONS.map((opt) => (
                                    <option key={opt} value={opt}>
                                      {opt}
                                    </option>
                                  ))}
                                </select>
                              </AutofilledFieldHighlight>
                            </div>
                            <div>
                              <label className="mb-1 block text-[10px] font-medium tracking-wider text-mute uppercase">
                                {t('wizard.issuingBody')}
                              </label>
                              <AutofilledFieldHighlight active={certAutofilledKeys.has('issuingBody')}>
                                <input
                                  type="text"
                                  value={newCert.issuingBody}
                                  onChange={(e) => updateCert({ issuingBody: e.target.value })}
                                  placeholder={t('wizard.issuingBodyPlaceholder')}
                                  className={inputClass}
                                />
                              </AutofilledFieldHighlight>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="mb-1 block text-[10px] font-medium tracking-wider text-mute uppercase">
                                {t('wizard.expiryDate')}
                              </label>
                              <AutofilledFieldHighlight active={certAutofilledKeys.has('expiryDate')}>
                                <input
                                  type="date"
                                  value={newCert.expiryDate}
                                  onChange={(e) => updateCert({ expiryDate: e.target.value })}
                                  className={inputClass}
                                />
                              </AutofilledFieldHighlight>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={handleAddCert}
                              disabled={addingCert || !newCert.issuingBody}
                              className="rounded-md bg-deep px-3 py-1.5 text-xs font-medium text-bone transition-colors hover:bg-deep disabled:opacity-50"
                            >
                              {addingCert ? t('wizard.addingCert') : t('wizard.addCertification')}
                            </button>
                            <button
                              onClick={() => {
                                setShowAddCert(false)
                                setNewCert({
                                  certType: 'ISO 9001',
                                  issuingBody: '',
                                  expiryDate: '',
                                })
                                resetCertIngestion()
                              }}
                              className="px-3 py-1.5 text-xs text-mute transition-colors hover:text-ink"
                            >
                              {t('wizard.cancel')}
                            </button>
                          </div>
                        </div>
                      )}

                      {savedCerts.length > 0 ? (
                        <div className="space-y-1.5">
                          {savedCerts.map((cert) => (
                            <div
                              key={cert.certId}
                              className="flex items-center justify-between rounded-lg border border-rule bg-paper px-3 py-2"
                            >
                              <div className="flex min-w-0 items-center gap-2">
                                <span className="text-xs font-medium text-ink">
                                  {cert.certType}
                                </span>
                                <span className="text-[10px] text-mute">
                                  {cert.issuingBody}
                                </span>
                                {cert.expiryDate && (
                                  <span className="text-[10px] text-mute">
                                    {new Date(cert.expiryDate).toLocaleDateString()}
                                  </span>
                                )}
                              </div>
                              <button
                                onClick={() => handleDeleteCert(cert.certId)}
                                className="ml-2 flex-shrink-0 text-mute transition-colors hover:text-threat"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        !showAddCert && (
                          <p className="text-[11px] text-mute">{t('wizard.noCertsYet')}</p>
                        )
                      )}
                    </div>
                    <div>
                      <label className={labelClass}>{t('wizard.factoryPhotos')}</label>
                      {data.factoryPhotosPreviews.length > 0 && (
                        <div className="mb-2 grid grid-cols-4 gap-2">
                          {data.factoryPhotosPreviews.map((preview, index) => (
                            <div key={index} className="group relative">
                              <img
                                src={preview}
                                alt={`Factory photo ${index + 1}`}
                                className="h-20 w-full rounded-lg border border-rule object-cover"
                              />
                              <button
                                onClick={() => removePhoto(index)}
                                className="absolute top-1 right-1 flex h-5 w-5 items-center justify-center rounded-full bg-deep/70 text-bone opacity-0 transition-opacity group-hover:opacity-100"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                      <button
                        onClick={() => photosInputRef.current?.click()}
                        className="flex items-center gap-2 rounded-lg border border-dashed border-rule px-3.5 py-2.5 text-sm text-mute transition-colors hover:border-mute hover:text-mute"
                      >
                        <Upload className="h-3.5 w-3.5" /> {t('wizard.uploadFactoryPhotos')}
                      </button>
                      <input
                        ref={photosInputRef}
                        type="file"
                        multiple
                        accept="image/*"
                        onChange={handlePhotosChange}
                        className="hidden"
                      />
                    </div>
                    <p className="text-[11px] text-mute">{t('wizard.optionalAddLater')}</p>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* ─── Navigation bar ─── */}
        <div className="flex items-center justify-between border-t border-rule px-6 py-4 md:px-10">
          <button
            onClick={handlePrevious}
            disabled={currentStep === 0}
            className="flex items-center gap-1.5 text-sm font-medium text-mute transition-all hover:text-ink disabled:cursor-default disabled:opacity-0"
          >
            <ChevronLeft className="h-4 w-4" /> {t('wizard.back')}
          </button>

          {/* Mobile skip */}
          <div className="md:hidden">
            {currentStep >= 1 && (
              <button
                onClick={handleSkip}
                className="text-xs text-mute transition-colors hover:text-mute"
              >
                {t('wizard.skip')}
              </button>
            )}
          </div>

          {currentStep === totalSteps - 1 || (companyDataExists && currentStep === 1) ? (
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center gap-2 rounded-lg bg-deep px-5 py-2.5 text-sm font-medium text-bone transition-all hover:bg-deep disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> {t('wizard.savingEllipsis')}
                </>
              ) : (
                <>
                  <Check className="h-4 w-4" /> {t('wizard.saveAndFinish')}
                </>
              )}
            </button>
          ) : canSkipCurrentStep ? (
            <div className="flex items-center gap-2">
              <button
                onClick={handleNext}
                className="px-4 py-2.5 text-sm font-medium text-mute transition-colors hover:text-mute"
              >
                {t('wizard.skipStep')}
              </button>
              <button
                onClick={handleNext}
                className="flex items-center gap-1.5 rounded-lg bg-deep px-5 py-2.5 text-sm font-medium text-bone transition-all hover:bg-deep"
              >
                {t('wizard.continue')} <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              onClick={handleNext}
              disabled={!canProceed()}
              className="flex items-center gap-1.5 rounded-lg bg-deep px-5 py-2.5 text-sm font-medium text-bone transition-all hover:bg-deep disabled:cursor-not-allowed disabled:opacity-50"
            >
              {t('wizard.continue')} <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <ProductCatalogReviewDialog
        open={productCatalogOpen}
        onOpenChange={setProductCatalogOpen}
        onCommitted={(count) => setProductCatalogCount((prev) => prev + count)}
        kind={productCatalogKind}
      />
    </div>
  )
}
