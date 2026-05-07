/**
 * Email Profiles API Service
 * Handles all email-related settings: templates, signatures, and AI training
 * Uses Next.js proxy to communicate with User Settings service (port 8005)
 */

import { settingsApiClient } from './client'
import type {
  EmailTemplate,
  EmailSignature,
  SignatureFields,
  EmailTrainingSamples,
  CreateTemplateData,
  UpdateTemplateData,
  GenerateResponse,
} from '@/types/email'

// ============================================================================
// Template API
// ============================================================================

export const templateApi = {
  /**
   * List all templates for a user
   */
  listTemplates: (
    channel = 'email',
    isActive = true,
    templateType?: string
  ): Promise<EmailTemplate[]> => {
    const params: Record<string, string> = {
      channel,
      isActive: isActive.toString(),
    }
    if (templateType) {
      params.templateType = templateType
    }
    return settingsApiClient.get('/templates', params)
  },

  /**
   * Create a new template
   */
  createTemplate: (data: CreateTemplateData): Promise<EmailTemplate> =>
    settingsApiClient.post('/templates', data),

  /**
   * Update an existing template
   */
  updateTemplate: (id: string, data: UpdateTemplateData): Promise<EmailTemplate> =>
    settingsApiClient.patch(`/templates/${id}`, data),

  /**
   * Delete a template (soft delete)
   */
  deleteTemplate: (id: string): Promise<{ message: string }> =>
    settingsApiClient.delete(`/templates/${id}`),

  /**
   * Generate template using AI
   */
  generateTemplate: (prompt: string, templateType = 'crm'): Promise<GenerateResponse> =>
    settingsApiClient.post('/templates/generate', { prompt }, { params: { templateType } }),

  /**
   * Duplicate a template (creates a copy)
   */
  duplicateTemplate: (id: string, newName: string): Promise<EmailTemplate> =>
    settingsApiClient.post(`/templates/${id}/branch`, { action: 'duplicateBase', newName }),
}

// ============================================================================
// Signature API
// ============================================================================

export const signatureApi = {
  /** Get the current user's email signature. Returns null when not set. */
  getSignature: (): Promise<EmailSignature | null> =>
    settingsApiClient.get('/signature/'),

  /** PUT — replace the entire signature. Omitted fields are cleared. */
  putSignature: (data: SignatureFields): Promise<EmailSignature> =>
    settingsApiClient.put('/signature/', data),

  /** PATCH — partial update. Only provided fields change. */
  patchSignature: (data: Partial<SignatureFields>): Promise<EmailSignature> =>
    settingsApiClient.patch('/signature/', data),

  /** DELETE — clear the signature. */
  deleteSignature: (): Promise<void> =>
    settingsApiClient.delete('/signature/'),

  /** Upload signature logo to GCS — unchanged endpoint. Returns the logo URL string,
   * which the frontend stores inside `signatureFields.logoUrl` before PUT/PATCH. */
  uploadLogo: async (file: File): Promise<{ logoUrl: string }> => {
    const formData = new FormData()
    formData.append('file', file)
    return settingsApiClient.upload('/signature/upload-logo', formData)
  },
}

// ============================================================================
// Email Training API
// ============================================================================

export const emailTrainingApi = {
  /**
   * Get saved email training samples
   */
  getTrainingSamples: (): Promise<EmailTrainingSamples> =>
    settingsApiClient.get('/email-training/'),

  /**
   * Save email training samples (3 email samples for AI personality training)
   */
  saveTrainingSamples: (data: EmailTrainingSamples): Promise<{ message: string }> =>
    settingsApiClient.post('/email-training/', data),
}

// ============================================================================
// SMTP Config API
// ============================================================================

export interface SmtpConfig {
  providerName: string
  smtpHost: string
  smtpPort: number
  smtpUser: string
  smtpPassword?: string
  imapHost?: string
  imapPort: number
  fromName?: string
  verified?: boolean
}

export interface SmtpTestResult {
  smtpOk: boolean
  smtpError?: string
  imapOk: boolean
  imapError?: string
}

export interface SmtpPreset {
  name: string
  smtpHost: string
  smtpPort: number
  imapHost: string
  imapPort: number
}

export const smtpApi = {
  getPresets: (): Promise<Record<string, SmtpPreset>> =>
    settingsApiClient.get('/smtp/presets'),

  getConfig: (): Promise<SmtpConfig | null> =>
    settingsApiClient.get('/smtp/config'),

  saveConfig: (data: SmtpConfig): Promise<SmtpConfig> =>
    settingsApiClient.post('/smtp/config', data),

  testConfig: (): Promise<SmtpTestResult> =>
    settingsApiClient.post('/smtp/test', {}),

  deleteConfig: (): Promise<{ status: string }> =>
    settingsApiClient.delete('/smtp/config'),
}

// ============================================================================
// Combined Export
// ============================================================================

const emailProfilesApi = {
  templates: templateApi,
  signatures: signatureApi,
  training: emailTrainingApi,
  smtp: smtpApi,
}

