'use client'

import { CRMProvider } from '@/contexts/CRMContext'

export default function CRMLayout({ children }: { children: React.ReactNode }) {
  return (
    <CRMProvider>
      <div className="h-full overflow-hidden">{children}</div>
    </CRMProvider>
  )
}
