/**
 * Deal Type Definitions
 * Consolidated from multiple sources across the codebase
 *
 * Note: Backend returns snake_case which is auto-converted to camelCase
 * by ApiClient. Only camelCase properties are needed here.
 */

export interface Deal {
  // Primary identifiers
  id: string | number
  dealId?: string | number

  // Deal info
  title?: string
  dealName?: string
  description?: string

  // Client info
  clientName?: string
  clientEmail?: string
  clientCompany?: string
  customerId?: string
  clientId?: string | number

  // Value
  amount?: number
  valueUsd?: number
  dealValue?: number
  hsCode?: string
  fobPrice?: number
  fobCurrency?: string
  landedPrice?: number
  quantity?: number
  moq?: number

  // Room status and status
  roomStatus?: string
  status?: string
  probability?: number

  // Deal room
  shareToken?: string
  viewCount?: number
  lastViewedAt?: string
  quoteData?: {
    productName?: string
    hsCode?: string
    moq?: number
    options?: any[]
    [key: string]: any
  }

  // Dates
  expectedCloseDate?: string
  lastContactDate?: string

  // Assignment
  assignedEmployeeName?: string
  assignedEmployeeId?: number | null
  salesmanName?: string
  salesmanId?: number
  employeeId?: number

  // Additional data
  notes?: string
  activities?: any[]

  // Timestamps
  createdAt?: string
  updatedAt?: string
}
