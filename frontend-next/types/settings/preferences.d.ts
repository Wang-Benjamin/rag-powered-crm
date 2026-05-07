/**
 * AI Preferences Types
 * AI personality and behavior configuration type definitions
 */

export interface ToneSettings {
  formality?: string
  conciseness?: string
  proactiveness?: string
  onBrandPhrases?: string
  avoidPhrases?: string
}

export interface GuardrailSettings {
  /** Predefined chip IDs + custom entries (prefixed with "custom:"). */
  topicsToAvoid?: string[]
  hardRestrictions?: string[]
  prohibitedStatements?: string[]
}

export interface AudienceSettings {
  idealCustomers?: string
  roles?: string
  products?: string
}

export interface AdditionalContextSettings {
  additionalContext?: string
}

export interface AIPreferences {
  tone: ToneSettings
  guardrails: GuardrailSettings
  audience: AudienceSettings
  additionalContext: AdditionalContextSettings
  aiSummary?: string
  isComplete?: boolean
  createdAt?: string
  updatedAt?: string
}
