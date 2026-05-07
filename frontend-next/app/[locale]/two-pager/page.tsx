'use client'

import React, { useState, useCallback, useEffect, Suspense } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from '@/i18n/navigation'
import { useSearchParams } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { type TwoPagerData } from '@/components/two-pager/TwoPagerPage1'
import leadsApiService from '@/lib/api/leads'
import { settingsApiClient } from '@/lib/api/client'
import ReportViewerChrome from '@/components/two-pager/ReportViewerChrome'
import HsCodeSelectionSection from '@/components/two-pager/picker/HsCodeSelectionSection'
import BatchPreflightDialog from '@/components/two-pager/picker/BatchPreflightDialog'

interface HsCodeItem {
  code: string
  description: string
  confirmed?: boolean
}

interface HsCodeSuggestion {
  code: string
  description: string
  confidence: number
}

interface BatchResult {
  hsCode: string
  description: string
  data: TwoPagerData | null
  error?: string
}

type LoadingStage = 'idle' | 'searching' | 'generating' | 'contacts' | 'emails' | 'done' | 'error'

const MAX_BATCH_SELECT = 14
// Approximate cost constants for credit pre-flight modal
const IY_CREDITS_PER_REPORT = 18
const APOLLO_COST_PER_REPORT = 0.15

const STAGE_LABELS: Record<LoadingStage, string> = {
  idle: '',
  searching: '搜索买家... Searching buyers...',
  generating: '生成报告... Generating report...',
  contacts: '正在获取联系方式... Fetching contacts...',
  emails: '正在生成开发信... Generating emails...',
  done: '',
  error: '',
}

// HS code validation: 4-10 chars, digits with optional dots
function isValidHsCode(value: string): boolean {
  return /^[\d.]{4,10}$/.test(value)
}

const IS_TWO_PAGER_ENABLED = process.env.NEXT_PUBLIC_ONE_PAGER_ENABLED === 'true'

