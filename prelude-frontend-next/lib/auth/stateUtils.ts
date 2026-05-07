/**
 * Generate a random state parameter for OAuth flow
 */
function generateState(serviceName: string): string {
  const randomBytes = new Uint8Array(16)
  crypto.getRandomValues(randomBytes)
  const randomString = btoa(String.fromCharCode(...randomBytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')

  // Include service name in state for extraction later
  return `${serviceName}_${randomString}`
}

/**
 * Extract service name from state parameter
 */
export function extractServiceFromState(state: string): string | null {
  if (!state) return null

  // State format: serviceName_randomString
  const parts = state.split('_')
  if (parts.length < 2) return null

  // Service name is the first part
  const serviceName = parts[0]

  // Validate service name
  if (serviceName === 'google' || serviceName === 'microsoft') {
    return serviceName
  }

  return null
}

/**
 * Validate state parameter matches stored state
 */
function validateState(state: string): boolean {
  const storedState = sessionStorage.getItem('oauth_state')
  if (!storedState) return false

  // Clear stored state after validation
  sessionStorage.removeItem('oauth_state')

  return state === storedState
}

/**
 * Store state parameter for validation
 */
function storeState(state: string): void {
  sessionStorage.setItem('oauth_state', state)
}
