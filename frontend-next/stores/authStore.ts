import { create } from 'zustand'
import { createJSONStorage, persist, subscribeWithSelector } from 'zustand/middleware'
import type { User, AuthState, AuthStoreState } from '@/types/auth'

export const useAuthStore = create<AuthStoreState>()(
  subscribeWithSelector(
    persist(
      (set, get) => ({
        // Initial state
        user: null,
        idToken: null,
        refreshToken: null,
        isAuthenticated: false,
        isLoading: true,
        authError: null,
        authProvider: null,

        // Actions
        setUser: (user) => set({ user }),
        setIdToken: (idToken) => set({ idToken }),
        setRefreshToken: (refreshToken) => set({ refreshToken }),
        setIsAuthenticated: (isAuthenticated) => set({ isAuthenticated }),
        setIsLoading: (isLoading) => set({ isLoading }),
        setAuthError: (authError) => set({ authError }),
        setAuthProvider: (authProvider) => set({ authProvider }),

        logout: () => {
          // Clear auth state
          set({
            user: null,
            idToken: null,
            refreshToken: null,
            isAuthenticated: false,
            authError: null,
            authProvider: null,
          })

          // Clear localStorage tokens
          if (typeof window !== 'undefined') {
            localStorage.removeItem('id_token')
            localStorage.removeItem('refresh_token')
            localStorage.removeItem('auth_service_name')
            localStorage.removeItem('auth_provider')

            // Clear OAuth tokens for both providers
            const providers = ['google', 'microsoft']
            providers.forEach((provider) => {
              localStorage.removeItem(`${provider}_access_token`)
              localStorage.removeItem(`${provider}_user_email`)
              localStorage.removeItem(`${provider}_connected`)
              localStorage.removeItem(`${provider}_auth_time`)
              localStorage.removeItem(`${provider}_refresh_token`)
            })

            // Clear lead gen cache from sessionStorage
            sessionStorage.removeItem('lead_gen_workflow_results')
            sessionStorage.removeItem('lead_gen_preview_results')
            sessionStorage.removeItem('lead_gen_active_view')
            sessionStorage.removeItem('lead_gen_prompt_input')
            sessionStorage.removeItem('lead_gen_max_results')
            sessionStorage.removeItem('leadgen_workflow_cache')
            sessionStorage.removeItem('leadgen_workflow_step')
            sessionStorage.removeItem('leadgen_history_refresh')
            sessionStorage.removeItem('leadgen_history_last_check')
            sessionStorage.removeItem('leadgen_history_cache')
          }
        },

        clearAuth: () => {
          set({
            user: null,
            idToken: null,
            refreshToken: null,
            isAuthenticated: false,
            authError: null,
            authProvider: null,
          })
        },

        initializeFromStorage: () => {
          if (typeof window === 'undefined') return

          const storedIdToken = localStorage.getItem('id_token')
          const storedRefreshToken = localStorage.getItem('refresh_token')
          const storedProvider = localStorage.getItem('auth_provider')

          if (storedIdToken) {
            // Parse user from token (simplified - in real implementation you'd decode JWT)
            try {
              const tokenParts = storedIdToken.split('.')
              if (tokenParts.length === 3) {
                const payload = JSON.parse(atob(tokenParts[1]))

                // Check if token is expired
                const currentTime = Math.floor(Date.now() / 1000)
                if (payload.exp && payload.exp < currentTime) {
                  console.log('Token expired, clearing auth state')
                  // Clear expired tokens
                  localStorage.removeItem('id_token')
                  localStorage.removeItem('refresh_token')
                  localStorage.removeItem('auth_provider')
                  set({
                    isAuthenticated: false,
                    isLoading: false,
                  })
                  return
                }

                const user: User = {
                  email: payload.email || payload.user_email || '',
                  userEmail: payload.user_email || payload.email || '',
                  name:
                    payload.name ||
                    `${payload.given_name || ''} ${payload.family_name || ''}`.trim(),
                  firstName: payload.given_name,
                  lastName: payload.family_name,
                  picture: payload.picture,
                  sub: payload.sub,
                }

                set({
                  user,
                  idToken: storedIdToken,
                  refreshToken: storedRefreshToken,
                  isAuthenticated: true,
                  authProvider: storedProvider,
                  isLoading: false,
                })
                return
              }
            } catch (error) {
              console.error('Error parsing stored token:', error)
              // Clear invalid tokens
              localStorage.removeItem('id_token')
              localStorage.removeItem('refresh_token')
              localStorage.removeItem('auth_provider')
            }
          }

          // No valid token found
          set({
            isAuthenticated: false,
            isLoading: false,
          })
        },

        updateTokens: (tokens) => {
          const { idToken, refreshToken } = tokens

          if (idToken) {
            set({ idToken })
            if (typeof window !== 'undefined') {
              localStorage.setItem('id_token', idToken)
            }

            // Parse user from new token
            try {
              const tokenParts = idToken.split('.')
              if (tokenParts.length === 3) {
                const payload = JSON.parse(atob(tokenParts[1]))
                const user: User = {
                  email: payload.email || payload.user_email || '',
                  userEmail: payload.user_email || payload.email || '',
                  name:
                    payload.name ||
                    `${payload.given_name || ''} ${payload.family_name || ''}`.trim(),
                  firstName: payload.given_name,
                  lastName: payload.family_name,
                  picture: payload.picture,
                  sub: payload.sub,
                }
                set({ user, isAuthenticated: true })
              }
            } catch (error) {
              console.error('Error parsing new token:', error)
            }
          }

          if (refreshToken) {
            set({ refreshToken })
            if (typeof window !== 'undefined') {
              localStorage.setItem('refresh_token', refreshToken)
            }
          }
        },
      }),
      {
        name: 'auth-storage',
        storage: createJSONStorage(() => {
          // Use sessionStorage for persistence to avoid hydration issues
          if (typeof window !== 'undefined') {
            return sessionStorage
          }
          return {
            getItem: () => null,
            setItem: () => {},
            removeItem: () => {},
          }
        }),
        partialize: (state) => ({
          user: state.user,
          isAuthenticated: state.isAuthenticated,
          authProvider: state.authProvider,
        }),
      }
    )
  )
)

// Auth initialization is handled in the dashboard layout to avoid hydration issues
