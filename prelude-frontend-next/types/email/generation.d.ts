/**
 * Email Generation Type Definitions
 * Consolidated from lib/api/crm.ts and lib/api/emailprofiles.ts
 */

export interface EmailGenerationRequest {
  customerId: number
  emailType?: string
  customPrompt?: string
  tone?: string
  includePersonalization?: boolean
}

export interface EmailGenerationResponse {
  subject: string
  body: string
  tone: string
  keyPoints: string[]
  personalizationNotes: string
  confidence: number
  tokens?: string[]
  description?: string
}

/**
 * Response from AI template generation endpoint
 * Used by templateApi.generateTemplate()
 */
export interface GenerateResponse {
  subject: string
  body: string
  name?: string
  description?: string
}
