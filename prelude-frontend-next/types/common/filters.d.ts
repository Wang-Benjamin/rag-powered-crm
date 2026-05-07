/**
 * Filter and Sort Type Definitions
 * Used for table filtering and sorting functionality
 */

/**
 * Filter option for dropdown/select filters
 */
export interface FilterOption {
  value: string
  label: string
  count?: number
}

/**
 * Sort configuration for table columns
 */
export interface SortConfig {
  key: string | null
  direction: 'asc' | 'desc'
}