// Fix 2: Inner component that consumes useSearchParams — must be wrapped in Suspense
function TwoPagerContent() {
  const t = useTranslations('leads.twoPager')
  const router = useRouter()
  const searchParams = useSearchParams()
  const { isAuthenticated, isLoading: authLoading } = useAuth()

  const [hsCodes, setHsCodes] = useState<HsCodeItem[]>([])
  const [hsLoading, setHsLoading] = useState(true)
  const [stage, setStage] = useState<LoadingStage>('idle')
  const [error, setError] = useState<string | null>(null)
  const [twoPagerReport, setTwoPagerReport] = useState<TwoPagerData | null>(null)

  // Selection state (two-step: select code, then confirm)
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [selectedDescription, setSelectedDescription] = useState('')

  // Multi-select state for batch generation
  const [multiSelected, setMultiSelected] = useState<Set<string>>(new Set())
  const [showPreflightModal, setShowPreflightModal] = useState(false)
  const [batchGenerating, setBatchGenerating] = useState(false)
  const [batchResults, setBatchResults] = useState<BatchResult[]>([])
  const [batchViewReport, setBatchViewReport] = useState<TwoPagerData | null>(null)

  // Manual entry state
  const [manualCode, setManualCode] = useState('')
  const [manualError, setManualError] = useState<string | null>(null)

  // Product description for direct report generation (separate from AI-suggest textarea)
  const [twoPagerProductDesc, setTwoPagerProductDesc] = useState('')
  const [twoPagerProductDescError, setTwoPagerProductDescError] = useState<string | null>(null)

  // AI suggest state
  const [productDescription, setProductDescription] = useState('')
  const [suggestions, setSuggestions] = useState<HsCodeSuggestion[]>([])
  const [suggestLoading, setSuggestLoading] = useState(false)
  const [suggestError, setSuggestError] = useState<string | null>(null)

  // Env gate — redirect if feature is disabled
  useEffect(() => {
    if (!IS_TWO_PAGER_ENABLED) {
      router.push('/')
    }
  }, [router])

  // Auth gate
  useEffect(() => {
    if (!IS_TWO_PAGER_ENABLED) return
    if (!authLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [authLoading, isAuthenticated, router])

  // Fetch user's HS codes on mount
  useEffect(() => {
    if (!IS_TWO_PAGER_ENABLED) return
    if (!isAuthenticated || authLoading) return

    let cancelled = false
    async function fetchHsCodes() {
      try {
        const data = await leadsApiService.getHsCodes()
        if (cancelled) return
        const codes: HsCodeItem[] = (data?.hsCodes || []).filter(
          (hs: HsCodeItem) => hs.confirmed !== false,
        )
        setHsCodes(codes)
      } catch (err) {
        console.error('Failed to fetch HS codes:', err)
      } finally {
        if (!cancelled) setHsLoading(false)
      }
    }
    fetchHsCodes()
    return () => { cancelled = true }
  }, [isAuthenticated, authLoading])

  // Auto-render a specific report when ?hsCode= query param is present
  // (used by batch "View / Print" links that open in a new tab)
  useEffect(() => {
    if (!IS_TWO_PAGER_ENABLED) return
    if (!isAuthenticated || authLoading || hsLoading) return
    const hsCodeParam = searchParams.get('hsCode')
    if (!hsCodeParam) return
    const matchedHs = hsCodes.find((h) => h.code === hsCodeParam)
    const desc = matchedHs?.description || ''
    // Kick off generation silently
    setSelectedCode(hsCodeParam)
    setSelectedDescription(desc)
  }, [isAuthenticated, authLoading, hsLoading, searchParams, hsCodes])

  // When selectedCode is set via query param, trigger generation once
  const [autoGenerateFired, setAutoGenerateFired] = useState(false)
  useEffect(() => {
    if (!IS_TWO_PAGER_ENABLED) return
    if (!selectedCode || autoGenerateFired) return
    if (searchParams.get('hsCode') !== selectedCode) return
    setAutoGenerateFired(true)
    handleGenerateDirect({ hsCode: selectedCode, productDescription: selectedDescription || undefined })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCode, autoGenerateFired, searchParams, selectedDescription])

  // Multi-select toggle (capped at MAX_BATCH_SELECT)
  const toggleMultiSelect = useCallback((code: string) => {
    setMultiSelected((prev) => {
      const next = new Set(prev)
      if (next.has(code)) {
        next.delete(code)
      } else if (next.size < MAX_BATCH_SELECT) {
        next.add(code)
      }
      return next
    })
  }, [])

  // Confirm pre-flight and run batch
  const handleBatchConfirm = useCallback(async () => {
    setShowPreflightModal(false)
    setBatchGenerating(true)
    setBatchResults([])

    const codes = Array.from(multiSelected)
    const codeDescMap = Object.fromEntries(hsCodes.map((h) => [h.code, h.description]))

    try {
      const response = await leadsApiService.generateTwoPagerBatch(
        codes.map((code) => ({ hsCode: code })),
      )
      const results: BatchResult[] = response.results.map((r) => ({
        hsCode: r.hsCode,
        description: codeDescMap[r.hsCode] || '',
        data: r.data as TwoPagerData | null,
        error: r.error?.message,
      }))
      setBatchResults(results)
    } catch (err: any) {
      // Entire request failed — surface as errors for each selected code
      const results: BatchResult[] = codes.map((code) => ({
        hsCode: code,
        description: codeDescMap[code] || '',
        data: null,
        error: err?.message || 'Batch request failed',
      }))
      setBatchResults(results)
    } finally {
      setBatchGenerating(false)
    }
  }, [multiSelected, hsCodes])

  const handleGenerateDirect = useCallback(async (params: { hsCode?: string; productDescription?: string }) => {
    setError(null)
    setTwoPagerReport(null)
    setStage('searching')

    const t1 = setTimeout(() => setStage('generating'), 5000)
    const t2 = setTimeout(() => setStage('contacts'), 20000)
    const t3 = setTimeout(() => setStage('emails'), 45000)
    try {
      const data = await leadsApiService.generateTwoPager(params)
      clearTimeout(t1); clearTimeout(t2); clearTimeout(t3)
      setTwoPagerReport(data as TwoPagerData)
      setStage('done')
    } catch (err: any) {
      clearTimeout(t1); clearTimeout(t2); clearTimeout(t3)
      console.error('Two-pager generation failed:', err)
      setError(err?.message || 'Failed to generate report. Please try again.')
      setStage('error')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleManualSubmit = useCallback(() => {
    const raw = manualCode.trim()
    if (!raw) return

    // Split on any non-digit/non-dot separator (comma, space, semicolon,
    // newline, pipe, slash). Lets users paste "9405, 9403, 8306" or
    // "9405 9403 8306" or newline-separated lists.
    const tokens = raw
      .split(/[^0-9.]+/)
      .map((t) => t.trim())
      .filter((t) => t.length > 0)

    if (tokens.length === 0) {
      setManualError('Enter 4-10 digits with optional dots (e.g. 9405.42)')
      return
    }

    const valid: string[] = []
    const invalid: string[] = []
    for (const t of tokens) {
      if (isValidHsCode(t)) valid.push(t)
      else invalid.push(t)
    }

    if (valid.length === 0) {
      setManualError(`Invalid: ${invalid.join(', ')}`)
      return
    }

    setManualError(invalid.length ? `Skipped invalid: ${invalid.join(', ')}` : null)

    if (valid.length === 1) {
      // Single code → same behavior as before (select + ready to generate)
      setSelectedCode(valid[0])
      setSelectedDescription('')
      return
    }

    // Multiple codes → add to multi-select batch pool. Clear single-select
    // state so the CTA flips to "Generate All Selected".
    setSelectedCode(null)
    setSelectedDescription('')
    setMultiSelected((prev) => {
      const next = new Set(prev)
      for (const code of valid) {
        if (next.size >= MAX_BATCH_SELECT) break
        next.add(code)
      }
      return next
    })
    setManualCode('')
  }, [manualCode])

  const handleSuggest = useCallback(async () => {
    const trimmed = productDescription.trim()
    if (!trimmed) {
      setSuggestError('Please describe your products first.')
      return
    }
    setSuggestError(null)
    setSuggestions([])
    setSuggestLoading(true)
    try {
      const response = await settingsApiClient.post<{
        hsCodes: Array<{ code: string; description: string; confidence: number }>
      }>('/hs-codes/suggest', { productDescription: trimmed })
      setSuggestions(response.hsCodes || [])
    } catch (err: any) {
      console.error('HS code suggestion failed:', err)
      setSuggestError(err?.message || 'Failed to get suggestions. Please try again.')
    } finally {
      setSuggestLoading(false)
    }
  }, [productDescription])

  const handleBack = useCallback(() => {
    setTwoPagerReport(null)
    setBatchViewReport(null)
    setStage('idle')
    setError(null)
  }, [])

  const isGenerating = stage === 'searching' || stage === 'generating' || stage === 'contacts' || stage === 'emails'
  // Fix 5: disable picker when batch results are showing to prevent mixed UI state
  const isPickerDisabled = isGenerating || batchGenerating || batchResults.length > 0
  // Form is submittable when at least one of HS code, product description,
  // or multi-selected batch codes is present
  const canGenerate = !!(selectedCode || twoPagerProductDesc.trim() || multiSelected.size > 0)
  // Batch mode: checkbox selections drive preflight (N >= 1) when no single HS/desc is set
  const isBatchMode = !selectedCode && !twoPagerProductDesc.trim() && multiSelected.size > 0

  // Spinner while auth or HS codes are loading
  if (authLoading || !isAuthenticated || hsLoading) {
    return (
      <div style={{ background: 'var(--bone)', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 32, height: 32, border: '2px solid var(--rule)', borderTop: '2px solid var(--accent)', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  if (!IS_TWO_PAGER_ENABLED) return null

  // Batch inline report viewer (when user clicks "View / Print" from results list)
  if (batchViewReport) {
    return (
      <ReportViewerChrome
        data={batchViewReport}
        backLabel="Back to Results"
        onBack={() => setBatchViewReport(null)}
      />
    )
  }

  // Two-pager report view
  if (twoPagerReport) {
    return (
      <ReportViewerChrome
        data={twoPagerReport}
        backLabel="Back"
        onBack={handleBack}
      />
    )
  }

  // HS code selector view
  return (
    <div style={{
      background: 'var(--bone)',
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif",
      padding: '40px 16px',
    }}>
      {/* eslint-disable-next-line @next/next/no-page-custom-font */}
      <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .tp-input:focus { border-color: var(--ink) !important; outline: 2px solid var(--accent); outline-offset: 1px; background: var(--bone) !important; }
        .tp-input::placeholder { color: var(--mute); opacity: 1; }
        .tp-suggest-card:hover { border-color: var(--ink) !important; background: var(--cream) !important; }
        .tp-suggest-card:focus-visible { border-color: var(--ink) !important; outline: 2px solid var(--accent); outline-offset: 2px; }
        .tp-btn-manual-select:not(:disabled):hover { background: var(--accent) !important; border-color: var(--accent) !important; }
        .tp-btn-manual-select:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
        .tp-btn-suggest:not(:disabled):hover { background: var(--cream) !important; border-color: var(--ink) !important; }
        .tp-btn-suggest:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
        .tp-btn-generate:not(:disabled):hover { background: var(--accent) !important; border-color: var(--accent) !important; transform: translateY(-1px); }
        .tp-btn-generate:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
      `}</style>

      <div style={{ width: 560, maxWidth: '100%' }}>

        {/* Editorial header */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{
            fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: '0.14em',
            textTransform: 'uppercase' as const,
            color: 'var(--mute)',
            marginBottom: 16,
            display: 'block',
          }}>
            US Import · Market Report
          </div>
          <h1 style={{
            fontFamily: "'Instrument Serif', 'Times New Roman', serif",
            fontSize: 'clamp(32px, 5vw, 48px)',
            fontWeight: 400,
            letterSpacing: '-0.015em',
            lineHeight: 1.05,
            color: 'var(--deep)',
            margin: '0 0 16px',
          }}>
            市场报告.{' '}
            <em style={{ fontStyle: 'italic', color: 'var(--accent)' }}>
              Buyers, in one click.
            </em>
          </h1>
          <p style={{
            fontSize: 17,
            lineHeight: 1.55,
            color: 'var(--mute)',
            maxWidth: '52ch',
            margin: '0 auto',
          }}>
            Select a product category to generate a report
          </p>
        </div>

        {/* Loading state */}
        {isGenerating && (
          <div style={{ marginBottom: 24, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 32, height: 32, border: '2px solid var(--rule)', borderTop: '2px solid var(--accent)', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
            <div style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 12, color: 'var(--mute)', letterSpacing: '0.04em' }}>
              {STAGE_LABELS[stage]}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ marginBottom: 16, padding: '12px 16px', borderRadius: 8, background: 'oklch(0.97 0.010 20)', border: '1px solid oklch(0.85 0.040 20)', color: 'oklch(0.45 0.12 20)', fontSize: 12, fontFamily: "'JetBrains Mono', ui-monospace, monospace", letterSpacing: '0.02em' }}>
            {error}
          </div>
        )}

        {/* Section 1: Your HS Codes */}
        <HsCodeSelectionSection
          hsCodes={hsCodes}
          selectedCode={selectedCode}
          setSelectedCode={setSelectedCode}
          setSelectedDescription={setSelectedDescription}
          multiSelected={multiSelected}
          toggleMultiSelect={toggleMultiSelect}
          MAX_BATCH_SELECT={MAX_BATCH_SELECT}
          isPickerDisabled={isPickerDisabled}
          batchGenerating={batchGenerating}
          batchResults={batchResults}
          setBatchResults={setBatchResults}
          setShowPreflightModal={setShowPreflightModal}
          setBatchViewReport={setBatchViewReport}
        />

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--rule)', marginBottom: 28 }} />

        {/* Section 2: Manual Entry */}
        <div style={{ marginBottom: 28 }}>
          <div style={{
            fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: '0.14em',
            textTransform: 'uppercase' as const,
            color: 'var(--mute)',
            marginBottom: 12,
          }}>
            Manual Entry / 手动输入
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={manualCode}
              onChange={(e) => {
                setManualCode(e.target.value)
                setManualError(null)
              }}
              onKeyDown={(e) => { if (e.key === 'Enter') handleManualSubmit() }}
              placeholder="Enter HS code(s) — one or many (e.g. 9405 or 9405, 9403, 8306)"
              disabled={isPickerDisabled}
              className="tp-input"
              style={{
                flex: 1,
                padding: '10px 14px',
                borderRadius: 8,
                border: manualError ? '1px solid oklch(0.85 0.040 20)' : '1px solid var(--rule)',
                background: 'var(--paper)',
                color: 'var(--ink)',
                fontSize: 13,
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                outline: 'none',
              }}
            />
            <button
              onClick={handleManualSubmit}
              disabled={isPickerDisabled || !manualCode.trim()}
              className="tp-btn-manual-select"
              style={{
                padding: '10px 18px',
                borderRadius: 8,
                border: '1px solid var(--deep)',
                background: 'var(--deep)',
                color: 'var(--bone)',
                fontSize: 13,
                fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif",
                fontWeight: 500,
                cursor: isPickerDisabled || !manualCode.trim() ? 'not-allowed' : 'pointer',
                opacity: isPickerDisabled || !manualCode.trim() ? 0.5 : 1,
                whiteSpace: 'nowrap' as const,
                transition: 'background 0.15s, border-color 0.15s',
              }}
            >
              Select
            </button>
          </div>
          {manualError && (
            <div style={{ marginTop: 6, fontSize: 12, color: 'oklch(0.45 0.12 20)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", letterSpacing: '0.02em' }}>
              {manualError}
            </div>
          )}
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--rule)', marginBottom: 28 }} />

        {/* Section 3: Product Description */}
        <div style={{ marginBottom: 28 }}>
          <div style={{
            fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: '0.14em',
            textTransform: 'uppercase' as const,
            color: 'var(--mute)',
            marginBottom: 12,
          }}>
            Product Description / 产品描述
          </div>
          <input
            type="text"
            value={twoPagerProductDesc}
            onChange={(e) => {
              setTwoPagerProductDesc(e.target.value)
              setTwoPagerProductDescError(null)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && canGenerate && !isPickerDisabled) {
                setTwoPagerProductDescError(null)
                handleGenerateDirect({ hsCode: selectedCode || undefined, productDescription: twoPagerProductDesc.trim() || undefined })
              }
            }}
            placeholder="e.g., wooden furniture, lithium-ion battery packs"
            disabled={isPickerDisabled}
            className="tp-input"
            style={{
              width: '100%',
              padding: '10px 14px',
              borderRadius: 8,
              border: twoPagerProductDescError ? '1px solid oklch(0.85 0.040 20)' : '1px solid var(--rule)',
              background: 'var(--paper)',
              color: 'var(--ink)',
              fontSize: 13,
              fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif",
              outline: 'none',
              boxSizing: 'border-box' as const,
            }}
          />
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--mute)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", letterSpacing: '0.02em' }}>
            Provide either an HS code or a product description — or both.
          </div>
          {twoPagerProductDescError && (
            <div style={{ marginTop: 4, fontSize: 12, color: 'oklch(0.45 0.12 20)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", letterSpacing: '0.02em' }}>
              {twoPagerProductDescError}
            </div>
          )}
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--rule)', marginBottom: 28 }} />

        {/* Section 4: AI Suggest */}
        <div>
          <div style={{
            fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: '0.14em',
            textTransform: 'uppercase' as const,
            color: 'var(--mute)',
            marginBottom: 12,
          }}>
            AI Suggest / AI推荐
          </div>
          <textarea
            value={productDescription}
            onChange={(e) => {
              setProductDescription(e.target.value)
              setSuggestError(null)
            }}
            placeholder="Describe what you manufacture or sell / 描述您的产品或业务"
            disabled={isPickerDisabled || suggestLoading}
            rows={3}
            className="tp-input"
            style={{
              width: '100%',
              padding: '10px 14px',
              borderRadius: 8,
              border: suggestError ? '1px solid oklch(0.85 0.040 20)' : '1px solid var(--rule)',
              background: 'var(--paper)',
              color: 'var(--ink)',
              fontSize: 13,
              fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif",
              outline: 'none',
              resize: 'vertical',
              boxSizing: 'border-box' as const,
            }}
          />
          {suggestError && (
            <div style={{ marginTop: 6, fontSize: 12, color: 'oklch(0.45 0.12 20)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", letterSpacing: '0.02em' }}>
              {suggestError}
            </div>
          )}
          <button
            onClick={handleSuggest}
            disabled={isPickerDisabled || suggestLoading || !productDescription.trim()}
            className="tp-btn-suggest"
            style={{
              marginTop: 10,
              padding: '10px 18px',
              borderRadius: 8,
              border: '1px solid var(--rule)',
              background: 'transparent',
              color: 'var(--ink)',
              fontSize: 13,
              fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif",
              fontWeight: 500,
              cursor: isPickerDisabled || suggestLoading || !productDescription.trim() ? 'not-allowed' : 'pointer',
              opacity: isPickerDisabled || suggestLoading || !productDescription.trim() ? 0.5 : 1,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'background 0.15s, border-color 0.15s',
            }}
          >
            {suggestLoading && (
              <span style={{ width: 14, height: 14, border: '2px solid var(--rule)', borderTop: '2px solid var(--accent)', borderRadius: '50%', display: 'inline-block', animation: 'spin 1s linear infinite' }} />
            )}
            Suggest HS Codes / 推荐HS编码
          </button>

          {/* Suggestion cards */}
          {suggestions.length > 0 && (
            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {suggestions.map((s) => (
                <button
                  key={s.code}
                  onClick={() => { setSelectedCode(s.code); setSelectedDescription(s.description) }}
                  disabled={isPickerDisabled}
                  className="tp-suggest-card"
                  style={{
                    padding: '12px 16px',
                    borderRadius: 12,
                    border: '1px solid var(--rule)',
                    background: 'var(--paper)',
                    cursor: isPickerDisabled ? 'wait' : 'pointer',
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    transition: 'border-color 0.15s, background 0.15s',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 13, fontWeight: 500, color: 'var(--deep)', letterSpacing: '0.03em', marginBottom: 2 }}>
                      {s.code}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--mute)', lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif" }}>
                      {s.description}
                    </div>
                  </div>
                  <div style={{
                    flexShrink: 0,
                    fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                    fontSize: 11,
                    fontWeight: 500,
                    color: s.confidence >= 80 ? 'var(--accent)' : s.confidence >= 60 ? 'var(--gold)' : 'var(--mute)',
                    background: s.confidence >= 80 ? 'var(--accent-lo)' : s.confidence >= 60 ? 'oklch(0.97 0.030 85)' : 'var(--paper)',
                    border: `1px solid ${s.confidence >= 80 ? 'oklch(0.420 0.070 160 / 0.3)' : s.confidence >= 60 ? 'oklch(0.720 0.120 85 / 0.3)' : 'var(--rule)'}`,
                    padding: '3px 8px',
                    borderRadius: 4,
                    letterSpacing: '0.04em',
                  }}>
                    {s.confidence}%
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--rule)', marginTop: 28, marginBottom: 28 }} />

        {/* Generate Report button */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          {(selectedCode || twoPagerProductDesc.trim()) && !isPickerDisabled && (
            <div style={{ fontSize: 12, color: 'var(--mute)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", marginBottom: 4, letterSpacing: '0.03em' }}>
              {selectedCode && (
                <span>HS: <span style={{ color: 'var(--accent)', fontWeight: 500 }}>{selectedCode}</span></span>
              )}
              {selectedCode && twoPagerProductDesc.trim() && <span> · </span>}
              {twoPagerProductDesc.trim() && (
                <span>Product: <span style={{ color: 'var(--accent)' }}>{twoPagerProductDesc.trim()}</span></span>
              )}
            </div>
          )}
          {isBatchMode && !isPickerDisabled && (
            <div style={{ fontSize: 12, color: 'var(--mute)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", marginBottom: 4, letterSpacing: '0.03em' }}>
              {t.rich('selectedCount', {
                count: multiSelected.size,
                // eslint-disable-next-line react/display-name
                highlight: (chunks) => <span style={{ color: 'var(--accent)', fontWeight: 500 }}>{chunks}</span>,
              })}
            </div>
          )}
          {!canGenerate && !isPickerDisabled && (
            <div style={{ fontSize: 12, color: 'oklch(0.45 0.12 20)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", marginBottom: 4, letterSpacing: '0.02em' }}>
              {t('pickerValidationEmpty')}
            </div>
          )}
          <button
            onClick={() => {
              if (!canGenerate) {
                setTwoPagerProductDescError('Enter an HS code or a product description to continue.')
                return
              }
              if (isBatchMode) {
                setShowPreflightModal(true)
                return
              }
              handleGenerateDirect({ hsCode: selectedCode || undefined, productDescription: twoPagerProductDesc.trim() || undefined })
            }}
            disabled={!canGenerate || isPickerDisabled}
            className="tp-btn-generate"
            style={{
              width: '100%',
              padding: '14px 24px',
              borderRadius: 8,
              border: canGenerate && !isPickerDisabled ? '1px solid var(--deep)' : '1px solid var(--rule)',
              background: canGenerate && !isPickerDisabled ? 'var(--deep)' : 'var(--paper)',
              color: canGenerate && !isPickerDisabled ? 'var(--bone)' : 'var(--mute)',
              fontSize: 14,
              fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif",
              fontWeight: 500,
              cursor: !canGenerate || isPickerDisabled ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
            }}
          >
            {isGenerating ? STAGE_LABELS[stage] : isBatchMode ? (
              <>Generate Selected ({multiSelected.size}) / 生成所选 <span style={{ display: 'inline-block', transition: 'transform 0.18s ease' }}>→</span></>
            ) : (
              <>Generate Report / 生成报告 <span style={{ display: 'inline-block', transition: 'transform 0.18s ease' }}>→</span></>
            )}
          </button>
        </div>
      </div>

      {/* Credit pre-flight modal */}
      <BatchPreflightDialog
        open={showPreflightModal}
        onOpenChange={setShowPreflightModal}
        multiSelected={multiSelected}
        onConfirm={handleBatchConfirm}
        IY_CREDITS_PER_REPORT={IY_CREDITS_PER_REPORT}
        APOLLO_COST_PER_REPORT={APOLLO_COST_PER_REPORT}
      />
    </div>
  )
}

// Fix 2: Suspense boundary wrapping the component that uses useSearchParams()
export default function TwoPagerPage() {
  return (
    <Suspense fallback={<div style={{ background: 'var(--bone)', minHeight: '100vh' }} />}>
      <TwoPagerContent />
    </Suspense>
  )
}
