import { NextRequest, NextResponse } from 'next/server'

const CRM_SERVICE_URL =
  process.env.NEXT_PUBLIC_CRM_API_URL?.replace('localhost', '127.0.0.1') || 'http://127.0.0.1:8003'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ token: string }> }
) {
  const { token } = await params
  const targetUrl = `${CRM_SERVICE_URL}/api/crm/public/deal/${token}`

  try {
    const response = await fetch(targetUrl, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    })

    const data = await response.text()
    return new NextResponse(data, {
      status: response.status,
      headers: { 'Content-Type': 'application/json' },
    })
  } catch (error) {
    console.error('Public deal room proxy error:', error)
    return NextResponse.json({ error: 'Failed to load deal room' }, { status: 502 })
  }
}
