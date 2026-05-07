/**
 * CRM Service - Customer Relationship Management API calls
 * Handles all CRM-related functionality including customers, communications, and analytics
 */

import { crmApiClient } from './client'

// Import types from centralized type definitions
import type {
  Customer,
  Deal,
  CommunicationSuggestion,
  CommunicationLog,
  CustomerMetrics,
  CommunicationMetrics,
  CustomerFilters,
} from '@/types/crm'

import type { EmailThreadSummary, ThreadEmail, ReplyContext } from '@/types/email'

// ===== LOCAL INTERFACES (not in types/crm/) =====

export interface EmailGenerationRequest {
  customerId: number
  customPrompt?: string
  tone?: string
  includePersonalization?: boolean
}

export interface EmailGenerationResponse {
  subject: string
  body: string
  tone: string
  keyPoints: string[]
  personalizationNotes: string
  confidence: number
}

// ===== CRM SERVICE CLASS =====

class CrmService {
  // ===== CUSTOMER MANAGEMENT =====

  /**
   * Get customers with filtering and pagination
   */
  async getCustomers(
    page: number = 1,
    perPage: number = 20,
    filters: CustomerFilters = {}
  ): Promise<{
    customers: Customer[]
    total: number
    page: number
    perPage: number
    hasMore: boolean
  }> {
    try {
      const params: Record<string, any> = {
        page: page.toString(),
        perPage: perPage.toString(),
        ...filters,
      }

      const response = await crmApiClient.get<{
        customers: Customer[]
        total: number
        page: number
        perPage: number
        hasMore?: boolean
      }>('/customers', params)

      return {
        customers: response.customers,
        total: response.total,
        page: response.page,
        perPage: response.perPage,
        hasMore: response.hasMore ?? response.customers.length === perPage,
      }
    } catch (error) {
      console.error('Error fetching customers:', error)
      throw error
    }
  }

  /**
   * Get a single customer by ID
   */
  async getCustomer(customerId: number): Promise<Customer | null> {
    try {
      return await crmApiClient.get<Customer>(`/customers/${customerId}`)
    } catch (error) {
      console.error('Error fetching customer:', error)
      return null
    }
  }

  /**
   * Get a single deal by ID
   */
  async getDeal(dealId: number): Promise<Deal | null> {
    try {
      return await crmApiClient.get<Deal>(`/deals/${dealId}`)
    } catch (error) {
      console.error('Error fetching deal:', error)
      return null
    }
  }

  /**
   * Create a new customer
   */
  async createCustomer(
    customerData: Omit<Customer, 'id' | 'createdAt' | 'updatedAt'>
  ): Promise<Customer> {
    try {
      return await crmApiClient.post<Customer>('/customers', customerData)
    } catch (error) {
      console.error('Error creating customer:', error)
      throw error
    }
  }

  /**
   * Update an existing customer
   */
  async updateCustomer(customerId: number, customerData: Partial<Customer>): Promise<Customer> {
    try {
      return await crmApiClient.put<Customer>(`/customers/${customerId}`, customerData)
    } catch (error) {
      console.error('Error updating customer:', error)
      throw error
    }
  }

  /**
   * Delete a customer
   */
  async deleteCustomer(customerId: number): Promise<void> {
    try {
      await crmApiClient.delete(`/customers/${customerId}`)
    } catch (error) {
      console.error('Error deleting customer:', error)
      throw error
    }
  }

  /**
   * Search customers by name, email, or company
   */
  async searchCustomers(query: string, limit: number = 10): Promise<Customer[]> {
    try {
      const response = await crmApiClient.get<{ customers: Customer[] }>('/customers/search', {
        q: query,
        limit: limit.toString(),
      })

      return response.customers
    } catch (error) {
      console.error('Error searching customers:', error)
      throw error
    }
  }

  // ===== COMMUNICATION SUGGESTIONS =====

  /**
   * Get communication suggestions for customers
   */
  async getCommunicationSuggestions(
    page: number = 1,
    perPage: number = 20,
    priority?: string
  ): Promise<{
    suggestions: CommunicationSuggestion[]
    total: number
  }> {
    try {
      const params: Record<string, string> = {
        page: page.toString(),
        perPage: perPage.toString(),
      }

      if (priority) {
        params.priority = priority
      }

      const response = await crmApiClient.get<{
        suggestions: CommunicationSuggestion[]
        total: number
      }>('/communication/suggestions', params)

      return {
        suggestions: response.suggestions.map((suggestion) => ({
          ...suggestion,
          lastContact: suggestion.lastContact ? new Date(suggestion.lastContact) : undefined,
          scheduledFor: suggestion.scheduledFor ? new Date(suggestion.scheduledFor) : undefined,
          createdAt: suggestion.createdAt ? new Date(suggestion.createdAt) : undefined,
        })),
        total: response.total,
      }
    } catch (error) {
      console.error('Error fetching communication suggestions:', error)
      throw error
    }
  }

