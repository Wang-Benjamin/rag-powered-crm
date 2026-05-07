/**
 * Feedback API Client
 * Handles all feedback-related API calls for CRM
 */

import { ApiClient } from './client'
import type {
  FeedbackCategory,
  FeedbackCreate,
  FeedbackUpdate,
  FeedbackResponse,
} from '@/types/crm/feedback'

// Re-export types for backward compatibility
export type {
  FeedbackCategory,
  FeedbackHistoryEntry,
  FeedbackAISummary,
  FeedbackCreate,
  FeedbackUpdate,
  FeedbackResponse,
} from '@/types/crm/feedback'

const feedbackApiClient = new ApiClient({
  baseUrl: '/api/proxy/crm',
})

// ============================================================================
// API Methods
// ============================================================================

export const feedbackApi = {
  /**
   * Create new feedback
   */
  createFeedback: async (data: FeedbackCreate): Promise<FeedbackResponse> => {
    return feedbackApiClient.post('/feedback', data)
  },

  /**
   * Get all feedback for a customer or deal, optionally filtered by category
   * Admins see all feedback, users see only their own
   */
  getFeedback: async (
    customerId: number,
    dealId?: number,
    category?: FeedbackCategory
  ): Promise<FeedbackResponse[]> => {
    const params: Record<string, string> = {}
    if (dealId !== undefined) params.dealId = dealId.toString()
    if (category) params.category = category

    return feedbackApiClient.get(`/customers/${customerId}/feedback`, params)
  },

  /**
   * Get feedback for a specific customer/deal and category
   */
  getFeedbackByCategory: async (
    customerId: number,
    category: FeedbackCategory,
    dealId?: number
  ): Promise<FeedbackResponse[]> => {
    const params: Record<string, string> = { category }
    if (dealId !== undefined) params.dealId = dealId.toString()

    return feedbackApiClient.get(`/customers/${customerId}/feedback`, params)
  },

  /**
   * Get specific feedback by ID
   */
  getFeedbackById: async (feedbackId: number): Promise<FeedbackResponse> => {
    return feedbackApiClient.get(`/feedback/${feedbackId}`)
  },

  /**
   * Update existing feedback
   */
  updateFeedback: async (feedbackId: number, data: FeedbackUpdate): Promise<FeedbackResponse> => {
    return feedbackApiClient.put(`/feedback/${feedbackId}`, data)
  },

  /**
   * Delete feedback
   */
  deleteFeedback: async (feedbackId: number): Promise<{ success: boolean; message: string }> => {
    return feedbackApiClient.delete(`/feedback/${feedbackId}`)
  },
}
