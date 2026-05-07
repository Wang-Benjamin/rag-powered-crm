/**
 * Settings Service - User Settings and Team Management API calls
 * Handles user profiles, team invitations, templates, analytics, and onboarding
 */

import { settingsApiClient } from './client'
import type {
  UserProfile,
  TeamInvitation,
  DatabaseTable,
  DatabaseStatus,
  TableContent,
  AIPreferences,
} from '@/types/settings'
import type { EmailTemplate } from '@/types/email'

// ===== SETTINGS SERVICE CLASS =====

class SettingsService {
  // ===== USER PROFILES =====

  /**
   * Get or create user profile
   */
  async getUserProfile(email: string): Promise<UserProfile | null> {
    try {
      const response = await settingsApiClient.get<{
        user: UserProfile
        invitations: TeamInvitation[]
      }>(`/invitations/user/${encodeURIComponent(email)}`)

      if (response.user) {
        return {
          ...response.user,
          lastLogin: response.user.lastLogin ? new Date(response.user.lastLogin) : undefined,
          createdAt: response.user.createdAt ? new Date(response.user.createdAt) : undefined,
          updatedAt: response.user.updatedAt ? new Date(response.user.updatedAt) : undefined,
        }
      }

      return null
    } catch (error) {
      console.error('Error fetching user profile:', error)
      return null
    }
  }

  // ===== EMAIL TEMPLATES =====
  // Note: Team invitation methods are in invitationsApi.ts to avoid duplication

  /**
   * Get email templates for a user
   */
  async getEmailTemplates(
    channel: string = 'email',
    isActive: boolean = true
  ): Promise<EmailTemplate[]> {
    try {
      const templates = await settingsApiClient.get<EmailTemplate[]>('/templates', {
        channel,
        isActive: isActive.toString(),
      })

      return templates
    } catch (error) {
      console.error('Error fetching email templates:', error)
      return []
    }
  }

  /**
   * Get a specific email template by ID
   */
  async getEmailTemplate(templateId: string): Promise<EmailTemplate | null> {
    try {
      const template = await settingsApiClient.get<EmailTemplate>(`/templates/${templateId}`)

      return template
    } catch (error) {
      console.error('Error fetching email template:', error)
      return null
    }
  }

  /**
   * Create a new email template
   */
  async createEmailTemplate(
    templateData: Omit<EmailTemplate, 'id' | 'createdAt' | 'updatedAt'>
  ): Promise<EmailTemplate> {
    try {
      const template = await settingsApiClient.post<EmailTemplate>('/templates', templateData)

      return template
    } catch (error) {
      console.error('Error creating email template:', error)
      throw error
    }
  }

  /**
   * Update an email template
   */
  async updateEmailTemplate(
    templateId: string,
    templateData: Partial<EmailTemplate>
  ): Promise<EmailTemplate> {
    try {
      const template = await settingsApiClient.put<EmailTemplate>(
        `/templates/${templateId}`,
        templateData
      )

      return template
    } catch (error) {
      console.error('Error updating email template:', error)
      throw error
    }
  }

  /**
   * Delete an email template
   */
  async deleteEmailTemplate(templateId: string): Promise<void> {
    try {
      await settingsApiClient.delete(`/templates/${templateId}`)
    } catch (error) {
      console.error('Error deleting email template:', error)
      throw error
    }
  }

  // ===== ANALYTICS =====

  /**
   * Log a user activity event via /activity/log endpoint
   */
  async trackEvent(
    userEmail: string,
    actionType: string,
    actionName: string,
    data: Record<string, any> = {}
  ): Promise<{ success: boolean; message: string } | null> {
    try {
      const sessionId = this.getOrCreateSessionId()

      const response = await settingsApiClient.post<{ success: boolean; message: string }>(
        '/activity/log',
        {
          userEmail,
          actionType,
          actionName,
          sessionId,
          actionData: data,
        }
      )

      return response
    } catch (error) {
      console.error('Error tracking event:', error)
      return null
    }
  }

  /**
   * Get user activity summary via /activity/summary endpoint
   */
  async getActivitySummary(days: number = 7): Promise<{
    byType: Array<{
      actionType: string
      count: number
      avgDurationMs: number | null
      uniqueUsers: number
    }>
    topPages: Array<{ pageUrl: string; views: number; avgDurationMs: number | null }>
  }> {
    try {
      const summary = await settingsApiClient.get<{
        byType: Array<{
          actionType: string
          count: number
          avgDurationMs: number | null
          uniqueUsers: number
        }>
        topPages: Array<{ pageUrl: string; views: number; avgDurationMs: number | null }>
      }>('/activity/summary', { days: days.toString() })

      return summary
    } catch (error) {
      console.error('Error getting activity summary:', error)
      return { byType: [], topPages: [] }
    }
  }