  /**
   * Generate new communication suggestions using AI
   */
  async generateCommunicationSuggestions(forceRefresh: boolean = false): Promise<{
    generated: number
    suggestions: CommunicationSuggestion[]
  }> {
    try {
      const response = await crmApiClient.post<{
        generated: number
        suggestions: CommunicationSuggestion[]
      }>('/communication/suggestions/generate', {
        forceRefresh,
      })

      return {
        generated: response.generated,
        suggestions: response.suggestions.map((suggestion) => ({
          ...suggestion,
          lastContact: suggestion.lastContact ? new Date(suggestion.lastContact) : undefined,
          scheduledFor: suggestion.scheduledFor ? new Date(suggestion.scheduledFor) : undefined,
          createdAt: suggestion.createdAt ? new Date(suggestion.createdAt) : undefined,
        })),
      }
    } catch (error) {
      console.error('Error generating communication suggestions:', error)
      throw error
    }
  }

  /**
   * Update communication suggestion status
   */
  async updateCommunicationSuggestion(
    suggestionId: number,
    status: 'pending' | 'completed' | 'dismissed'
  ): Promise<CommunicationSuggestion> {
    try {
      const suggestion = await crmApiClient.put<CommunicationSuggestion>(
        `/communication/suggestions/${suggestionId}`,
        { status }
      )

      return {
        ...suggestion,
        lastContact: suggestion.lastContact ? new Date(suggestion.lastContact) : undefined,
        scheduledFor: suggestion.scheduledFor ? new Date(suggestion.scheduledFor) : undefined,
        createdAt: suggestion.createdAt ? new Date(suggestion.createdAt) : undefined,
      }
    } catch (error) {
      console.error('Error updating communication suggestion:', error)
      throw error
    }
  }

  // ===== COMMUNICATION LOGS =====

  /**
   * Get communication logs for a customer
   */
  async getCommunicationLogs(
    customerId: number,
    page: number = 1,
    perPage: number = 20
  ): Promise<{
    logs: CommunicationLog[]
    total: number
  }> {
    try {
      const response = await crmApiClient.get<{
        logs: CommunicationLog[]
        total: number
      }>(`/customers/${customerId}/communications`, {
        page: page.toString(),
        perPage: perPage.toString(),
      })

      return {
        logs: response.logs.map((log) => ({
          ...log,
          timestamp: new Date(log.timestamp),
        })),
        total: response.total,
      }
    } catch (error) {
      console.error('Error fetching communication logs:', error)
      throw error
    }
  }

  /**
   * Log a new communication
   */
  async logCommunication(
    communicationData: Omit<CommunicationLog, 'id' | 'timestamp'>
  ): Promise<CommunicationLog> {
    try {
      const log = await crmApiClient.post<CommunicationLog>('/communications', communicationData)

      return {
        ...log,
        timestamp: new Date(log.timestamp),
      }
    } catch (error) {
      console.error('Error logging communication:', error)
      throw error
    }
  }

  // ===== EMAIL GENERATION =====

  /**
   * Generate AI-powered email for a customer
   */
  async generateEmail(request: EmailGenerationRequest): Promise<EmailGenerationResponse> {
    try {
      const response = await crmApiClient.post<EmailGenerationResponse>(
        `/customers/${request.customerId}/generate-email`,
        {
          customPrompt: request.customPrompt,
          tone: request.tone,
          includePersonalization: request.includePersonalization,
        }
      )

      return response
    } catch (error) {
      console.error('Error generating email:', error)
      throw error
    }
  }

  /**
   * Send email to customer
   */
  async sendEmail(
    customerId: number,
    subject: string,
    body: string,
    metadata?: Record<string, any>
  ): Promise<{ success: boolean; messageId?: string; error?: string }> {
    try {
      const response = await crmApiClient.post<{
        success: boolean
        messageId?: string
        error?: string
      }>(`/customers/${customerId}/send-email`, {
        subject,
        body,
        metadata,
      })

      // Log the communication if successful
      if (response.success) {
        await this.logCommunication({
          customerId,
          type: 'email',
          subject,
          content: body,
          direction: 'outbound',
          status: 'sent',
          metadata: {
            messageId: response.messageId,
            ...metadata,
          },
        })
      }

      return response
    } catch (error) {
      console.error('Error sending email:', error)
      throw error
    }
  }

  // ===== ANALYTICS & METRICS =====

