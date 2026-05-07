import createMiddleware from 'next-intl/middleware'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { routing } from './i18n/routing'

const handleI18nRouting = createMiddleware(routing)

function resolveLocale(request: NextRequest): string {
  const pathname = request.nextUrl.pathname
  const localeMatch = pathname.match(/^\/(en|zh-CN)(?:\/|$)/)
  return localeMatch?.[1] || request.cookies.get('NEXT_LOCALE')?.value || 'en'
}

export default function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname
  const locale = resolveLocale(request)

  if (pathname === '/two-pager') {
    return NextResponse.redirect(new URL(`/${locale}/two-pager`, request.url))
  }

  return handleI18nRouting(request)
}

export const config = {
  matcher: [
    '/((?!api|auth/callback|deal|storefront|_next/static|_next/image|icon|apple-icon|manifest|sitemap|robots|opengraph-image|twitter-image|images|.*\\.(?:png|svg|ico|jpg|jpeg|webp|gif)$).*)',
  ],
}
