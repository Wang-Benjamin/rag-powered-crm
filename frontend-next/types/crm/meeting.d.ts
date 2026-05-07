/**
 * Meeting Type Definitions
 * Types for CRM meeting functionality
 */

export interface MeetingData {
  title: string
  description?: string
  startTime: string
  endTime: string
  location?: string
  attendees?: string[]
}

export interface SyncRequest {
  timeMin?: string
  timeMax?: string
}