  /**
   * Get customer metrics and analytics
   */
  async getCustomerMetrics(dateRange?: { from: Date; to: Date }): Promise<CustomerMetrics> {
    try {
      const params: Record<string, string> = {}

      if (dateRange) {
        params.from = dateRange.from.toISOString()
        params.to = dateRange.to.toISOString()
      }

      return await crmApiClient.get<CustomerMetrics>('/metrics/customers', params)
    } catch (error) {
      console.error('Error fetching customer metrics:', error)
      throw error
    }
  }

  /**
   * Get communication metrics and analytics
   */
  async getCommunicationMetrics(dateRange?: {
    from: Date
    to: Date
  }): Promise<CommunicationMetrics> {
    try {
      const params: Record<string, string> = {}

      if (dateRange) {
        params.from = dateRange.from.toISOString()
        params.to = dateRange.to.toISOString()
      }

      return await crmApiClient.get<CommunicationMetrics>('/metrics/communications', params)
    } catch (error) {
      console.error('Error fetching communication metrics:', error)
      throw error
    }
  }

  /**
   * Get customer revenue analytics
   */
  async getRevenueAnalytics(dateRange?: { from: Date; to: Date }): Promise<{
    totalRevenue: number
    monthlyRevenue: { month: string; revenue: number }[]
    topCustomers: { name: string; revenue: number }[]
  }> {
    try {
      const params: Record<string, string> = {}

      if (dateRange) {
        params.from = dateRange.from.toISOString()
        params.to = dateRange.to.toISOString()
      }

      return await crmApiClient.get('/analytics/revenue', params)
    } catch (error) {
      console.error('Error fetching revenue analytics:', error)
      throw error
    }
  }

  // ===== IMPORT/EXPORT =====

