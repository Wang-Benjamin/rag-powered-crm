/**
 * Email Profiles Context Type Definitions
 * Context and state types for email templates + settings caching
 */

import type { EmailTemplate, TemplateType } from './template'
import type { EmailSignature, EmailTrainingSamples } from './signature'

export interface EmailProfilesContextType {
  // Template data (cached per type)
  templates: { crm: EmailTemplate[]; leadgen: EmailTemplate[] }
  templatesLoading: boolean

  // Settings data (signature + training)
  signature: EmailSignature | null
  trainingSamples: EmailTrainingSamples | null
  settingsLoading: boolean

  // Template actions
  loadTemplates: (templateType: TemplateType, forceRefresh?: boolean) => Promise<void>
  refreshTemplates: (templateType: TemplateType) => Promise<void>
  updateTemplatesCache: (templateType: TemplateType, templates: EmailTemplate[]) => void

  // Settings actions
  loadSettings: (forceRefresh?: boolean) => Promise<void>
  updateSignatureCache: (signature: EmailSignature) => void
  updateTrainingSamplesCache: (samples: EmailTrainingSamples) => void
}