  // ===== ONBOARDING =====

  // ===== AUTHENTICATION =====

  /**
   * Login with email and password
   */
  async login(
    email: string,
    password: string
  ): Promise<{
    success: boolean
    token?: string
    user?: UserProfile
    message?: string
  }> {
    try {
      const response = await settingsApiClient.post<{
        success: boolean
        token?: string
        user?: UserProfile
        message?: string
      }>('/login', {
        email,
        password,
      })

      if (response.user) {
        response.user = {
          ...response.user,
          lastLogin: response.user.lastLogin ? new Date(response.user.lastLogin) : undefined,
          createdAt: response.user.createdAt ? new Date(response.user.createdAt) : undefined,
          updatedAt: response.user.updatedAt ? new Date(response.user.updatedAt) : undefined,
        }
      }

      return response
    } catch (error) {
      console.error('Error during login:', error)
      throw error
    }
  }

  /**
   * Register new user account
   */
  async register(userData: {
    email: string
    password: string
    name?: string
    company?: string
  }): Promise<{
    success: boolean
    user?: UserProfile
    message?: string
  }> {
    try {
      const response = await settingsApiClient.post<{
        success: boolean
        user?: UserProfile
        message?: string
      }>('/register', userData)

      if (response.user) {
        response.user = {
          ...response.user,
          lastLogin: response.user.lastLogin ? new Date(response.user.lastLogin) : undefined,
          createdAt: response.user.createdAt ? new Date(response.user.createdAt) : undefined,
          updatedAt: response.user.updatedAt ? new Date(response.user.updatedAt) : undefined,
        }
      }

      return response
    } catch (error) {
      console.error('Error during registration:', error)
      throw error
    }
  }

  // ===== PRIVATE UTILITY METHODS =====

  private sessionId: string | null = null

  /**
   * Get or create session ID for analytics tracking
   */
  private getOrCreateSessionId(): string {
    if (!this.sessionId) {
      this.sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    }
    return this.sessionId
  }

  // ===== AI PREFERENCES =====

  /**
   * Save AI preferences from questionnaire
   */
  async saveAIPreferences(preferences: {
    email: string
    tone: AIPreferences['tone']
    guardrails: AIPreferences['guardrails']
    audience: AIPreferences['audience']
    additionalContext: AIPreferences['additionalContext']
  }): Promise<{
    success: boolean
    message?: string
    preferences?: AIPreferences
  }> {
    try {
      const response = await settingsApiClient.post<{
        success: boolean
        message?: string
        preferences?: AIPreferences
      }>('/ai-preferences/save', preferences)

      return response
    } catch (error) {
      console.error('Error saving AI preferences:', error)
      throw error
    }
  }

  /**
   * Get AI preferences for a user
   */
  async getAIPreferences(email: string): Promise<{
    success: boolean
    message?: string
    preferences?: AIPreferences
  }> {
    try {
      const response = await settingsApiClient.get<{
        success: boolean
        message?: string
        preferences?: AIPreferences
      }>(`/ai-preferences/get/${encodeURIComponent(email)}`)

      return response
    } catch (error) {
      console.error('Error fetching AI preferences:', error)
      throw error
    }
  }

  /**
   * Delete AI preferences for a user
   */
  async deleteAIPreferences(email: string): Promise<{
    success: boolean
    message?: string
  }> {
    try {
      const response = await settingsApiClient.delete<{
        success: boolean
        message?: string
      }>(`/ai-preferences/delete/${encodeURIComponent(email)}`)

      return response
    } catch (error) {
      console.error('Error deleting AI preferences:', error)
      throw error
    }
  }

  // ===== LOCALE PREFERENCES =====

  /**
   * Get user locale preference
   */
  async getLocalePreference(): Promise<{ preferredLocale: string }> {
    try {
      return await settingsApiClient.get('/profile/locale')
    } catch (error) {
      console.error('Error fetching locale preference:', error)
      return { preferredLocale: 'en' }
    }
  }

  /**
   * Update user locale preference
   */
  async updateLocalePreference(locale: string): Promise<{ preferredLocale: string }> {
    return await settingsApiClient.put('/profile/locale', { preferredLocale: locale })
  }

  // ===== HEALTH CHECK =====

  /**
   * Get settings service health status
   */
  async getHealth(): Promise<{ status: string; timestamp: string }> {
    try {
      return await settingsApiClient.get('/health')
    } catch (error) {
      console.error('Error checking settings service health:', error)
      throw error
    }
  }
}

// Create singleton instance
export const settingsService = new SettingsService()

