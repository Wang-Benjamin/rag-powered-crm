/**
 * Translator shape accepted by deal-status helpers. Typed loosely so this
 * works with next-intl's typed `Translator` (which expects a known namespace
 * key union) without forcing callers to weaken their typing.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Translator = (key: any) => string

/**
 * Maps a deal room status (`draft`, `sent`, `viewed`, `quote_requested`,
 * `closed-won`, `closed-lost`) to its localized label, falling back to the
 * raw status string when unknown or empty.
 */
export function formatRoomStatus(
  status: string | undefined | null,
  t: Translator
): string {
  if (!status) return ''
  const map: Record<string, string> = {
    draft: t('dealStages.draft'),
    sent: t('dealStages.sent'),
    viewed: t('dealStages.viewed'),
    quote_requested: t('dealStages.quoteRequested'),
    'closed-won': t('dealStages.closedWon'),
    'closed-lost': t('dealStages.closedLost'),
  }
  return map[status] || status
}
