'use client'

import React, { useEffect, useRef, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { setCachedData } from '@/utils/data-cache'
import { toCamelCase } from '@/lib/api/caseTransform'
import styles from './PreloadProgress.module.css'

interface PreloadProgressProps {
  onComplete?: () => void
  onError?: (error: string) => void
  initialStage?: 'authenticating' | 'loading'
}

interface ProgressUpdate {
  progress: number
  total: number
  completed?: number
  message: string
  result?: {
    name: string
    status: string
    error?: string
    data?: any
  }
  done?: boolean
}

// Map endpoint names to cache keys (must match what contexts/pages expect)
const CACHE_KEY_MAP: Record<string, string> = {
  crm_customers: 'crm_customers',
  crm_deals: 'crm_deals',
  crm_employees: 'crm_employees',
  leads_all: 'leads_all',
}

type Status = 'pending' | 'loading' | 'success' | 'error'
type OrbState = 'loading' | 'success' | 'error'

interface LoadingItem {
  name: string
  displayName: string
  status: Status
}

const LOADING_ITEMS: { name: string; displayNameKey: string }[] = [
  { name: 'authentication', displayNameKey: 'preload.items.authentication' },
  { name: 'crm_customers', displayNameKey: 'preload.items.customerData' },
  { name: 'crm_deals', displayNameKey: 'preload.items.dealsPipeline' },
  { name: 'crm_employees', displayNameKey: 'preload.items.teamMembers' },
  { name: 'leads_all', displayNameKey: 'preload.items.leadGeneration' },
]

const RING_R = 118
const RING_CIRC = 2 * Math.PI * RING_R

// Visual-pacing delay between staggered checklist flips — SSE results can arrive
// in a burst, so this spaces them so each row change is legible.
const QUEUE_STAGGER_MS = 400

// Grace before dismissing the preloader so the 'ready' state has a beat to land.
const COMPLETE_HANDOFF_MS = 800

const CHECK_SVG = (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M20 6L9 17l-5-5" />
  </svg>
)

const X_SVG = (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
)

// Full d3 is heavier than d3-geo alone, but d3-geo's UMD expects d3-array already
// present on window.d3 — loading d3-geo standalone would silently break on first
// use. The bigger win is parallelizing with the atlas fetch + caching the parse.
const D3_SRC = 'https://unpkg.com/d3@7.8.5/dist/d3.min.js'
const TOPOJSON_SRC = 'https://unpkg.com/topojson-client@3.1.0/dist/topojson-client.min.js'
const WORLD_ATLAS_SRC = 'https://unpkg.com/world-atlas@2.0.2/countries-110m.json'

// Cache the parsed topojson feature collection across mounts — the preloader
// can render multiple times per session (auth callback + cold workspace entry).
let cachedCountries: any = null

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof document === 'undefined') return reject(new Error('no document'))
    const existing = document.querySelector<HTMLScriptElement>(`script[data-preload-src="${src}"]`)
    if (existing) {
      if (existing.dataset.loaded === '1') return resolve()
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error(`failed: ${src}`)))
      return
    }
    const s = document.createElement('script')
    s.src = src
    s.async = true
    s.dataset.preloadSrc = src
    s.onload = () => {
      s.dataset.loaded = '1'
      resolve()
    }
    s.onerror = () => reject(new Error(`failed: ${src}`))
    document.head.appendChild(s)
  })
}

