'use client'

import React, { createContext, useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  decodeToken,
  isTokenExpired,
  getTimeUntilExpiration,
  storeTokens,
  clearTokens,
  extractUserFromToken,
} from '@/lib/auth/tokenUtils'
import { clearAllAppCookies } from '@/utils/cookie-manager'
import { syncLocaleFromBackend } from '@/lib/locale'
import { extractServiceFromState } from '@/lib/auth/stateUtils'
import { crmApiClient, leadsApiClient } from '@/lib/api/client'
import { toast } from 'sonner'
import type { User, TokenResponse, AuthContextType } from '@/types/auth'

// Helper function to normalize token response from snake_case to camelCase
function normalizeTokenResponse(tokens: any): TokenResponse {
  return {
    idToken: tokens.id_token || tokens.idToken,
    refreshToken: tokens.refresh_token || tokens.refreshToken,
    expiresIn: tokens.expires_in || tokens.expiresIn,
    oauthExpiresIn: tokens.oauth_expires_in || tokens.oauthExpiresIn,
    oauthAccessToken: tokens.oauth_access_token || tokens.oauthAccessToken,
    oauthRefreshToken: tokens.oauth_refresh_token || tokens.oauthRefreshToken,
    userInfo: tokens.user_info || tokens.userInfo,
    scope: tokens.scope,
  }
}

// Create context
export const AuthContext = createContext<AuthContextType | null>(null)

