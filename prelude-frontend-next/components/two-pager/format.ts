// Tons (real US-customs weight, annualized) — replaces the old USD
// estimate that came from a hardcoded FOB price table. Above 1,000吨 we
// switch to "千吨" so the digit budget stays small for Page 1 stat cards.
export function formatTons(n: number | null): string {
  if (n === null || n === undefined) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}百万吨`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}千吨`
  if (n >= 10) return `${Math.round(n).toLocaleString()}吨`
  return `${n.toFixed(1)}吨`
}

function formatInt(n: number | null): string {
  if (n === null || n === undefined) return '—'
  return n.toLocaleString()
}

export function formatPct(n: number | null): string {
  if (n === null || n === undefined) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}%`
}
