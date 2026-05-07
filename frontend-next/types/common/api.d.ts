/**
 * API Response and Error Type Definitions
 * Consolidated from lib/api/client.ts and components/crm/types.ts
 */

/**
 * Generic API Response structure
 * Used across all backend services for consistent response handling
 */
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  message?: string
  total?: number
  page?: number
  limit?: number
}

/**
 * API Error structure
 * Used for consistent error handling across API clients
 */
export interface ApiError {
  message: string
  status: number
  data?: any
}

/**
 * FastAPI Error Response structure
 * Standard error format returned by FastAPI backend services
 */
export interface FastApiError {
  detail: string
}

/**
 * API Client Configuration
 * Used by ApiClient class constructor
 */
export interface ApiClientConfig {
  baseUrl?: string
  timeout?: number
  retries?: number
  headers?: Record<string, string>
}

/**
 * Request Configuration
 * Used for individual API requests
 */
export interface RequestConfig extends RequestInit {
  timeout?: number
  retries?: number
  params?: Record<string, any>
}

/**
 * User Data from database service
 */
export interface UserData {
  user: {
    databaseName: string
    [key: string]: any
  }
  [key: string]: any
}
