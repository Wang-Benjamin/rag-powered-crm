import camelcaseKeys from 'camelcase-keys'
import snakecaseKeys from 'snakecase-keys'

/**
 * Convert snake_case response to camelCase
 * Handles nested objects and arrays automatically
 */
export function toCamelCase<T>(data: unknown): T {
  if (data === null || data === undefined) return data as T
  if (typeof data !== 'object') return data as T

  return camelcaseKeys(data as Record<string, unknown>, { deep: true }) as T
}

/**
 * Convert camelCase request body to snake_case
 */
export function toSnakeCase<T>(data: unknown): T {
  if (data === null || data === undefined) return data as T
  if (typeof data !== 'object') return data as T
  if (data instanceof FormData || data instanceof Blob) return data as T

  return snakecaseKeys(data as Record<string, unknown>, { deep: true }) as T
}
