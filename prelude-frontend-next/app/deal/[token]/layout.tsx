import type { Metadata } from 'next'
import { Toaster } from 'sonner'

export const metadata: Metadata = {
  title: 'Deal Room — Prelude',
  description: 'Manufacturer deal room',
}

export default function DealRoomLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link
        href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300..700;1,9..40,300..700&display=swap"
        rel="stylesheet"
      />
      <div className="min-h-screen bg-stone-50 text-stone-900 antialiased">{children}</div>
      <Toaster position="bottom-right" richColors />
    </>
  )
}
