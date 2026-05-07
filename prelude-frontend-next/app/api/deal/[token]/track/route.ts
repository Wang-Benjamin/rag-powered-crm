import { NextRequest, NextResponse } from 'next/server'
import { buildForwardHeaders } from '@/lib/api/deal-headers'

const CRM_SERVICE_URL =
  process.env.NEXT_PUBLIC_CRM_API_URL?.replace('localhost', '127.0.0.1') || 'http://127.0.0.1:8003'

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ token: string }> }
) {
  const { token } = await params
  const targetUrl = `${CRM_SERVICE_URL}/api/crm/public/deal/${token}/track`

  try {
    // Forward client headers for accurate analytics
    const headers = buildForwardHeaders(request, { includeReferer: true })

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
    console.error('Track proxy error:', error)
    return NextResponse.json({ success: false }, { status: 502 })
  }
}
