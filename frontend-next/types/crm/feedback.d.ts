/**
 * Feedback Type Definitions
 * Types for CRM feedback functionality
 */

export type FeedbackCategory = 'churnRisk' | 'aiInsights' | 'stageProgression' | 'dealInsights'

export interface FeedbackHistoryEntry {
  text: string
  timestamp: string
  employeeId: number
}

export interface FeedbackAISummary {
  summary: string
  ratingTrend: 'improving' | 'declining' | 'stable'
  sentimentEvolution: 'positive' | 'negative' | 'mixed'
  keyThemes: string[]
  actionableInsights: string[]
  generatedAt: string
  entriesAnalyzed: number
  fallback?: boolean
}

export interface FeedbackCreate {
  customerId: number
  dealId?: number
  feedbackCategory: FeedbackCategory
  rating: number // 1-5
  feedbackText?: string
}

export interface FeedbackUpdate {
  rating?: number // 1-5
  feedbackText?: string
}

export interface FeedbackResponse {
  feedbackId: number
  customerId: number
  dealId?: number
  feedbackCategory: FeedbackCategory
  employeeId: number
  rating: number
  feedbackHistory: FeedbackHistoryEntry[]
  aiSummary?: FeedbackAISummary
  createdAt: string
  updatedAt: string
  employeeName?: string
  employeeEmail?: string
}
