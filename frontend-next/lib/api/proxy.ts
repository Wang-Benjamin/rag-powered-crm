import { NextRequest, NextResponse } from 'next/server'
import { validateAuth } from '@/lib/auth/auth-options'
import { locales } from '@/i18n/config'

interface ProxyConfig {
  serviceUrl: string
  apiPrefix: string
}

export function createProxyHandler(config: ProxyConfig) {
  return async function proxyRequest(
    request: NextRequest,
    { params }: { params: Promise<{ path?: string[] }> }
  ) {
    const isAuthorized = await validateAuth(request)

    if (!isAuthorized) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { path: pathArray } = await params
    const path = pathArray?.join('/') || ''
    const searchParams = new URL(request.url).searchParams.toString()

    const cleanPath = path ? `/${path}` : ''
    const targetUrl = `${config.serviceUrl}${config.apiPrefix}${cleanPath}${searchParams ? `?${searchParams}` : ''}`

    try {
      const contentType = request.headers.get('content-type')
      const isFormData = contentType?.includes('multipart/form-data')

      const headers = new Headers()

      const authHeader = request.headers.get('authorization')
      if (authHeader) {
        headers.set('Authorization', authHeader)
      }

      if (contentType) {
        headers.set('Content-Type', contentType)
      } else {
        headers.set('Content-Type', 'application/json')
      }

      const forwardHeaders = ['user-agent', 'accept', 'accept-language', 'x-google-access-token']
      forwardHeaders.forEach((header) => {
        const value = request.headers.get(header)
        if (value) headers.set(header, value)
      })

      const raw = request.cookies.get('NEXT_LOCALE')?.value
      const locale = locales.includes(raw as any) ? raw! : 'en'
      headers.set('X-User-Locale', locale)

      let body: BodyInit | null | undefined
      if (request.method !== 'GET' && request.method !== 'HEAD') {
        if (isFormData) {
          body = await request.arrayBuffer()
        } else {
          body = await request.text()
        }
      }

      const response = await fetch(targetUrl, {
        method: request.method,
        headers,
        body,
      })

      // Stream SSE responses instead of buffering
      const responseContentType = response.headers.get('content-type') || ''
      if (responseContentType.includes('text/event-stream') && response.body) {
        return new Response(response.body, {
          status: response.status,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            Connection: 'keep-alive',
          },
        })
      }

      const responseBody = await response.text()
      const nextResponse = new NextResponse(responseBody, {
        status: response.status,
        statusText: response.statusText,
      })

      const responseHeaders = ['content-type', 'cache-control', 'location']
      responseHeaders.forEach((header) => {
        const value = response.headers.get(header)
        if (value) nextResponse.headers.set(header, value)
      })

      return nextResponse
    } catch (error) {
      const serviceName = config.apiPrefix.replace(/^\/api\//, '') || 'proxy'
      console.error(`${serviceName} proxy error:`, error)
      return NextResponse.json({ error: 'Service unavailable' }, { status: 503 })
    }
  }
}
