'use client'

import { Toaster } from 'sonner'
import { AuthProvider } from '@/contexts/AuthContext'
import { NotificationProvider } from '@/contexts/NotificationContext'

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <NotificationProvider>
        {children}
        <Toaster position="bottom-right" visibleToasts={1} duration={2000} richColors />
      </NotificationProvider>
    </AuthProvider>
  )
}
