'use client'

import { useEffect, useState } from 'react'

/**
 * Runtime kit-token reader. For places where Tailwind class names don't work:
 * Recharts colors, SVG fills, inline styles, canvas drawing.
 *
 * Reads CSS custom properties off <html> inside useEffect and returns an
 * object keyed by kit token names. Re-reads when [data-theme] changes so
 * Recharts series flip with dark mode.
 *
 * Never call getComputedStyle at module scope — it throws on the SSR path.
 */

export type KitTokens = {
  bone: string
  paper: string
  cream: string
  fog: string
  rule: string
  mute: string
  ink: string
  deep: string
  accent: string
  accentHi: string
  accentLo: string
  gold: string
  goldLo: string
  threat: string
  threatHi: string
  threatLo: string
  info: string
  infoHi: string
  infoLo: string
}

const TOKEN_MAP: ReadonlyArray<readonly [keyof KitTokens, string]> = [
  ['bone', '--bone'],
  ['paper', '--paper'],
  ['cream', '--cream'],
  ['fog', '--fog'],
  ['rule', '--rule'],
  ['mute', '--mute'],
  ['ink', '--ink'],
  ['deep', '--deep'],
  ['accent', '--accent'],
  ['accentHi', '--accent-hi'],
  ['accentLo', '--accent-lo'],
  ['gold', '--gold'],
  ['goldLo', '--gold-lo'],
  ['threat', '--threat'],
  ['threatHi', '--threat-hi'],
  ['threatLo', '--threat-lo'],
  ['info', '--info'],
  ['infoHi', '--info-hi'],
  ['infoLo', '--info-lo'],
]

const EMPTY: KitTokens = {
  bone: '',
  paper: '',
  cream: '',
  fog: '',
  rule: '',
  mute: '',
  ink: '',
  deep: '',
  accent: '',
  accentHi: '',
  accentLo: '',
  gold: '',
  goldLo: '',
  threat: '',
  threatHi: '',
  threatLo: '',
  info: '',
  infoHi: '',
  infoLo: '',
}

export function useDesignTokens(): KitTokens {
  const [tokens, setTokens] = useState<KitTokens>(EMPTY)

  useEffect(() => {
    const root = document.documentElement

    const read = () => {
      const cs = getComputedStyle(root)
      const next = { ...EMPTY }
      for (const [key, cssVar] of TOKEN_MAP) {
        next[key] = cs.getPropertyValue(cssVar).trim()
      }
      setTokens(next)
    }

    read()

    const observer = new MutationObserver(read)
    observer.observe(root, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
    return () => observer.disconnect()
  }, [])

  return tokens
}
