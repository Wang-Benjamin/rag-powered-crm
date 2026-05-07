import { NextRequest, NextResponse } from 'next/server'
import { buildForwardHeaders } from '@/lib/api/deal-headers'

const CRM_SERVICE_URL =
  process.env.NEXT_PUBLIC_CRM_API_URL?.replace('localhost', '127.0.0.1') ||
  'http://127.0.0.1:8003'

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params
  const targetUrl = `${CRM_SERVICE_URL}/api/crm/public/storefront/${encodeURIComponent(slug)}/quote-request`

  try {
    const headers = buildForwardHeaders(request)
    const body = await request.text()
    const response = await fetch(targetUrl, {
      method: 'POST',
      headers,
      body,
    })

    const data = await response.text()
    return new NextResponse(data, {
      status: response.status,
      headers: { 'Content-Type': 'application/json' },
    })
  } catch (error) {
    console.error('Quote request proxy error:', error)
    return NextResponse.json({ error: 'Failed to submit quote request' }, { status: 502 })
  }
}
