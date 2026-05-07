/**
 * Semantic signal helper — single source of truth for status / score / trend
 * color choices. Never pick --accent / --gold / --threat / --info inline.
 *
 * Kit v2026.07 four-tier system:
 *   positive → accent (verified, on-track, score ≥ 80)
 *   warn     → gold   (medium, stale, score 60-79)
 *   neutral  → mute   (unknown, score < 60, declines — minus carries the load)
 *   complete → deep   (finalized, closed)
 *   threat   → threat (destructive / terminal failure) — rare, max 1 per row
 *   info     → info   (syncing / indexing) — rare, must pair with motion dot
 *
 * If the kit ever demotes gold to amber or bumps --accent hue, this file
 * is the one place that changes.
 */

export type SignalTier =
  | 'positive'
  | 'warn'
  | 'neutral'
  | 'complete'
  | 'threat'
  | 'info'

/** Full state-chip class stack (uses kit `.chip` + `.chip-*` from tokens.css). */
export function signalChipClass(tier: SignalTier): string {
  const map: Record<SignalTier, string> = {
    positive: 'chip chip-accent',
    warn: 'chip chip-gold',
    neutral: 'chip chip-neutral',
    complete: 'chip chip-dark',
    threat: 'chip chip-threat',
    info: 'chip chip-info',
  }
  return map[tier]
}

/** Tailwind text-color utility for a signal tier. */
export function signalTextClass(tier: SignalTier): string {
  const map: Record<SignalTier, string> = {
    positive: 'text-accent',
    warn: 'text-gold',
    neutral: 'text-mute',
    complete: 'text-deep',
    threat: 'text-threat',
    info: 'text-info',
  }
  return map[tier]
}

/** Tailwind background utility for a signal tier (low-saturation variant). */
function signalBgClass(tier: SignalTier): string {
  const map: Record<SignalTier, string> = {
    positive: 'bg-accent-lo',
    warn: 'bg-gold-lo',
    neutral: 'bg-cream',
    complete: 'bg-deep',
    threat: 'bg-threat-lo',
    info: 'bg-info-lo',
  }
  return map[tier]
}

/** 0-100 score → tier. Kit rule: 80+ positive, 60-79 warn, else neutral.
 *  No red for low scores — minus sign / neutral grey carries declines. */
export function scoreTier(score: number): SignalTier {
  if (score >= 80) return 'positive'
  if (score >= 60) return 'warn'
  return 'neutral'
}

/** Delta sign → tier. Never threat for a normal decline. */
export function trendTier(delta: number): SignalTier {
  return delta >= 0 ? 'positive' : 'neutral'
}
