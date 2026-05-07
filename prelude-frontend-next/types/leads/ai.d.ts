export interface AISuggestions {
  insights?: string[]
  citations?: string[]
  generatedAt: string
  leadId?: string
  confidence?: number
}

export interface AIParsedIntent {
  industry?: string
  location?: string
  keywords?: string[]
  companySize?: string
  targetRoles?: string[]
  isValid: boolean
  confidence: number
}
