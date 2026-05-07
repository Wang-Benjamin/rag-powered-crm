export interface LeadEmailData {
  leadId: string
  toEmail: string
  subject: string
  body: string
  provider?: 'gmail' | 'outlook'
}

export interface EmailOptions {
  limit?: number
  daysBack?: number
  direction?: 'sent' | 'received' | 'all'
}

export interface EmailData {
  statusChanged?: boolean
  newStatus?: string
  sentTo?: string
  positiveRepliesCount?: number
}
