/**
 * Activity Type Definitions
 * Includes Activity, Note, Interaction, and CachedSummary types
 */

export type ActivityType = 'email' | 'call' | 'meeting' | 'note'
export type Direction = 'incoming' | 'outgoing'

export interface Activity {
  id: string
  activityType: ActivityType
  title?: string
  description?: string
  content?: string
  body?: string
  createdAt: string
  employeeName?: string
  customerId?: string
  dealId?: string
  interactionId?: string
  noteId?: string
  source?: string
  direction?: Direction
}

export interface Note {
  id: string
  title: string
  content: string
  starred: boolean
  createdAt: string
  updatedAt?: string
  employeeName?: string
  customerId?: string
  dealId?: string
}

export interface Interaction {
  id: string
  type: 'email' | 'call' | 'meeting'
  title?: string
  subject?: string
  body?: string
  content?: string
  description?: string
  theme?: string
  direction?: Direction
  fromEmail?: string
  toEmail?: string
  createdAt: string
  customerId?: string
  employeeId?: number
  employeeName?: string
  gmailMessageId?: string
  metadata?: {
    interactionId?: string
    theme?: string
    subject?: string
    direction?: string
    sourceName?: string
    sourceType?: string
    fromEmail?: string
  }
  [key: string]: any
}

export interface CachedSummary {
  customerId: string | number
  summary?: string
  createdAt?: string
  updatedAt?: string
  periodDays?: number
}
