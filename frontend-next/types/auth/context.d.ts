/**
 * Auth Context and Store Type Definitions
 * Context and store state types for authentication management
 */

import type { User, AuthState } from './index'

/**
 * Auth Store State interface - extends base AuthState with actions
 * Used by Zustand auth store
 */
export interface AuthStoreState extends AuthState {
  // Actions
  setUser: (user: User | null) => void
  setIdToken: (token: string | null) => void
  setRefreshToken: (token: string | null) => void
  setIsAuthenticated: (isAuth: boolean) => void
  setIsLoading: (loading: boolean) => void
  setAuthError: (error: string | null) => void
  setAuthProvider: (provider: string | null) => void
  logout: () => void
  clearAuth: () => void

  // Helper methods
  initializeFromStorage: () => void
  updateTokens: (tokens: { idToken?: string; refreshToken?: string }) => void
}

/**
 * Auth Context Type - provided by AuthProvider
 * Used by useAuth hook consumers
 */
export interface AuthContextType {
  user: User | null
  idToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  authError: string | null
  authProvider: string | null
  loginWith: (serviceName: string) => Promise<void>
  handleAuthCode: (code: string, state: string) => Promise<boolean>
  logout: () => void
  authFetch: (url: string, options?: RequestInit) => Promise<Response>
}
