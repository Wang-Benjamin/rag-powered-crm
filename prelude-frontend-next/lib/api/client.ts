/**
 * Base API Client for Next.js Frontend
 * Handles authentication, error handling, and common API patterns
 */

import { toCamelCase, toSnakeCase } from './caseTransform'
import type { ApiClientConfig, RequestConfig } from '@/types/common'

export class ApiClientError extends Error {
  constructor(
    message: string,
    public status: number = 500,
    public data?: any
  ) {
    super(message)
    this.name = 'ApiClientError'
  }
}

/**
 * Base API Client Class
 */
export class ApiClient {
  protected config: Required<ApiClientConfig>

  constructor(config: ApiClientConfig = {}) {
    this.config = {
      baseUrl: '',
      timeout: 90000, // 90 seconds — cache-miss two-pager can take 30-60s
      retries: 3,
      headers: {},
      ...config,
    }
  }

  /**
   * Get authentication headers for requests
   */
  protected async getAuthHeaders(): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.config.headers,
    }

    try {
      // Get JWT token from localStorage (matches existing auth pattern)
      if (typeof window !== 'undefined') {
        const token = localStorage.getItem('id_token')
        if (token) {
          headers['Authorization'] = `Bearer ${token}`
        }
      }
    } catch (error) {
      console.warn('Failed to get auth token:', error)
    }

    return headers
  }

  /**
   * Execute fetch with timeout support
   */
  private async fetchWithTimeout(
    url: string,
    options: RequestInit,
    timeoutMs: number
  ): Promise<Response> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      })
      clearTimeout(timeoutId)
      return response
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new ApiClientError('Request timeout', 408)
      }
      throw error
    }
  }

  /**
   * Handle API response
   */
  private async handleResponse<T>(response: Response): Promise<T> {
    const contentType = response.headers.get('content-type')
    let data: any

    try {
      if (contentType?.includes('application/json')) {
        const json = await response.json()

        // Special handling for suggestedMappings to preserve CSV column names
        if (json && json.suggested_mappings) {
          const preservedMappings = json.suggested_mappings
          data = toCamelCase(json)
          // Restore the original keys for suggestedMappings
          data.suggestedMappings = preservedMappings
        } else {
          data = toCamelCase(json)
        }
      } else {
        data = await response.text()
      }
    } catch {
      throw new ApiClientError('Failed to parse response', response.status)
    }

    if (!response.ok) {
      // Handle structured error details: { code: "...", message: "..." }
      const detail = data?.detail
      const detailMessage = detail && typeof detail === 'object' ? detail.message : detail
      const errorMessage =
        detailMessage ||
        data?.message ||
        data?.error ||
        `HTTP ${response.status}: ${response.statusText}`

      throw new ApiClientError(errorMessage, response.status, data)
    }

    return data
  }

  /**
   * Build URL with query params (converts camelCase to snake_case)
   */
  private buildUrlWithParams(endpoint: string, params?: Record<string, any>): string {
    if (!params || Object.keys(params).length === 0) {
      return endpoint
    }
    const queryString = new URLSearchParams(
      toSnakeCase(params) as Record<string, string>
    ).toString()
    const separator = endpoint.includes('?') ? '&' : '?'
    return `${endpoint}${separator}${queryString}`
  }

  /**
   * Make authenticated API request with retry logic
   */
  async request<T = any>(endpoint: string, config: RequestConfig = {}): Promise<T> {
    const {
      timeout = this.config.timeout,
      retries = this.config.retries,
      ...requestOptions
    } = config

    const url = this.config.baseUrl + endpoint
    const authHeaders = await this.getAuthHeaders()

    const options: RequestInit = {
      ...requestOptions,
      headers: {
        ...authHeaders,
        ...requestOptions.headers,
      },
    }

    let lastError: Error | null = null

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const response = await this.fetchWithTimeout(url, options, timeout)
        return await this.handleResponse<T>(response)
      } catch (error) {
        lastError = error as Error

        // Don't retry on client errors (4xx) - these are not transient
        if (error instanceof ApiClientError && error.status >= 400 && error.status < 500) {
          throw error
        }

        // Don't retry on the last attempt
        if (attempt === retries) {
          break
        }

        // Exponential backoff delay
        const delay = Math.min(1000 * Math.pow(2, attempt), 10000)
        await new Promise((resolve) => setTimeout(resolve, delay))
      }
    }

    throw lastError || new ApiClientError('Request failed after all retries')
  }

  /**
   * GET request
   * Params are automatically converted from camelCase to snake_case
   */
  async get<T = any>(
    endpoint: string,
    params?: Record<string, any>,
    config?: RequestConfig
  ): Promise<T> {
    const url = this.buildUrlWithParams(endpoint, params)
    return this.request<T>(url, {
      method: 'GET',
      ...config,
    })
  }

  /**
   * POST request
   * Supports query params via config.params (auto-converted to snake_case)
   */
  async post<T = any>(endpoint: string, data?: any, config?: RequestConfig): Promise<T> {
    const { params, ...restConfig } = config || {}
    const url = this.buildUrlWithParams(endpoint, params)
    return this.request<T>(url, {
      method: 'POST',
      body: data ? JSON.stringify(toSnakeCase(data)) : undefined,
      ...restConfig,
    })
  }

  /**
   * PUT request
   * Supports query params via config.params (auto-converted to snake_case)
   */
  async put<T = any>(endpoint: string, data?: any, config?: RequestConfig): Promise<T> {
    const { params, ...restConfig } = config || {}
    const url = this.buildUrlWithParams(endpoint, params)
    return this.request<T>(url, {
      method: 'PUT',
      body: data ? JSON.stringify(toSnakeCase(data)) : undefined,
      ...restConfig,
    })
  }

  /**
   * PATCH request
   * Supports query params via config.params (auto-converted to snake_case)
   */
  async patch<T = any>(endpoint: string, data?: any, config?: RequestConfig): Promise<T> {
    const { params, ...restConfig } = config || {}
    const url = this.buildUrlWithParams(endpoint, params)
    return this.request<T>(url, {
      method: 'PATCH',
      body: data ? JSON.stringify(toSnakeCase(data)) : undefined,
      ...restConfig,
    })
  }

  /**
   * DELETE request
   * Supports query params via config.params (auto-converted to snake_case)
   */
  async delete<T = any>(endpoint: string, config?: RequestConfig): Promise<T> {
    const { params, ...restConfig } = config || {}
    const url = this.buildUrlWithParams(endpoint, params)
    return this.request<T>(url, {
      method: 'DELETE',
      ...restConfig,
    })
  }

  /**
   * GET request that returns a Blob (for file downloads)
   * Use this for endpoints that return files (CSV, PDF, etc.)
   */
  async getBlob(
    endpoint: string,
    params?: Record<string, any>,
    config?: RequestConfig
  ): Promise<{ blob: Blob; filename: string }> {
    const url = this.buildUrlWithParams(endpoint, params)
    const authHeaders = await this.getAuthHeaders()
    const { timeout = this.config.timeout } = config || {}

    const response = await this.fetchWithTimeout(
      this.config.baseUrl + url,
      {
        method: 'GET',
        headers: authHeaders,
      },
      timeout
    )

    if (!response.ok) {
      throw new ApiClientError(`HTTP ${response.status}: ${response.statusText}`, response.status)
    }

    const blob = await response.blob()
    const contentDisposition = response.headers.get('content-disposition')
    const filename = contentDisposition
      ? contentDisposition.split('filename=')[1]?.replace(/"/g, '') || 'download'
      : 'download'

    return { blob, filename }
  }

  /**
   * Upload file with FormData
   */
  async upload<T = any>(endpoint: string, formData: FormData, config?: RequestConfig): Promise<T> {
    const { params, ...restConfig } = config || {}
    const url = this.buildUrlWithParams(endpoint, params)

    // Get auth token directly without Content-Type header
    let authHeader: Record<string, string> = {}
    try {
      if (typeof window !== 'undefined') {
        const token = localStorage.getItem('id_token')
        if (token) {
          authHeader['Authorization'] = `Bearer ${token}`
        }
      }
    } catch (error) {
      console.warn('Failed to get auth token:', error)
    }

    // Call request with skipAuthHeaders flag to prevent Content-Type from being added
    return this.requestWithoutContentType<T>(url, {
      method: 'POST',
      body: formData,
      headers: authHeader,
      ...restConfig,
    })
  }

  /**
   * Internal method for requests that need custom Content-Type handling (like file uploads)
   */
  private async requestWithoutContentType<T = any>(
    endpoint: string,
    config: RequestConfig = {}
  ): Promise<T> {
    const {
      timeout = this.config.timeout,
      retries = this.config.retries,
      ...requestOptions
    } = config

    const url = this.config.baseUrl + endpoint

    const options: RequestInit = {
      ...requestOptions,
      headers: {
        ...requestOptions.headers, // Only use provided headers, don't add Content-Type
      },
    }

    let lastError: Error | null = null

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const response = await this.fetchWithTimeout(url, options, timeout)
        return await this.handleResponse<T>(response)
      } catch (error) {
        lastError = error as Error

        // Don't retry on client errors (4xx) - these are not transient
        if (error instanceof ApiClientError && error.status >= 400 && error.status < 500) {
          throw error
        }

        if (attempt === retries) {
          break
        }

        const delay = Math.min(1000 * Math.pow(2, attempt), 10000)
        await new Promise((resolve) => setTimeout(resolve, delay))
      }
    }

    throw lastError || new ApiClientError('Request failed after all retries')
  }
}

