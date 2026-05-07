/**
 * Email Thread Types - Thread tracking for Gmail/Outlook conversations
 */

/**
 * Summary of an email thread for list view
 */
export interface EmailThreadSummary {
  threadId: string
  customerId?: number
  leadId?: string
  subject: string
  lastActivity: string
  emailCount: number
  sentCount: number
  receivedCount: number
  fromEmail: string
  toEmail: string
  lastDirection: 'sent' | 'received'
  preview: string
  lastRfcMessageId: string | null
}

/**
 * Individual email within a thread
 */
export interface ThreadEmail {
  emailId: number
  fromEmail: string
  toEmail: string
  subject: string
  body: string
  direction: 'sent' | 'received'
  createdAt: string
  rfcMessageId: string | null
  threadId: string
  inReplyTo: string | null
}

/**
 * Context for replying to a thread
 * Used to maintain conversation threading when sending replies
 */
export interface ReplyContext {
  threadId: string
  rfcMessageId: string
  subject: string
}

/**
 * Response from thread list endpoint
 */
export interface ThreadListResponse {
  threads: EmailThreadSummary[]
  total: number
}

/**
 * Response from thread detail endpoint
 */
export interface ThreadDetailResponse {
  threadId: string
  emails: ThreadEmail[]
  total: number
}