// Buffer time before token expiration to trigger refresh (in seconds)
const REFRESH_TOKEN_BUFFER_SECONDS = 5 * 60 // 5 minutes

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // State for authentication
  const [user, setUser] = useState<User | null>(null)
  const [idToken, setIdToken] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState<string | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [authError, setAuthError] = useState<string | null>(null)
  const [authProvider, setAuthProvider] = useState<string | null>(null)

  // Refs for token refresh timer
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Clear invalid tokens on app start
  useEffect(() => {
    const storedIdToken = localStorage.getItem('id_token')
    if (storedIdToken && isTokenExpired(storedIdToken)) {
      console.log('Clearing expired tokens on app start')
      clearTokens()
      setAuthError('Session expired. Please log in again.')
    }
  }, [])

  // Clear auth data on logout
  const logout = useCallback(() => {
    console.log('Logging out...')
    clearTokens()
    setIdToken(null)
    setRefreshToken(null)
    setUser(null)
    setIsAuthenticated(false)
    setAuthError(null)
    setAuthProvider(null)

    // Clear provider info from localStorage
    localStorage.removeItem('auth_service_name')
    localStorage.removeItem('auth_provider')

    // Clear OAuth tokens for both providers
    ;['google', 'microsoft'].forEach((provider) => {
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
    sessionStorage.removeItem('workspace_preloaded')
    console.log('🗑️ Cleared lead gen cache on logout')

    // Clear all app cookies
    clearAllAppCookies()
    console.log('🍪 Cleared all app cookies on logout')

    // Clear the refresh timer
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current)
      refreshTimerRef.current = null
    }
  }, [])

  // Refresh tokens using refresh token
  const refreshTokens = useCallback(
    async (refreshTokenStr: string): Promise<boolean> => {
      console.log('Attempting to refresh tokens...')
      setAuthError(null)
      setIsLoading(true)

      try {
        const provider = localStorage.getItem('auth_provider') || 'google'

        // Call Next.js API route which proxies to user-settings service
        const response = await fetch('/api/auth/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: '',
            refreshToken: refreshTokenStr,
            provider: provider,
          }),
        })

        if (!response.ok) {
          const errorData = await response
            .json()
            .catch(() => ({ detail: 'Failed to refresh token' }))
          console.error('Backend token refresh failed:', response.status, errorData)
          throw new Error(errorData.detail || `Failed to refresh token: ${response.status}`)
        }

        const rawTokens = await response.json()
        const tokens = normalizeTokenResponse(rawTokens)

        // Store and set the new tokens
        storeTokens(tokens)
        setIdToken(tokens.idToken)

        if (tokens.oauthRefreshToken) {
          setRefreshToken(tokens.oauthRefreshToken)
          localStorage.setItem('refresh_token', tokens.oauthRefreshToken)
        }

        // Update OAuth tokens if returned
        if (tokens.oauthAccessToken) {
          localStorage.setItem(`${provider}_access_token`, tokens.oauthAccessToken)
          localStorage.setItem(`${provider}_user_email`, tokens.userInfo?.email || '')
          localStorage.setItem(`${provider}_connected`, 'true')
          localStorage.setItem(`${provider}_auth_time`, Date.now().toString())

          if (tokens.oauthRefreshToken) {
            localStorage.setItem(`${provider}_refresh_token`, tokens.oauthRefreshToken)
          }
        }

        // Decode the new ID token and update user info
        const decoded = decodeToken(tokens.idToken)
        if (decoded) {
          setUser(extractUserFromToken(tokens.idToken))
          setIsAuthenticated(true)

          // Schedule next refresh
          const expiresAtSeconds = tokens.oauthExpiresIn
            ? Date.now() / 1000 + tokens.oauthExpiresIn
            : decoded.exp
          const timeUntilRefresh =
            expiresAtSeconds * 1000 - Date.now() - REFRESH_TOKEN_BUFFER_SECONDS * 1000

          if (timeUntilRefresh > 0) {
            if (refreshTimerRef.current) {
              clearTimeout(refreshTimerRef.current)
            }
            console.log(`Scheduling token refresh in ${timeUntilRefresh / 1000} seconds.`)
            refreshTimerRef.current = setTimeout(async () => {
              console.log('Attempting scheduled token refresh...')
              try {
                await refreshTokens(localStorage.getItem('refresh_token') || '')
              } catch {
                console.warn('Scheduled refresh triggered but no refresh token available.')
              }
            }, timeUntilRefresh)
          }

          console.log('Tokens refreshed successfully.')
          return true
        } else {
          console.error('Failed to decode new ID token after refresh.')
          logout()
          setAuthError('Failed to process new token after refresh.')
          return false
        }
      } catch (error) {
        console.error('Error refreshing token:', error)
        logout()
        setAuthError((error as Error).message || 'An error occurred during token refresh.')
        return false
      } finally {
        setIsLoading(false)
      }
    },
    [logout]
  )

  // Schedule token refresh before expiration
  const scheduleTokenRefresh = useCallback(
    (timeUntilRefresh: number) => {
      if (timeUntilRefresh <= 0) {
        console.log('Token expiration within buffer, not scheduling future refresh.')
        return
      }

      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current)
      }

      refreshTimerRef.current = setTimeout(async () => {
        try {
          const storedRefreshToken = localStorage.getItem('refresh_token')
          if (storedRefreshToken) {
            await refreshTokens(storedRefreshToken)
          }
        } catch {
          console.warn('Scheduled refresh triggered but no refresh token available.')
        }
      }, timeUntilRefresh)
    },
    [refreshTokens]
  )

  // Handle Authorization Code Callback
  const handleAuthCode = useCallback(
    async (code: string, state: string): Promise<boolean> => {
      console.log(`Handling auth code. State: ${state}`)
      setAuthError(null)
      setIsLoading(true)

      try {
        const serviceName = extractServiceFromState(state)
        if (!serviceName) {
          console.error('Could not extract service name from state parameter.')
          throw new Error('Invalid state parameter.')
        }
        console.log(`Extracted service name from state: ${serviceName}`)

        console.log('PKCE code verifier is handled by the backend.')
        console.log(
          `Sending token exchange request - provider: ${serviceName}, code: ${code.substring(0, 20)}...`
        )

        // Call Next.js API route which proxies to user-settings service
        const response = await fetch('/api/auth/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: code,
            provider: serviceName,
          }),
        })

        if (!response.ok) {
          const errorData = await response
            .json()
            .catch(() => ({ detail: 'Unknown error during code exchange' }))
          console.error('Backend token exchange failed:', response.status, errorData)
          throw new Error(
            errorData.detail || `Token exchange failed with status: ${response.status}`
          )
        }

        const rawTokens = await response.json()
        const tokens = normalizeTokenResponse(rawTokens)

        // Store the received tokens and the service name
        storeTokens(tokens)
        localStorage.setItem('auth_service_name', serviceName)
        localStorage.setItem('auth_provider', serviceName)
        window.dispatchEvent(new Event('prelude:auth-changed'))

        // Store OAuth refresh token for JWT refresh
        if (tokens.oauthRefreshToken) {
          localStorage.setItem('refresh_token', tokens.oauthRefreshToken)
          setRefreshToken(tokens.oauthRefreshToken)
        }

        // Store OAuth tokens for email API access
        if (tokens.oauthAccessToken) {
          localStorage.setItem(`${serviceName}_access_token`, tokens.oauthAccessToken)
          localStorage.setItem(`${serviceName}_user_email`, tokens.userInfo?.email || '')
          localStorage.setItem(`${serviceName}_connected`, 'true')
          localStorage.setItem(`${serviceName}_auth_time`, Date.now().toString())

          if (tokens.oauthRefreshToken) {
            localStorage.setItem(`${serviceName}_refresh_token`, tokens.oauthRefreshToken)
          }

          // Save OAuth tokens to backend databases
          const savePromises = []

          // Save to CRM service
          savePromises.push(
            crmApiClient.post('/oauth/save-tokens', {
              provider: serviceName,
              accessToken: tokens.oauthAccessToken,
              refreshToken: tokens.oauthRefreshToken,
              expiresIn: tokens.oauthExpiresIn || 3600,
              scope: tokens.scope,
            })
          )

          // Save to lead_gen service
          savePromises.push(
            leadsApiClient.post('/oauth/save-tokens', {
              provider: serviceName,
              accessToken: tokens.oauthAccessToken,
              refreshToken: tokens.oauthRefreshToken,
              expiresIn: tokens.oauthExpiresIn || 3600,
              scope: tokens.scope,
            })
          )

          // Fire-and-forget: don't block auth flow waiting for backend token saves
          Promise.allSettled(savePromises)
            .then((results) => {
              if (results[0].status === 'fulfilled') {
                console.log(`✅ Saved ${serviceName} OAuth tokens to CRM service`)
              } else {
                console.error(
                  `⚠️ Failed to save ${serviceName} tokens to CRM service`,
                  results[0].reason
                )
              }
              if (results[1].status === 'fulfilled') {
                console.log(`✅ Saved ${serviceName} OAuth tokens to lead_gen service`)
              } else {
                console.error(
                  `⚠️ Failed to save ${serviceName} tokens to lead_gen service`,
                  results[1].reason
                )
              }
              // Pre-locale context: hardcoded English is intentional (runs during auth before locale is determined)
              const allFailed = results.every(r => r.status === 'rejected')
              if (allFailed) {
                toast.error('Failed to save authentication tokens. Some features may not work correctly.')
              }
            })
        }

        // Update AuthProvider state
        setIdToken(tokens.idToken)

        // Decode the ID token and set user info
        const decoded = decodeToken(tokens.idToken)
        if (decoded) {
          setUser(extractUserFromToken(tokens.idToken))
          setIsAuthenticated(true)
          setAuthProvider(serviceName)

          // Schedule the next token refresh
          const expiresAtSeconds = tokens.oauthExpiresIn
            ? Date.now() / 1000 + tokens.oauthExpiresIn
            : decoded.exp
          const timeUntilRefresh =
            expiresAtSeconds * 1000 - Date.now() - REFRESH_TOKEN_BUFFER_SECONDS * 1000

          if (timeUntilRefresh > 0) {
            if (refreshTimerRef.current) {
              clearTimeout(refreshTimerRef.current)
            }
            console.log(`Scheduling token refresh in ${timeUntilRefresh / 1000} seconds.`)
            refreshTimerRef.current = setTimeout(async () => {
              console.log('Attempting scheduled token refresh...')
              try {
                await refreshTokens(localStorage.getItem('refresh_token') || '')
              } catch {
                console.warn('Scheduled refresh triggered but no refresh token available.')
              }
            }, timeUntilRefresh)
          }

          // Sync locale preference from backend to cookie
          syncLocaleFromBackend().catch(() => {})

          console.log('Auth code exchange successful.')
          return true
        } else {
          console.error('Received invalid ID token during code exchange.')
          logout()
          setAuthError('Failed to process received token.')
          return false
        }
      } catch (error) {
        console.error('Error handling auth code:', error)
        clearTokens()
        setIdToken(null)
        setRefreshToken(null)
        setUser(null)
        setIsAuthenticated(false)
        setAuthError((error as Error).message || 'Login failed. Please try again.')
        return false
      } finally {
        setIsLoading(false)
      }
    },
    [logout, refreshTokens]
  )

  // Initiate Login Redirect
  const loginWith = useCallback(async (serviceName: string) => {
    console.log(`Initiating login with service: ${serviceName}`)
    setAuthError(null)
    setIsLoading(true)

    try {
      console.log('PKCE code verifier generation handled by the backend.')
      console.log('About to make fetch request...')

      // Call Next.js API route which proxies to user-settings service
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          service: serviceName,
        }),
      })

      console.log('Fetch request completed, response:', response)

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ detail: 'Failed to get authorization URL' }))
        console.error('Backend login initiation failed:', response.status, errorData)
        throw new Error(errorData.detail || `Failed to start login flow: ${response.status}`)
      }

      const data = await response.json()
      const authorizationUrl = data.authorizationUrl

      if (!authorizationUrl) {
        console.error('Backend response missing authorizationUrl.')
        throw new Error('Backend did not provide authorization URL.')
      }

      console.log(`Received authorization URL from backend. Redirecting to: ${authorizationUrl}`)
      window.location.assign(authorizationUrl)
    } catch (error) {
      console.error(`Error initiating login for service "${serviceName}":`, error)
      setIsLoading(false)
      setAuthError((error as Error).message || 'Failed to start login flow.')
    }
  }, [])

  // Authenticated Fetch Wrapper
  const authFetch = useCallback(
    async (url: string, options: RequestInit = {}): Promise<Response> => {
      if (!idToken) {
        console.warn('Attempted authFetch without ID token. User not authenticated.')
        throw new Error('Not authenticated')
      }

      const authOptions: RequestInit = {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${idToken}`,
        },
      }

      try {
        const response = await fetch(url, authOptions)

        if (response.status === 401) {
          console.log('authFetch received 401. Attempting token refresh...')

          if (refreshToken) {
            const refreshSuccess = await refreshTokens(refreshToken)

            if (refreshSuccess) {
              console.log('Token refreshed successfully. Retrying original request...')
              const newIdToken = localStorage.getItem('id_token')

              if (newIdToken) {
                const retryOptions: RequestInit = {
                  ...options,
                  headers: {
                    ...options.headers,
                    Authorization: `Bearer ${newIdToken}`,
                  },
                }
                return fetch(url, retryOptions)
              } else {
                console.error(
                  'Token refresh succeeded but could not retrieve new ID token from storage.'
                )
                logout()
                throw new Error('Failed to retrieve new token after refresh.')
              }
            } else {
              console.error('Token refresh failed.')
              throw new Error(authError || 'Token refresh failed, user logged out.')
            }
          } else {
            console.warn('authFetch received 401 but no refresh token available. Logging out.')
            logout()
            throw new Error('Not authenticated, no refresh token available.')
          }
        }

        return response
      } catch (error) {
        console.error('Authenticated fetch request failed:', error)
        throw error
      }
    },
    [idToken, refreshToken, refreshTokens, logout, authError]
  )

  // Initialization Effect
  useEffect(() => {
    const storedIdToken = localStorage.getItem('id_token')
    const storedRefreshToken = localStorage.getItem('refresh_token')
    const storedServiceName = localStorage.getItem('auth_service_name')

    if (storedIdToken) {
      const expired = isTokenExpired(storedIdToken, REFRESH_TOKEN_BUFFER_SECONDS)

      if (expired && storedRefreshToken && storedServiceName) {
        refreshTokens(storedRefreshToken)
      } else if (expired) {
        logout()
      } else {
        setIdToken(storedIdToken)
        setRefreshToken(storedRefreshToken)
        setUser(extractUserFromToken(storedIdToken))
        setIsAuthenticated(true)

        const storedProvider = localStorage.getItem('auth_provider') || 'google'
        setAuthProvider(storedProvider)

        const timeUntilRefresh = getTimeUntilExpiration(storedIdToken, REFRESH_TOKEN_BUFFER_SECONDS)
        scheduleTokenRefresh(timeUntilRefresh)

        // Sync locale preference from backend to cookie on app init
        syncLocaleFromBackend().catch(() => {})
      }
    } else {
      setIsAuthenticated(false)
      setUser(null)
      setIdToken(null)
      setRefreshToken(null)
      localStorage.removeItem('auth_service_name')
    }

    setIsLoading(false)
  }, [logout, refreshTokens, scheduleTokenRefresh])

  // Cleanup Effect
  useEffect(() => {
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current)
      }
    }
  }, [])

  // Context Value
  const contextValue = useMemo<AuthContextType>(
    () => ({
      user,
      idToken,
      isAuthenticated,
      isLoading,
      authError,
      authProvider,
      loginWith,
      handleAuthCode,
      logout,
      authFetch,
    }),
    [
      user,
      idToken,
      isAuthenticated,
      isLoading,
      authError,
      authProvider,
      loginWith,
      handleAuthCode,
      logout,
      authFetch,
    ]
  )

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
}
