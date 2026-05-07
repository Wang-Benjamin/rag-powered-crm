/**
 * Email Domain Types - Barrel Export
 */

export type {
  EmailTemplate,
  CreateTemplateData,
  UpdateTemplateData,
  TemplateLevel,
  EmailChannel,
  TemplateType,
} from './template'

export type {
  EmailGenerationRequest,
  EmailGenerationResponse,
  GenerateResponse,
} from './generation'

export type { EmailSignature, SignatureFields, EmailTrainingSamples } from './signature'

export type { EmailSyncState } from './sync'

export type { EmailProfilesContextType } from './context'

export type {
  EmailThreadSummary,
  ThreadEmail,
  ReplyContext,
  ThreadListResponse,
  ThreadDetailResponse,
} from './thread'
