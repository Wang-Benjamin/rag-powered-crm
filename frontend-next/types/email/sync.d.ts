/**
 * Email Sync Type Definitions
 * Consolidated from contexts/EmailSyncProvider.tsx
 */

/**
 * State and methods for email synchronization
 */
export interface EmailSyncState {
  emailAccounts: unknown[]
  isLoading: boolean
  isSyncing: boolean
  error: string | null
  lastSyncTime: Date | null
  syncEnabled: boolean
  setSyncEnabled: (enabled: boolean) => void
  crmSyncEnabled: boolean
  setCrmSyncEnabled: (enabled: boolean) => void
  performSync: () => Promise<void>
  performCrmSync: () => Promise<void>
  registerSyncCallback: (callback: (result: unknown) => void) => () => void
  registerCrmSyncCallback: (callback: (result: unknown) => void) => () => void
  /** Persistent sync error (survives page reload). Null when no error. */
  syncError: string | null
  /** Clear the persistent sync error (called on user dismiss or reconnect). */
  clearSyncError: () => void
}
