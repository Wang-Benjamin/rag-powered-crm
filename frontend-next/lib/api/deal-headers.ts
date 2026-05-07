import type { NextRequest } from 'next/server'

/**
 * Builds the forward-header set used by public deal proxy routes.
 *
 * Always seeds `Content-Type: application/json` and forwards `x-forwarded-for`
 * and `x-real-ip` when present on the inbound request. `referer` is only
 * forwarded when `opts.includeReferer` is true — track endpoints want it for
 * analytics, message endpoints intentionally do not.
 */
export function buildForwardHeaders(
  request: NextRequest,
  opts: { includeReferer?: boolean } = {}
): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const forwarded = request.headers.get('x-forwarded-for')
  const realIp = request.headers.get('x-real-ip')
  if (forwarded) headers['x-forwarded-for'] = forwarded
  if (realIp) headers['x-real-ip'] = realIp
  if (opts.includeReferer) {
    const referer = request.headers.get('referer')
    if (referer) headers['referer'] = referer
  }
  return headers
}
