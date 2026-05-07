import { settingsApiClient } from './client'
import { getCachedData, setCachedData, clearCachedData } from '@/utils/data-cache'
import type {
  InvitationData,
  UserInvitationsResponse,
  OnboardingStatus,
  OnboardingProgress,
} from '@/types/settings'

const CACHE_DURATION = 60 * 60 * 1000 // 1 hour

export const invitationsApi = {
  /**
   * Get invitations for a specific user email
   * @param email - The email address to search for
   * @param forceRefresh - Force refresh from server, bypassing cache
   * @returns Object containing user data and invitations array: {user: {...}, invitations: [...]}
   */
  async getUserInvitations(email: string, forceRefresh = false): Promise<UserInvitationsResponse> {
    try {
      // Check cache first if not forcing refresh
      if (!forceRefresh) {
        const cached = getCachedData<UserInvitationsResponse>(
          'team_invitations',
          CACHE_DURATION,
          email
        )
        if (cached) {
          return cached
        }
      }

      // Fetch from API
      const data = await settingsApiClient.get(`/invitations/user/${encodeURIComponent(email)}`)

      // Cache the result
      setCachedData('team_invitations', data, email)

      return data
    } catch (error: any) {
      if (error?.status === 404) {
        return { user: null, invitations: [] }
      }
      console.error('Error fetching user invitations:', error)
      throw error
    }
  },

  /**
   * Get all invitations for a company
   * @param company - The company name
   * @param forceRefresh - Force refresh from server, bypassing cache
   * @returns Array of invitation objects
   */
  async getCompanyInvitations(company: string, forceRefresh = false): Promise<any[]> {
    try {
      // Check cache first if not forcing refresh
      if (!forceRefresh) {
        const cached = getCachedData<any[]>('company_invitations', CACHE_DURATION, company)
        if (cached) {
          return cached
        }
      }

      // Fetch from API
      const data = await settingsApiClient.get(
        `/invitations/company/${encodeURIComponent(company)}`
      )
      const invitations = data.invitations || []

      // Cache the result
      setCachedData('company_invitations', invitations, company)

      return invitations
    } catch (error) {
      console.error('Error fetching company invitations:', error)
      throw error
    }
  },

  /**
   * Create a new invitation
   * @param invitationData - The invitation data
   * @returns Created invitation object
   */
  async createInvitation(invitationData: InvitationData): Promise<any> {
    try {
      return await settingsApiClient.post('/invitations', invitationData)
    } catch (error: any) {
      if (error?.status === 409) {
        throw new Error(error?.data?.detail || 'User already exists')
      }
      console.error('Error creating invitation:', error)
      throw error
    }
  },

  /**
   * Update an existing invitation
   * @param email - The email address of the invitation to update
   * @param updateData - The fields to update
   * @returns Updated invitation object
   */
  async updateInvitation(email: string, updateData: Partial<InvitationData>): Promise<any> {
    try {
      return await settingsApiClient.put(`/invitations/${encodeURIComponent(email)}`, updateData)
    } catch (error) {
      console.error('Error updating invitation:', error)
      throw error
    }
  },

  /**
   * Delete an invitation
   * @param email - The email address of the invitation to delete
   * @returns Deletion confirmation
   */
  async deleteInvitation(email: string): Promise<any> {
    try {
      return await settingsApiClient.delete(`/invitations/${encodeURIComponent(email)}`)
    } catch (error) {
      console.error('Error deleting invitation:', error)
      throw error
    }
  },

  /**
   * Check if a user exists in the database
   * @param email - The email address to check
   * @returns True if user exists, false otherwise
   */
  async checkUserExists(email: string): Promise<boolean> {
    try {
      const data = await settingsApiClient.get(`/invitations/check/${encodeURIComponent(email)}`)
      return data.exists || false
    } catch (error: any) {
      if (error?.status === 404) {
        return false
      }
      console.error('Error checking user existence:', error)
      return false
    }
  },

  /**
   * Update onboarding progress for a user
   * @param email - The user's email
   * @param data - Onboarding update data
   * @returns Updated onboarding state
   */
  async updateOnboarding(
    email: string,
    data: {
      onboardingStatus?: OnboardingStatus
      onboardingStep?: number
      onboardingProgress?: OnboardingProgress
    }
  ): Promise<any> {
    try {
      const result = await settingsApiClient.patch(
        `/invitations/${encodeURIComponent(email)}/onboarding`,
        data
      )
      // Invalidate cached user data so the guard re-fetches
      clearCachedData('team_invitations', email)
      return result
    } catch (error) {
      console.error('Error updating onboarding:', error)
      throw error
    }
  },
}
