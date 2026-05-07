const fmtPartsET = (d: Date): Record<string, number> =>
  Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      year: 'numeric', month: 'numeric', day: 'numeric',
      hour: 'numeric', minute: 'numeric', hour12: false,
    })
      .formatToParts(d)
      .filter((x) => x.type !== 'literal')
      .map((x) => [x.type, parseInt(x.value)])
  )

// Probe at 4 PM UTC on the target day to get the correct ET offset (handles DST).
function etToLocalString(etYear: number, etMonth: number, etDay: number, h: number, m: number): string {
  const probeUTC = new Date(Date.UTC(etYear, etMonth - 1, etDay, 16))
  const etProbe = fmtPartsET(probeUTC)
  const offsetMs =
    probeUTC.getTime() -
    Date.UTC(etProbe.year, etProbe.month - 1, etProbe.day, etProbe.hour, etProbe.minute)
  const targetUTC = Date.UTC(etProbe.year, etProbe.month - 1, etProbe.day, h, m) + offsetMs
  const d = new Date(targetUTC)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Next 11:59 AM ET — default for CRM / direct email schedule. */
export function getDefaultScheduleTime(): string {
  const et = fmtPartsET(new Date())
  const isPast = et.hour > 11 || (et.hour === 11 && et.minute >= 58)
  return etToLocalString(et.year, et.month, et.day + (isPast ? 1 : 0), 11, 59)
}

/**
 * Random minute in the 11:30 AM – 12:29 PM ET window — default for Buyers
 * (initial outreach). Spreads sends across the noon-ET inbox-check window to
 * avoid burst signatures.
 *
 * - Before 11:30 ET → today, uniform 11:30–12:29
 * - Inside window   → today, uniform max(now+5min, 11:30)–12:29
 * - ≥ 12:25 ET      → tomorrow, uniform 11:30–12:29 (too little remaining today)
 */
export function getNextBuyersMorningWindow(): string {
  const et = fmtPartsET(new Date())
  const etMin = et.hour * 60 + et.minute
  const WINDOW_START = 11 * 60 + 30 // 11:30 ET
  const WINDOW_END = 12 * 60 + 30   // 12:30 ET (exclusive upper bound)

  let day = et.day
  let lower = WINDOW_START
  if (etMin >= WINDOW_END - 5) {
    day += 1
  } else if (etMin >= WINDOW_START) {
    lower = etMin + 5
  }

  const minutes = lower + Math.floor(Math.random() * (WINDOW_END - lower))
  return etToLocalString(et.year, et.month, day, Math.floor(minutes / 60), minutes % 60)
}
