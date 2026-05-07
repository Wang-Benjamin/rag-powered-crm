/**
 * Metrics Type Definitions
 * Includes CustomerMetrics, CommunicationMetrics, CommunicationSuggestion, and CommunicationLog
 */

export interface CustomerMetrics {
  totalCustomers: number
  activeCustomers: number
  prospectCustomers: number
  totalRevenue: number
  averageRevenue: number
  recentActivity: number
  conversionRate: number
  monthlyGrowth: number
}

export interface CommunicationMetrics {
  totalCommunications: number
  emailsSent: number
  callsMade: number
  meetingsScheduled: number
  responseRate: number
  averageResponseTime: number
  topPerformingTemplates: string[]
}

export interface CommunicationSuggestion {
  id?: number
  customerId: number
  customerName: string
  type: 'email' | 'call' | 'meeting' | 'linkedin'
  priority: 'low' | 'medium' | 'high'
  reason: string
  suggestion: string
  template?: string
  bestTime?: string
  estimatedResponseRate?: number
  lastContact?: Date | string
  daysSinceContact: number
  aiGenerated: boolean
  status?: 'pending' | 'completed' | 'dismissed'
  scheduledFor?: Date | string
  createdAt?: Date | string
}

export interface CommunicationLog {
  id?: number
  customerId: number
  type: 'email' | 'call' | 'meeting' | 'note'
  subject?: string
  content: string
  direction: 'inbound' | 'outbound'
  status: 'sent' | 'received' | 'scheduled' | 'failed'
  timestamp: Date | string
  metadata?: Record<string, any>
}
