/**
 * Token Type Definitions
 * JWT and OAuth token-related types
 */

export interface DecodedToken {
  exp: number
  iat: number
  email?: string
  name?: string
  picture?: string
  sub?: string
}

/**
 * Raw token response from OAuth provider (snake_case per OAuth 2.0 spec)
 * This is normalized to TokenResponse via normalizeTokenResponse() in AuthContext
 */
export interface RawTokenResponse {
  id_token: string
  refresh_token?: string
  expires_in?: number
  oauth_expires_in?: number
  oauth_access_token?: string
  oauth_refresh_token?: string
  scope?: string
  user_info?: {
    email: string
  }
}

/**
 * Normalized token response (camelCase for frontend use)
 * Created by normalizeTokenResponse() from RawTokenResponse
 */
export interface TokenResponse {
  idToken: string
  refreshToken?: string
  expiresIn?: number
  oauthExpiresIn?: number
  oauthAccessToken?: string
  oauthRefreshToken?: string
  scope?: string
  userInfo?: {
    email: string
  }
}