  /**
   * Import customers from CSV file
   */
  async importCustomers(
    file: File,
    mappings: Record<string, string>
  ): Promise<{
    imported: number
    skipped: number
    errors: string[]
  }> {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('mappings', JSON.stringify(mappings))

      return await crmApiClient.upload('/customers/import', formData)
    } catch (error) {
      console.error('Error importing customers:', error)
      throw error
    }
  }

  /**
   * Export customers to CSV
   */
  async exportCustomers(filters: CustomerFilters = {}): Promise<string> {
    try {
      const params: Record<string, any> = {
        format: 'csv',
        ...filters,
      }

      const response = await crmApiClient.get('/customers/export', params)
      return response
    } catch (error) {
      console.error('Error exporting customers:', error)
      throw error
    }
  }

  // ===== EMAIL THREADS =====

  /**
   * Get all email threads for a customer
   */
  async getCustomerThreads(
    customerId: number,
    limit: number = 50
  ): Promise<{
    threads: EmailThreadSummary[]
    total: number
  }> {
    try {
      const response = await crmApiClient.get<{
        customerId: number
        threads: EmailThreadSummary[]
        total: number
      }>(`/customers/${customerId}/threads`, { limit: limit.toString() })

      return {
        threads: response.threads || [],
        total: response.total || 0,
      }
    } catch (error) {
      console.error('Error fetching customer threads:', error)
      throw error
    }
  }

  /**
   * Get emails in a specific thread
   */
  async getCustomerThreadDetail(
    customerId: number,
    threadId: string,
    limit: number = 50
  ): Promise<{
    threadId: string
    emails: ThreadEmail[]
    total: number
  }> {
    try {
      const response = await crmApiClient.get<{
        customerId: number
        threadId: string
        emails: ThreadEmail[]
        total: number
      }>(`/customers/${customerId}/threads/${encodeURIComponent(threadId)}`, {
        limit: limit.toString(),
      })

      return {
        threadId: response.threadId,
        emails: response.emails || [],
        total: response.total || 0,
      }
    } catch (error) {
      console.error('Error fetching thread detail:', error)
      throw error
    }
  }

  /**
   * Send email with optional reply threading
   */
  async sendEmailWithReply(
    customerId: number,
    toEmail: string,
    subject: string,
    body: string,
    replyContext?: ReplyContext | null,
    dealId?: string | null
  ): Promise<{ success: boolean; sentTo?: string; error?: string }> {
    try {
      const authProvider =
        typeof window !== 'undefined' ? localStorage.getItem('auth_provider') : null
      const accessToken =
        authProvider === 'google'
          ? typeof window !== 'undefined'
            ? localStorage.getItem('google_access_token')
            : null
          : null

      const emailData: Record<string, any> = {
        toEmail,
        subject,
        body,
        customerId,
        provider:
          authProvider === 'google' ? 'gmail' : authProvider === 'microsoft' ? 'outlook' : 'sendgrid',
        accessToken,
      }

      if (dealId) {
        emailData.dealId = dealId
      }

      if (replyContext) {
        emailData.replyToThreadId = replyContext.threadId
        emailData.replyToRfcMessageId = replyContext.rfcMessageId
      }

      const response = await crmApiClient.post<{
        status: string
        sentTo?: string
        message?: string
      }>('/send-email', emailData)

      return {
        success: response.status === 'success',
        sentTo: response.sentTo,
        error: response.status !== 'success' ? response.message : undefined,
      }
    } catch (error) {
      console.error('Error sending email:', error)
      throw error
    }
  }

  // ===== INITIAL OUTREACH (Buyers page → CRM) =====

  /**
   * Generate initial outreach email for a single BoL lead
   */
  async generateInitialOutreach(data: {
    leadId: string
    importContext?: Record<string, any>
    supplierContext?: Record<string, any>
    offer?: string
    ask?: string
    detail?: string
    customPrompt?: string
    templateId?: string
    strictnessLevel?: number
    generationMode?: string
    products?: Array<{ name: string; fobPrice?: string; landedPrice?: string }>
    fobPrice?: string
    certifications?: string[]
    moq?: string
    leadTime?: string
    sampleStatus?: string
  }): Promise<any> {
    try {
      return await crmApiClient.post('/initial-outreach/generate', data)
    } catch (error) {
      console.error('Error generating initial outreach:', error)
      throw error
    }
  }

  /**
   * Send initial outreach email for a single BoL lead
   */
  async sendInitialOutreach(data: {
    leadId: string
    subject: string
    body: string
    toEmail: string
    provider?: string
  }): Promise<any> {
    try {
      return await crmApiClient.post('/initial-outreach/send', data)
    } catch (error) {
      console.error('Error sending initial outreach:', error)
      throw error
    }
  }

  /**
   * Generate initial outreach emails for multiple BoL leads (mass)
   */
  async generateInitialOutreachMass(data: {
    leadIds: string[]
    importContexts?: Record<string, Record<string, any>>
    supplierContexts?: Record<string, Record<string, any>>
    offer?: string
    ask?: string
    detail?: string
    customPrompt?: string
    templateId?: string
    strictnessLevel?: number
    products?: Array<{ name: string; fobPrice?: string }>
    fobPrice?: string
    certifications?: string[]
    moq?: string
    leadTime?: string
    sampleStatus?: string
  }): Promise<any> {
    try {
      return await crmApiClient.post('/initial-outreach-mass/generate', data, { timeout: 120000 })
    } catch (error) {
      console.error('Error generating mass initial outreach:', error)
      throw error
    }
  }

  /**
   * Send initial outreach emails for multiple BoL leads (mass)
   */
  async sendInitialOutreachMass(data: {
    emails: Array<{ leadId: string; subject: string; body: string; toEmail: string }>
    modifiedEmails?: Array<{ leadId: string; subject: string; body: string; toEmail: string }>
    provider?: string
    campaignName?: string
    offer?: string
    ask?: string
    detail?: string
    // Trade fields persisted as trade_context on the campaign row
    products?: Array<{ name: string; fobPrice?: string; landedPrice?: string }>
    certifications?: string[]
    moq?: string
    leadTime?: string
    sampleStatus?: string
  }): Promise<any> {
    try {
      return await crmApiClient.post('/initial-outreach-mass/send', data)
    } catch (error) {
      console.error('Error sending mass initial outreach:', error)
      throw error
    }
  }

  // ===== CAMPAIGNS =====

  /**
   * Get all campaigns
   */
  async getCampaigns(): Promise<any> {
    try {
      return await crmApiClient.get('/campaigns')
    } catch (error) {
      console.error('Error fetching campaigns:', error)
      throw error
    }
  }

  /**
   * Get campaign detail by ID
   */
  async getCampaignDetail(campaignId: string): Promise<any> {
    try {
      return await crmApiClient.get(`/campaigns/${campaignId}`)
    } catch (error) {
      console.error('Error fetching campaign detail:', error)
      throw error
    }
  }

  /**
   * Get last-7-days outreach + reply counts for the current employee.
   */
  async getOutreachWeekly(): Promise<{ outreachWeek: number; repliesWeek: number }> {
    try {
      return await crmApiClient.get('/outreach/weekly')
    } catch (error) {
      console.error('Error fetching weekly outreach metrics:', error)
      return { outreachWeek: 0, repliesWeek: 0 }
    }
  }

  // ===== HEALTH CHECK =====

  /**
   * Get CRM service health status
   */
  async getHealth(): Promise<{ status: string; timestamp: string }> {
    try {
      return await crmApiClient.get('/health')
    } catch (error) {
      console.error('Error checking CRM service health:', error)
      throw error
    }
  }
}

// Create singleton instance
export const crmService = new CrmService()

