/**
 * Email Template Type Definitions
 * Consolidated from types/email.ts, lib/api/emailprofiles.ts, and lib/api/settings.ts
 */

export type TemplateLevel = 0 | 1

export type EmailChannel = 'email' | 'sms' | 'push'

export type TemplateType = 'crm' | 'leadgen'

export type TemplateCategory = 'purpose' | 'user'

export interface EmailTemplate {
  id: string
  name: string
  subject: string
  body: string
  description?: string
  channel: EmailChannel
  templateType: TemplateType
  templateCategory: TemplateCategory
  promptInstructions?: string
  isShared: boolean
  isActive: boolean
  sendCount: number
  userEmail: string
  createdAt: string
  updatedAt: string
  lastUsedAt?: string
  level: TemplateLevel
  parentId: string | null
  rootId: string | null
}

export interface CreateTemplateData {
  name: string
  subject: string
  body: string
  description?: string
  channel?: EmailChannel
  templateType?: TemplateType
  templateCategory?: TemplateCategory
  promptInstructions?: string
  isShared?: boolean
}

export interface UpdateTemplateData {
  name?: string
  subject?: string
  body?: string
  description?: string
  isActive?: boolean
  isShared?: boolean
}
