import { createProxyHandler } from '@/lib/api/proxy'

const SERVICE_URL =
  process.env.NEXT_PUBLIC_BACKEND_LEAD_API_URL?.replace('localhost', '127.0.0.1') ||
  'http://127.0.0.1:9000'

const handler = createProxyHandler({ serviceUrl: SERVICE_URL, apiPrefix: '/api/leads' })

export const GET = handler
export const POST = handler
export const PUT = handler
export const DELETE = handler
export const PATCH = handler
