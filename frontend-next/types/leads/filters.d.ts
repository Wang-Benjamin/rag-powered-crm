export interface GetLeadsOptions {
  page?: number
  perPage?: number
  status?: string | null
  search?: string | null
  industry?: string | null
  location?: string | null
  includeRecent?: boolean
  userEmail?: string | null
}

export interface LeadFilterParams {
  search?: string
  searchColumns?: string[]
  status?: string
  columnFilters?: Record<string, any>
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export interface EnrichLeadsParams {
  companyIds?: string[]
  companies?: any[]
  jobTitles?: string[] | null
  department?: string | null
  seniorityLevel?: string | null
}
