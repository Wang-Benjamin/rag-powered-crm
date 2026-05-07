import type { Personnel } from './personnel'
import type { BolDetailContext } from './bol'

// Aligned with backend config/constants.py LeadStatus enum
// Includes frontend-only statuses ('hot', 'converted') for UI purposes
export type LeadStatus =
  | 'new'
  | 'qualified'
  | 'hot'
  | 'cold'
  | 'contacted'
  | 'converted'
  | 'lost'
  | 'syncedToCrm'

// Employee assignment from employee_lead_links table
export interface AssignedEmployee {
  employeeId: number
  employeeName: string
  email?: string
  role?: string
  department?: string
  assignedAt?: string
  notes?: string
  matchedBy?: string
  status?: string
}

export interface Lead {
  // Primary identifiers
  id: string | number
  leadId?: string | number

  // Company info
  company: string
  companyName?: string
  name?: string
  position?: string
  location?: string
  industry?: string

  // Contact info (via personnel records)
  website?: string
  websites?: string[]

  // Status and metadata
  status?: LeadStatus | string
  source?: string
  companySize?: string
  revenue?: string
  employeesCount?: number

  // Scoring
  score?: number
  finalScore?: number
  completenessScore?: number
  completionScore?: number
  reliabilityScore?: number

  // Personnel
  personnel?: Personnel[]

  // Assignment (many-to-many via employee_lead_links)
  assignedEmployees?: AssignedEmployee[]
  // Backward compatibility - primary (most recent) assigned employee
  assignedEmployeeName?: string
  assignedEmployeeId?: string | number

  // CRM Readiness (analyzed by CRM Recommender Agent based on email engagement)
  readyToCrm?: boolean

  // ImportYeti context (from buyer pipeline)
  importContext?: {
    totalShipments?: number
    matchingShipments?: number
    mostRecentShipment?: string
    topPorts?: string[]
    topProducts?: string[]
    hsCodes?: string[]
    totalSuppliers?: number
    topSuppliers?: string[]
  }
  supplierContext?: {
    suppliers?: Array<{
      name: string
      country: string
      share: number
      shipments12M: number
      shipments1224M: number
      trend: number
      weightKg?: number
      teu?: number
    }>
    enrichedAt?: string
    bolCompanySlug?: string
  }

  // Deep enrichment detail (populated at add-to-pipeline time for detail view)
  bolDetailContext?: BolDetailContext

  // Visibility (server-stamped per PRD §2 rendering contract)
  isBlurred?: boolean

  // Timestamps
  createdAt?: string
  updatedAt?: string
}

export interface LeadStats {
  total: number
  qualified: number
  hot: number
  totalPersonnel: number
  companiesWithPersonnel: number
  avgPersonnelPerCompany: number | string
}