/**
 * API Service URLs - Client components use Next.js proxy routes
 *
 * Per CLAUDE.md: "Client Components should NOT talk to FastAPI directly"
 * All client-side requests go through Next.js API proxy routes which:
 * - Handle authentication validation
 * - Forward requests to backend services
 * - Avoid CORS issues in production
 */
const API_ENDPOINTS = {
  CRM: '/api/proxy/crm',
  LEADS: '/api/proxy/leads',
  SETTINGS: '/api/proxy/settings',
} as const

/**
 * Pre-configured API clients for each service
 */
export const crmApiClient = new ApiClient({ baseUrl: API_ENDPOINTS.CRM })
export const leadsApiClient = new ApiClient({ baseUrl: API_ENDPOINTS.LEADS })
export const settingsApiClient = new ApiClient({ baseUrl: API_ENDPOINTS.SETTINGS })

/**
 * Default API client (can be configured with any base URL)
 */
const apiClient = new ApiClient()

/**
 * Helper function to handle API errors consistently
 */
function handleApiError(error: unknown): never {
  if (error instanceof ApiClientError) {
    throw error
  }

  if (error instanceof Error) {
    throw new ApiClientError(error.message)
  }

  throw new ApiClientError('Unknown API error')
}

/**
 * Server-side API client (for use in API routes and SSR)
 * Does not use NextAuth session, requires manual token passing
 */
class ServerApiClient extends ApiClient {
  private token?: string

  constructor(config: ApiClientConfig = {}, token?: string) {
    super(config)
    this.token = token
  }

  protected async getAuthHeaders(): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.config.headers,
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    return headers
  }

  /**
   * Set the authentication token
   */
  setToken(token: string): void {
    this.token = token
  }

  /**
   * Clear the authentication token
   */
  clearToken(): void {
    this.token = undefined
  }
}

