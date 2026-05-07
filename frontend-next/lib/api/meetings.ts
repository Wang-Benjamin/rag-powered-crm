import { crmApiClient } from './client'
import type { MeetingData, SyncRequest } from '@/types/crm/meeting'

// Re-export types for backward compatibility
export type { MeetingData, SyncRequest } from '@/types/crm/meeting'

/**
 * Create a new meeting for a customer
 */
const createMeeting = async (
  customerId: string | number,
  meetingData: MeetingData,
  googleAccessToken: string
): Promise<any> => {
  return crmApiClient.post(`/customers/${customerId}/meetings`, meetingData, {
    headers: {
      'X-Google-Access-Token': googleAccessToken,
    },
  })
}

/**
 * Update an existing meeting
 */
const updateMeeting = async (
  interactionId: string | number,
  meetingData: MeetingData,
  googleAccessToken: string
): Promise<any> => {
  return crmApiClient.put(`/meetings/${interactionId}`, meetingData, {
    headers: {
      'X-Google-Access-Token': googleAccessToken,
    },
  })
}

/**
 * Delete a meeting (hard delete from both Google Calendar and CRM)
 */
const deleteMeeting = async (
  interactionId: string | number,
  googleAccessToken: string
): Promise<any> => {
  return crmApiClient.delete(`/meetings/${interactionId}`, {
    headers: {
      'X-Google-Access-Token': googleAccessToken,
    },
  })
}

/**
 * Get all meetings for a specific customer
 */
const getCustomerMeetings = async (customerId: string | number): Promise<any> => {
  return crmApiClient.get(`/customers/${customerId}/meetings`)
}

/**
 * Get a single meeting by interaction ID
 */
export const getMeetingById = async (interactionId: string | number): Promise<any> => {
  return crmApiClient.get(`/meetings/${interactionId}`)
}

/**
 * Sync meetings from Google Calendar to CRM for a specific customer
 */
const syncGoogleCalendar = async (
  customerId: string | number,
  googleAccessToken: string,
  syncRequest: SyncRequest = {}
): Promise<any> => {
  return crmApiClient.post(`/customers/${customerId}/sync-google-calendar`, syncRequest, {
    headers: {
      'X-Google-Access-Token': googleAccessToken,
    },
  })
}

/**
 * Sync all Google Calendar events across all customers
 */
const syncAllGoogleCalendar = async (
  googleAccessToken: string,
  syncRequest: SyncRequest = {}
): Promise<any> => {
  return crmApiClient.post(`/sync-all-google-calendar`, syncRequest, {
    headers: {
      'X-Google-Access-Token': googleAccessToken,
    },
  })
}
