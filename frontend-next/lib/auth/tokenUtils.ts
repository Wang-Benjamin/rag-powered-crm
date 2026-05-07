import type { DecodedToken, TokenResponse, User } from '@/types/auth'
import { toWorkspaceId } from '@/lib/auth/workspaceId'

export type AuthProvider = 'password' | 'wechat'

/**
 * Decode a JWT token (without verification - client-side only)
 */
export function decodeToken(token: string): DecodedToken | null {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch (error) {
    console.error('Error decoding token:', error)
    return null
  }
}

/**
 * Check if a token is expired
 */
export function isTokenExpired(token: string, bufferSeconds: number = 0): boolean {
  const decoded = decodeToken(token)
  if (!decoded || !decoded.exp) {
    return true // Consider invalid tokens as expired
  }

  const currentTime = Date.now() / 1000
  return decoded.exp < currentTime + bufferSeconds
}

/**
 * Get time until token expiration in milliseconds
 */
export function getTimeUntilExpiration(token: string, bufferSeconds: number = 0): number {
  const decoded = decodeToken(token)
  if (!decoded || !decoded.exp) {
    return 0
  }

  const expirationTime = (decoded.exp - bufferSeconds) * 1000
  const currentTime = Date.now()
  return Math.max(0, expirationTime - currentTime)
}

/**
 * Store tokens in localStorage
 */
export function storeTokens(tokens: TokenResponse): void {
  if (tokens.idToken) {
    localStorage.setItem('id_token', tokens.idToken)
  }

  if (tokens.refreshToken) {
    localStorage.setItem('refresh_token', tokens.refreshToken)
  }

  if (tokens.expiresIn) {
    localStorage.setItem('token_expires_at', (Date.now() + tokens.expiresIn * 1000).toString())
  }
}

/**
 * Clear tokens from localStorage
 */
export function clearTokens(): void {
  localStorage.removeItem('id_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('token_expires_at')
}

/**
 * Extract user information from ID token
 */
export function extractUserFromToken(token: string): User | null {
  const decoded = decodeToken(token)
  if (!decoded) {
    return null
  }

  return {
    email: decoded.email || '',
    name: decoded.name,
    picture: decoded.picture,
    sub: decoded.sub,
  }
}

/**
 * Get stored ID token
 */
export function getStoredIdToken(): string | null {
  return localStorage.getItem('id_token')
}

/**
 * Get stored refresh token
 */
function getStoredRefreshToken(): string | null {
  return localStorage.getItem('refresh_token')
}

/**
 * Check if user is authenticated (has valid token)
 */
function isAuthenticated(): boolean {
  const token = getStoredIdToken()
  return token !== null && !isTokenExpired(token)
}

/**
 * Build the workspace landing path from an id token.
 * Decodes the token, derives the workspace id from the email, and returns
 * `/workspace/{workspaceId}/crm` (optionally prefixed with a locale segment).
 * Returns `null` if the token cannot be decoded — callers choose the fallback.
 */
export function workspacePathFromToken(
  idToken: string,
  opts?: { locale?: string }
): string | null {
  const decoded = decodeToken(idToken)
  if (!decoded) return null
  const userEmail = (decoded.email || (decoded as { user_email?: string }).user_email) ?? null
  const workspaceId = toWorkspaceId(userEmail)
  const path = `/workspace/${workspaceId}/crm`
  return opts?.locale ? `/${opts.locale}${path}` : path
}

/**
 * Persist login tokens + auth-provider metadata to localStorage.
 * Matches the shape that login/register endpoints return (snake_case).
 */
function persistLoginTokens(
  data: { id_token: string; refresh_token: string },
  provider: AuthProvider
): void {
  localStorage.setItem('id_token', data.id_token)
  localStorage.setItem('refresh_token', data.refresh_token)
  localStorage.setItem('auth_provider', provider)
  localStorage.setItem('auth_service_name', provider)
}
