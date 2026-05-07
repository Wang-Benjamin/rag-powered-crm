import { NextRequest, NextResponse } from 'next/server'

const CRM_SERVICE_URL =
  process.env.NEXT_PUBLIC_CRM_API_URL?.replace('localhost', '127.0.0.1') ||
  'http://127.0.0.1:8003'

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params
  const targetUrl = `${CRM_SERVICE_URL}/api/crm/public/storefront/${encodeURIComponent(slug)}`

  try {
    const response = await fetch(targetUrl, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    const data = await response.text()
    return new NextResponse(data, {
      status: response.status,
      headers: { 'Content-Type': 'application/json' },
    })
  } catch (error) {
    console.error('Public storefront proxy error:', error)
    return NextResponse.json({ error: 'Failed to load storefront' }, { status: 502 })
  }
}
