import type { Metadata } from 'next'
import { NextIntlClientProvider } from 'next-intl'
import { Toaster } from 'sonner'
import enStorefront from '@/messages/en/storefront.json'

export const metadata: Metadata = {
  title: 'Storefront — Prelude',
  description: 'Manufacturer storefront on Prelude',
}

// Public buyer view is English-only by design. The seller's Prelude language
// drives only the resulting deal_name in /crm — not what the buyer sees.
export default function PublicStorefrontLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <NextIntlClientProvider locale="en" messages={{ storefront: enStorefront }}>
      <div className="min-h-screen bg-bone text-deep antialiased">{children}</div>
      <Toaster position="bottom-right" richColors />
    </NextIntlClientProvider>
  )
}
