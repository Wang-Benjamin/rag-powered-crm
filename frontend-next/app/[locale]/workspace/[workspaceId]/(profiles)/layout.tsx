'use client'

import { EmailProfilesProvider } from '@/contexts/EmailProfilesContext'

export default function ProfilesLayout({ children }: { children: React.ReactNode }) {
  return (
    <EmailProfilesProvider>
      <div className="h-full overflow-hidden">{children}</div>
    </EmailProfilesProvider>
  )
}
