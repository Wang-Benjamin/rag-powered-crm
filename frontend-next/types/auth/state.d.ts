/**
 * Auth State Type Definitions
 * Authentication state management types
 */

import { User } from './user'

export interface AuthState {
  user: User | null
  idToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  authError: string | null
  authProvider: string | null
}
