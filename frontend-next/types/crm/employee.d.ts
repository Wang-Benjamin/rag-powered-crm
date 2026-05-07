/**
 * Employee Type Definitions
 * Consolidated from multiple sources across the codebase
 *
 * Note: Use camelCase for all properties. The ApiClient automatically
 * converts between snake_case (backend) and camelCase (frontend).
 */

export interface Employee {
  // Primary identifiers
  id: string | number
  employeeId?: number

  // Name (support both full name and split)
  name: string
  firstName?: string
  lastName?: string

  // Contact and role
  email?: string
  role?: string
  position?: string
  department?: string
}