const PreloadProgress: React.FC<PreloadProgressProps> = ({
  onComplete,
  onError,
  initialStage = 'loading',
}) => {
  const t = useTranslations('common')
  const locale = useLocale()
  const emClass = locale.startsWith('zh') ? styles.emZh : styles.emLatin

  const [isComplete, setIsComplete] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [loadingItems, setLoadingItems] = useState<LoadingItem[]>(
    LOADING_ITEMS.map((item, index) => ({
      name: item.name,
      displayName: t(item.displayNameKey as any),
      status: initialStage === 'authenticating' && index === 0 ? 'loading' : 'pending',
    }))
  )

  const orbState: OrbState = hasError ? 'error' : isComplete ? 'success' : 'loading'

  // Visual-pacing queue: stagger item transitions so UI reads left-to-right
  const completionQueue = useRef<Array<{ name: string; status: 'success' | 'error'; data?: any }>>(
    []
  )
  const isFlushing = useRef(false)

  const flushQueue = () => {
    if (isFlushing.current || completionQueue.current.length === 0) return
    isFlushing.current = true

    const processNext = () => {
      const item = completionQueue.current.shift()
      if (!item) {
        isFlushing.current = false
        return
      }

      setLoadingItems((prev) =>
        prev.map((i) => (i.name === item.name ? { ...i, status: item.status } : i))
      )

      if (item.status === 'success' && item.data) {
        const cacheKey = CACHE_KEY_MAP[item.name]
        if (cacheKey) {
          const token = localStorage.getItem('id_token')
          try {
            const payload = JSON.parse(atob(token!.split('.')[1]))
            const userEmail = payload.email || payload.userEmail
            // Preload streams raw backend JSON (snake_case). Contexts read
            // camelCase via ApiClient, so normalize before writing the cache.
            setCachedData(cacheKey, toCamelCase(item.data), userEmail)
          } catch {
            // Cache error
          }
        }
      }

      setTimeout(processNext, QUEUE_STAGGER_MS)
    }

    processNext()
  }

  // ───── Globe (D3 orthographic) ─────
  const globeSvgRef = useRef<SVGSVGElement | null>(null)
  const globeRafRef = useRef<number | null>(null)
  const globeSpeedRef = useRef(0.5)

  useEffect(() => {
    let cancelled = false

    async function mountGlobe() {
      try {
        // Fire the world-atlas fetch in parallel with the scripts — atlas download
        // is ~100KB and otherwise stalls behind d3-geo/topojson script loads.
        const fetchAtlas =
          cachedCountries !== null ? Promise.resolve(null) : fetch(WORLD_ATLAS_SRC)
        const [, , atlasRes] = await Promise.all([
          loadScript(D3_SRC),
          loadScript(TOPOJSON_SRC),
          fetchAtlas,
        ])
        if (cancelled || !globeSvgRef.current) return

        const d3 = (window as any).d3
        const topojson = (window as any).topojson
        if (!d3 || !topojson) return

        if (cachedCountries === null && atlasRes) {
          const topo = await atlasRes.json()
          if (cancelled) return
          cachedCountries = topojson.feature(topo, topo.objects.countries)
        }
        const countries = cachedCountries

        const svg = globeSvgRef.current
        const ns = 'http://www.w3.org/2000/svg'
        const R = 88

        svg.innerHTML = ''

        const sphere = document.createElementNS(ns, 'circle')
        sphere.setAttribute('cx', '0')
        sphere.setAttribute('cy', '0')
        sphere.setAttribute('r', String(R))
        sphere.setAttribute('fill', 'var(--paper)')
        sphere.setAttribute('stroke', 'var(--deep)')
        sphere.setAttribute('stroke-width', '1')
        svg.appendChild(sphere)

        const gratG = document.createElementNS(ns, 'g')
        gratG.setAttribute('fill', 'none')
        gratG.setAttribute('stroke', 'var(--mute)')
        gratG.setAttribute('stroke-width', '0.4')
        gratG.setAttribute('opacity', '0.28')
        svg.appendChild(gratG)

        const landG = document.createElementNS(ns, 'g')
        landG.setAttribute('fill', 'var(--deep)')
        landG.setAttribute('fill-opacity', '0.9')
        landG.setAttribute('stroke', 'var(--bone)')
        landG.setAttribute('stroke-width', '0.3')
        landG.setAttribute('stroke-linejoin', 'round')
        svg.appendChild(landG)

        const projection = d3.geoOrthographic().scale(R).translate([0, 0]).clipAngle(90)
        const path = d3.geoPath(projection)
        const graticule = d3.geoGraticule10()

        const gratPath = document.createElementNS(ns, 'path')
        gratG.appendChild(gratPath)

        const countryPaths = countries.features.map((f: any) => {
          const p = document.createElementNS(ns, 'path')
          landG.appendChild(p)
          return { f, el: p }
        })

        let lambda = 0
        const render = () => {
          projection.rotate([lambda, -14, 0])
          gratPath.setAttribute('d', path(graticule) || '')
          for (const { f, el } of countryPaths) el.setAttribute('d', path(f) || '')
        }
        const tick = () => {
          if (cancelled) return
          lambda = (lambda + globeSpeedRef.current) % 360
          render()
          globeRafRef.current = requestAnimationFrame(tick)
        }
        render()
        globeRafRef.current = requestAnimationFrame(tick)
      } catch {
        // CDN blocked / offline — globe quietly absent, rings + progress still work
      }
    }

    mountGlobe()

    return () => {
      cancelled = true
      if (globeRafRef.current !== null) cancelAnimationFrame(globeRafRef.current)
    }
  }, [])

  useEffect(() => {
    if (orbState === 'success') globeSpeedRef.current = 0.15
    else if (orbState === 'error') globeSpeedRef.current = 0
    else globeSpeedRef.current = 0.5
  }, [orbState])

  // ───── SSE preload fetch ─────
  useEffect(() => {
    if (initialStage === 'authenticating') return

    setLoadingItems((prev) =>
      prev.map((item, index) => (index === 0 ? { ...item, status: 'success' as const } : item))
    )
    setProgress(20)

    const token = localStorage.getItem('id_token')
    if (!token) {
      setHasError(true)
      setErrorMessage(t('preload.notAuthenticated'))
      onError?.('Not authenticated')
      return
    }
    setLoadingItems((prev) =>
      prev.map((item) =>
        item.name !== 'authentication' ? { ...item, status: 'loading' as const } : item
      )
    )

    const controller = new AbortController()

    const fetchPreload = async () => {
      try {
        const response = await fetch('/api/proxy/settings/preload/all', {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          signal: controller.signal,
        })

        if (!response.ok) throw new Error('Failed to start preload')

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()
        if (!reader) throw new Error('No response body')

        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const data: ProgressUpdate = JSON.parse(line.substring(6))

              if (data.progress !== undefined) setProgress(data.progress)

              if (data.result) {
                if (data.result.status === 'success' || data.result.status === 'error') {
                  completionQueue.current.push({
                    name: data.result.name,
                    status: data.result.status as 'success' | 'error',
                    data: data.result.data,
                  })
                  flushQueue()
                }
              }

              if (data.done) {
                setProgress(100)
                setIsComplete(true)
                setTimeout(() => onComplete?.(), COMPLETE_HANDOFF_MS)
                return
              }
            } catch {
              // Parse error
            }
          }
        }

        if (buffer.trim().startsWith('data: ')) {
          try {
            const data: ProgressUpdate = JSON.parse(buffer.substring(6))
            if (data.done) {
              setProgress(100)
              setIsComplete(true)
              setTimeout(() => onComplete?.(), COMPLETE_HANDOFF_MS)
            }
          } catch {
            // Final buffer parse error
          }
        }
      } catch (error: any) {
        if (error?.name === 'AbortError') return
        setHasError(true)
        setErrorMessage(t('preload.failedToLoad'))
        onError?.('Failed to connect to preload service')
      }
    }

    fetchPreload()
    return () => {
      controller.abort()
    }
  }, [initialStage, onComplete, onError, t])

  // ───── Title + eyebrow + subtitle (state-dependent) ─────
  type RichKey = 'preload.titleRich' | 'preload.readyRich' | 'preload.errorTitleRich'
  const titleRichKey: RichKey = hasError
    ? 'preload.errorTitleRich'
    : isComplete
      ? 'preload.readyRich'
      : 'preload.titleRich'
  const subtitle = hasError
    ? errorMessage || t('preload.failedSubtitle')
    : isComplete
      ? t('preload.redirecting')
      : initialStage === 'authenticating'
        ? t('preload.authenticating')
        : t('preload.pleaseWait')
  const eyebrowText = hasError
    ? t('preload.eyebrow.error')
    : isComplete
      ? t('preload.eyebrow.ready')
      : t('preload.eyebrow.loading')
  const eyebrowState: 'success' | 'error' | undefined = hasError
    ? 'error'
    : isComplete
      ? 'success'
      : undefined

  const renderMetaText = (status: Status) => t(`preload.meta.${status}` as any)

  const renderIcon = (status: Status) => {
    if (status === 'success') return CHECK_SVG
    if (status === 'error') return X_SVG
    if (status === 'loading') return <div className={styles.loadingSpin} />
    return <div className={styles.pendingDot} />
  }

  return (
    <div className={styles.container} role="status" aria-live="polite">
      <main className={styles.card}>
        <span className={styles.eyebrow} data-state={eyebrowState}>
          <span className={styles.pulseDot} aria-hidden="true" />
          <span>{eyebrowText}</span>
        </span>

        <div className={styles.orb} data-state={orbState} aria-hidden="true">
          {/* Progress ring (orbits while loading) */}
          <div className={`${styles.ringStack} ${styles.progressOrbit}`}>
            <svg viewBox="0 0 260 260" style={{ width: '100%', height: '100%', overflow: 'visible' }}>
              <circle
                className={styles.ringBg}
                cx="130"
                cy="130"
                r={RING_R}
                fill="none"
                strokeWidth="2"
              />
              <circle
                className={styles.progressArc}
                cx="130"
                cy="130"
                r={RING_R}
                fill="none"
                strokeWidth="2"
                strokeLinecap="round"
                transform="rotate(-90 130 130)"
                strokeDasharray={RING_CIRC}
                strokeDashoffset={RING_CIRC * (1 - progress / 100)}
              />
            </svg>
          </div>

          {/* Whirl layer (only 'a' in the quiet variant) */}
          <div className={`${styles.ringStack} ${styles.whirlSpinA}`}>
            <svg viewBox="0 0 260 260" style={{ width: '100%', height: '100%', overflow: 'visible' }}>
              <circle
                cx="130"
                cy="130"
                r="100"
                fill="none"
                stroke="var(--accent)"
                strokeWidth="1.25"
                strokeLinecap="round"
                strokeDasharray="120 508"
                opacity="0.7"
              />
              <circle
                cx="130"
                cy="130"
                r="100"
                fill="none"
                stroke="var(--accent)"
                strokeWidth="1.25"
                strokeLinecap="round"
                strokeDasharray="18 610"
                strokeDashoffset="-200"
                opacity="0.45"
              />
            </svg>
          </div>

          {/* Globe */}
          <div className={styles.globeOrbit}>
            <div className={styles.globeWrap}>
              <svg ref={globeSvgRef} viewBox="-100 -100 200 200" />
            </div>
          </div>
        </div>

        <h2 className={styles.title}>
          {t.rich(titleRichKey, {
            em: (chunks) => <span className={emClass}>{chunks}</span>,
          })}
        </h2>
        <p className={styles.subtitle}>{subtitle}</p>

        <div className={styles.checklist}>
          {loadingItems.map((item, i) => (
            <div
              key={item.name}
              className={styles.row}
              data-status={item.status}
              style={{ animationDelay: `${i * 0.08}s` }}
            >
              <span className={styles.ico}>{renderIcon(item.status)}</span>
              <span className={styles.lbl}>{item.displayName}</span>
              <span className={styles.meta}>{renderMetaText(item.status)}</span>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}

export default PreloadProgress
