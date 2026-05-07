/**
 * Frontend types mirroring the backend ingestion drafts.
 * Keep in sync with prelude-user-settings/src/services/document_ingestion/schemas.py.
 */

export type JobKind =
  | 'company_profile'
  | 'product_csv'
  | 'product_pdf'
  | 'certification'

export type JobStatus =
  | 'queued'
  | 'processing'
  | 'ready_for_review'
  | 'committed'
  | 'failed'
  | 'discarded'

export type BusinessType = 'manufacturer' | 'trading' | 'oem' | 'odm' | 'other'

export interface CompanyProfileDraft {
  companyNameEn?: string
  companyNameLocal?: string
  yearFounded?: number
  headquartersLocation?: string
  employeeCountRange?: string
  businessType?: BusinessType
  productDescription?: string
  mainMarkets?: string[]
  factoryLocation?: string
  factorySizeSqm?: number
  productionCapacity?: string
  certificationsMentioned?: string[]
  keyCustomersMentioned?: string[]
}

export interface PriceRange {
  min?: number
  max?: number
  currency?: string
  unit?: string
}

export interface ProductRecordDraft {
  name: string
  description?: string
  specs?: Record<string, string>
  imageUrl?: string
  moq?: number
  priceRange?: PriceRange
  hsCodeSuggestion?: string
}

export interface ProductCatalogDraft {
  products: ProductRecordDraft[]
  columnMapping?: Record<string, string>
  /** CSV-lane only: included during the proposed-mapping phase. */
  proposedMapping?: Record<string, string>
  /** CSV-lane only: raw header strings from the user's file. */
  sourceHeaders?: string[]
  /** CSV-lane only: first few rows for preview. */
  sampleRows?: Record<string, string>[]
  /** CSV-lane only: total row count in the uploaded file. */
  rowCount?: number
  /** CSV-lane only: `.csv` or `.xlsx`. */
  fileExt?: string
}

export interface CertificationDraft {
  certType?: string
  certNumber?: string
  issuingBody?: string
  issueDate?: string
  expiryDate?: string
  notes?: string
}

export type DraftPayload =
  | CompanyProfileDraft
  | ProductCatalogDraft
  | CertificationDraft

export interface IngestionJob {
  jobId: string
  kind: JobKind
  status: JobStatus
  draftPayload?: DraftPayload | null
  error?: string | null
  sourceUrl?: string
  createdAt?: string
  updatedAt?: string
}

/**
 * Five visible states in the dropzone. `ready` collapses the backend
 * `ready_for_review` into a user-facing "we filled these in" state.
 */
export type DropzoneState =
  | 'idle'
  | 'uploading'
  | 'processing'
  | 'ready'
  | 'failed'
