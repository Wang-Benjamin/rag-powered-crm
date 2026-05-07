/**
 * Pagination Type Definitions
 * Used for paginated lists and tables
 */

import type { ApiResponse } from './api'

/**
 * Pagination configuration
 */
export interface PaginationConfig {
  currentPage: number
  totalPages: number
  itemsPerPage: number
  totalItems: number
}

/**
 * Paginated API response wrapper
 * Combines ApiResponse with pagination metadata
 */
export interface PaginatedResponse<T> extends ApiResponse<T> {
  total: number
  page: number
  limit: number
}
