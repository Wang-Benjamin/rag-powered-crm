// Route to handle OAuth token exchange by proxying to user-settings backend
import { NextRequest, NextResponse } from 'next/server'
import { toCamelCase, toSnakeCase } from '@/lib/api/caseTransform'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

// OAuth has been migrated to user-settings service (port 8005)
// Use 127.0.0.1 instead of localhost for server-side requests in Next.js
const USER_SETTINGS_API_URL =
  process.env.NEXT_PUBLIC_USER_SETTINGS_API_URL?.replace('localhost', '127.0.0.1') ||
  'http://127.0.0.1:8005'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // Proxy the request to the user-settings backend (OAuth migrated from chatbot)
    // Convert camelCase request to snake_case for backend compatibility
    const response = await fetch(`${USER_SETTINGS_API_URL}/api/settings/oauth/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(toSnakeCase(body)),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Token exchange failed' }))
      console.error('Token exchange failed:', response.status, errorData)
      return NextResponse.json(
        { detail: errorData.detail || `Token exchange failed: ${response.status}` },
        { status: response.status }
      )
    }

    const data = await response.json()

    // Convert snake_case response to camelCase for frontend consistency
    return NextResponse.json(toCamelCase(data))
  } catch (error) {
    console.error('Token exchange error:', error)
    return NextResponse.json({ detail: 'Token exchange failed' }, { status: 500 })
  }
}
