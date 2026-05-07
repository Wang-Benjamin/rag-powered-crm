'use client'

import { LeadProvider } from '@/contexts/LeadContext'

export default function LeadsLayout({ children }: { children: React.ReactNode }) {
  return (
    <LeadProvider>
      <div className="h-full overflow-hidden">{children}</div>
    </LeadProvider>
  )
}
