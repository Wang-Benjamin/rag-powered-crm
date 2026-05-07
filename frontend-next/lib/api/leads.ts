// Lead Generation API Service
// Uses leadsApiClient which auto-converts camelCase <-> snake_case

import { leadsApiClient, settingsApiClient } from './client'

interface LeadData {
  [key: string]: any
}

interface GetLeadsOptions {
  page?: number
  perPage?: number
  status?: string | null
  search?: string | null
  industry?: string | null
  location?: string | null
  includeRecent?: boolean
}

interface FilterParams {
  search?: string
  searchColumns?: string[]
  status?: string
  columnFilters?: Record<string, any>
  sortBy?: string
  sortOrder?: string
}

interface EnrichLeadsParams {
  companyIds?: string[]
  companies?: any[]
  jobTitles?: string[] | null
  department?: string | null
  seniorityLevel?: string | null
}

interface CompetitorExposureItem {
  supplierName: string
  supplierSlug: string
  threatLevel: string // HIGH, GROWING, DECLINING, MODERATE, LOW
  threatScore: number
  trendYoy: number | null
  matchingShipments: number
  isTracked: boolean
  buyerTeu: number
  buyerSharePct: number
}

interface PersonnelData {
  [key: string]: any
}

interface EmailOptions {
  limit?: number
  daysBack?: number
  direction?: string
}

class LeadsApiService {
  // All API calls now use leadsApiClient which handles auth automatically

  // Lead management endpoints
  async getLeads(page = 1, perPage = 50, filters: Record<string, any> = {}) {
    try {
      // Use camelCase - ApiClient auto-converts to snake_case
      return await leadsApiClient.get('/', {
        page: page.toString(),
        perPage: perPage.toString(),
        ...filters,
      })
    } catch (error) {
      console.error('Error getting leads:', error)
      throw error
    }
  }

  // Get a single lead by ID
  async getLeadById(leadId: string) {
    try {
      return await leadsApiClient.get(`/lead/${leadId}`)
    } catch (error: any) {
      if (error?.status === 404) {
        return null // Lead not found
      }
      console.error('Error getting lead by ID:', error)
      throw error
    }
  }

  // Create a new lead
  async createLead(leadData: LeadData) {
    try {
      // ApiClient handles auth token automatically
      // Use empty string instead of '/' to avoid trailing slash issues
      return await leadsApiClient.post('', leadData)
    } catch (error) {
      console.error('Error creating lead:', error)
      throw error
    }
  }

  // Update lead (general update for any field)
  async updateLead(leadId: string, updateData: Partial<LeadData>) {
    try {
      // ApiClient handles auth and case conversion automatically
      return await leadsApiClient.put(`/lead/${leadId}`, updateData)
    } catch (error) {
      console.error('Error updating lead:', error)
      throw error
    }
  }

  // Update lead status
  async updateLeadStatus(leadId: string, status: string) {
    try {
      // Use the general update endpoint with only status field
      return await this.updateLead(leadId, { status })
    } catch (error) {
      console.error('Error updating lead status:', error)
      throw error
    }
  }

  // Delete a single lead
  async deleteLead(leadId: string) {
    try {
      return await leadsApiClient.delete(`/lead/${leadId}`)
    } catch (error) {
      console.error('Error deleting lead:', error)
      throw error
    }
  }

  // Clear all leads
  async clearAllLeads() {
    try {
      return await leadsApiClient.delete('/')
    } catch (error) {
      console.error('Error clearing all leads:', error)
      throw error
    }
  }

  // Get lead statistics
  async getLeadStats() {
    try {
      return await leadsApiClient.get('/stats')
    } catch (error) {
      console.error('Error getting lead stats:', error)
      throw error
    }
  }

  // Get leads with personnel data
  async getLeadsWithPersonnel(options: GetLeadsOptions = {}) {
    try {
      const {
        page = 1,
        perPage = 50,
        status = null,
        search = null,
        industry = null,
        location = null,
        includeRecent = false,
      } = options

      // Build params object with camelCase - ApiClient auto-converts to snake_case
      const params: Record<string, string> = {
        page: page.toString(),
        perPage: perPage.toString(),
      }

      if (status) params.status = status
      if (search) params.search = search
      if (industry) params.industry = industry
      if (location) params.location = location
      if (includeRecent) params.includeRecent = 'true'

      return await leadsApiClient.get('/with-personnel', params)
    } catch (error) {
      console.error('Error getting leads with personnel:', error)
      throw error
    }
  }

  // Export leads to CSV (old method - kept for backward compatibility)
  async exportLeadsToCSV() {
    try {
      // Backend returns JSON with CSV content
      const data = await leadsApiClient.get('/data/export/leads', { format: 'csv' })
      const csvContent = data.content

      // Create filename with timestamp
      const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-')
      const filename = `leads_export_${timestamp}.csv`

      // Create blob from CSV content and trigger download
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)

      // Parse CSV to get row count for stats
      const rows = csvContent.split('\n').filter((row: string) => row.trim().length > 0)
      const totalRows = Math.max(0, rows.length - 1) // Exclude header row

      return {
        totalLeads: totalRows,
        totalRows: totalRows,
        personnelCount: data.personnelCount || 0,
        filename: filename,
      }
    } catch (error) {
      console.error('Error exporting leads to CSV:', error)
      throw error
    }
  }

  // Export filtered leads to CSV (new method with filter support)
  async exportLeadsCSV(filterParams: FilterParams = {}) {
    try {
      // Build query params with camelCase - ApiClient auto-converts to snake_case
      const params: Record<string, string> = {}

      if (filterParams.search) {
        params.search = filterParams.search
      }

      if (filterParams.searchColumns && Array.isArray(filterParams.searchColumns)) {
        params.searchColumns = filterParams.searchColumns.join(',')
      }

      if (filterParams.status) {
        params.status = filterParams.status
      }

      if (filterParams.columnFilters) {
        // Serialize column filters as JSON
        params.columnFilters = JSON.stringify(filterParams.columnFilters)
      }

      if (filterParams.sortBy) {
        params.sortBy = filterParams.sortBy
      }

      if (filterParams.sortOrder) {
        params.sortOrder = filterParams.sortOrder
      }

      // Backend returns CSV content as text
      return await leadsApiClient.get('/export', params)
    } catch (error) {
      console.error('Error exporting filtered leads to CSV:', error)
      throw error
    }
  }

  // Generate email for a lead using AI generation
  async generateEmail(
    leadId: string,
    customPrompt = '',
    templateId: string | null = null,
    factoryData?: Record<string, any>
  ) {
    try {
      const body: Record<string, any> = { customPrompt }
      if (templateId) body.templateId = templateId
      if (factoryData) Object.assign(body, factoryData)
      return await leadsApiClient.post('/generate-email', { leadId, ...body })
    } catch (error) {
      console.error('Error generating email:', error)
      throw error
    }
  }

  // Get lead email history
  async getLeadEmailHistory(leadId: string, limit = 20) {
    try {
      return await leadsApiClient.get(`/lead/${leadId}/email-history`, { limit: limit.toString() })
    } catch (error) {
      console.error('Error getting lead email history:', error)
      throw error
    }
  }

  // Get lead info for email generation
  async getLeadInfoForEmail(leadId: string) {
    try {
      return await leadsApiClient.get(`/lead/${leadId}/info`)
    } catch (error) {
      console.error('Error getting lead info for email:', error)
      throw error
    }
  }

  // Get BoL buyer intelligence for email compose screen
  async getBolIntelligence(leadId: string) {
    try {
      return await leadsApiClient.get(`/${leadId}/bol-intelligence`)
    } catch (error) {
      console.error('Error getting BoL intelligence:', error)
      return { intelligence: null, leadId }
    }
  }

  // Send email
  async sendEmail(toEmail: string, subject: string, body: string, leadId: string | null = null) {
    try {
      // Use camelCase - ApiClient auto-converts to snake_case
      const requestBody: any = {
        toEmail: toEmail,
        subject: subject,
        body: body,
      }

      if (leadId) {
        requestBody.leadId = leadId
      }

      // Set provider based on auth provider - tokens are now fetched from database by backend
      const authProvider = localStorage.getItem('auth_provider')
      if (authProvider === 'google') {
        requestBody.provider = 'gmail'
      } else if (authProvider === 'microsoft') {
        requestBody.provider = 'outlook'
      }

      return await leadsApiClient.post('/send-email', requestBody)
    } catch (error) {
      console.error('Error sending email:', error)
      throw error
    }
  }

  // Check for email replies and update lead status if positive
  // Get email configuration status
  async getEmailConfig() {
    try {
      return await leadsApiClient.get('/email-config')
    } catch (error) {
      console.error('Error getting email config:', error)
      throw error
    }
  }

  // Get email timeline for a lead (for timeline visualization)
  async getLeadEmailTimeline(leadId: string, options: EmailOptions = {}) {
    try {
      const {
        limit = 200, // Default to 200 to fetch all emails (backend max)
        daysBack = 365, // Default to 1 year to get full history
        direction = 'all',
      } = options

      // Use camelCase - ApiClient auto-converts to snake_case
      return await leadsApiClient.get(`/${leadId}/email-timeline`, {
        limit: limit.toString(),
        daysBack: daysBack.toString(),
        direction: direction,
      })
    } catch (error) {
      console.error('Error getting lead email timeline:', error)
      throw error
    }
  }

  // Get email statistics for a lead (for timeline header)
  async getLeadEmailStats(leadId: string) {
    try {
      return await leadsApiClient.get(`/${leadId}/email-stats`)
    } catch (error) {
      console.error('Error getting lead email stats:', error)
      throw error
    }
  }

  /**
   * Enrich selected leads with email contacts
   * Takes company IDs and returns leads with emails (no phone)
   * Note: This endpoint uses /workflow/enrich (proxy adds /api/leads/)
   */
  async enrichLeads(params: EnrichLeadsParams) {
    try {
      const {
        companyIds,
        companies, // Full company data for Google Maps -> Apollo hybrid lookup
        jobTitles,
        department,
        seniorityLevel,
      } = params

      // Use camelCase - ApiClient auto-converts to snake_case
      return await leadsApiClient.post('/workflow/enrich', {
        companyIds: companyIds,
        companies: companies || [], // Send company data for hybrid enrichment
        jobTitles: jobTitles || null,
        department: department || null,
        seniorityLevel: seniorityLevel || null,
      })
    } catch (error) {
      console.error('Error enriching leads:', error)
      throw error
    }
  }

  /**
   * Get enrichment history for the current user
   */
  async getEnrichmentHistory(limit = 20, offset = 0) {
    try {
      const data = await leadsApiClient.get('/enrichment-history', {
        limit: limit.toString(),
        offset: offset.toString(),
      })
      return {
        history: data.history || [],
        total: data.total || 0,
        hasMore: data.hasMore || false,
      }
    } catch (error) {
      console.error('Error fetching enrichment history:', error)
      throw error
    }
  }

  async deleteEnrichmentHistory(recordId: string) {
    try {
      return await leadsApiClient.delete(`/enrichment-history/${recordId}`)
    } catch (error: any) {
      // Handle 401 Unauthorized (token expired)
      if (error?.status === 401) {
        throw new Error('Session expired. Please refresh the page and log in again.')
      }
      console.error('Error deleting enrichment history:', error)
      throw error
    }
  }

  /**
   * Find leads by company name
   */
  async findLeadsByCompany(companyName: string) {
    try {
      // Use camelCase - ApiClient auto-converts to snake_case
      const data = await leadsApiClient.get('/', {
        company: companyName,
        pageSize: '10',
      })
      return data.data || []
    } catch (error) {
      console.error('Error finding leads by company:', error)
      throw error
    }
  }

  /**
   * Batch check which companies already exist in database
   */
  async batchCheckCompaniesExist(companyNames: string[]) {
    try {
      // Use camelCase - ApiClient auto-converts to snake_case
      return await leadsApiClient.post('/batch-check-exists', {
        companyNames: companyNames,
      })
    } catch (error) {
      console.error('Error batch checking companies:', error)
      throw error
    }
  }

  /**
   * Create personnel record
   */
  async createPersonnel(personnelData: PersonnelData) {
    try {
      return await leadsApiClient.post('/personnel', personnelData)
    } catch (error) {
      console.error('Error creating personnel:', error)
      throw error
    }
  }

  /**
   * Get monthly token usage for the current user
   *
   * Returns the number of leads created this month that have at least 1 personnel
   * with an email address. Each such lead counts as 1 token.
   */
  async getMonthlyTokenUsage() {
    try {
      return await leadsApiClient.get('/token-usage/monthly')
    } catch (error) {
      console.error('Error getting monthly token usage:', error)
      throw error
    }
  }

  // ===== MASS EMAIL METHODS =====

  /**
   * Send mass email to multiple leads
   * Supports template-based sending via templateId (templates created in User Settings)
   */
  async sendMassEmail(
    leadIds: string[],
    subjectTemplate: string,
    bodyTemplate: string,
    provider: string,
    templateId: string | null = null
  ) {
    try {
      // Use camelCase - ApiClient auto-converts to snake_case
      const payload: any = {
        leadIds: leadIds,
        provider: provider,
      }

      // Send templateId and edited content (if using saved template)
      // Use camelCase - ApiClient auto-converts to snake_case
      if (templateId) {
        payload.templateId = templateId
        // Also send edited subject/body to preserve user edits
        payload.subjectTemplate = subjectTemplate
        payload.bodyTemplate = bodyTemplate
      } else {
        // AI-generated mode: only subject/body
        payload.subjectTemplate = subjectTemplate
        payload.bodyTemplate = bodyTemplate
      }

      return await leadsApiClient.post('/send-mass-email', payload)
    } catch (error) {
      console.error('Error sending mass email:', error)
      throw error
    }
  }

  /**
   * Generate personalized mass emails for multiple leads using Batch API (max 25 leads)
   * AI decides the email approach automatically based on context.
   */
  async generatePersonalizedMassEmails(
    leadIds: string[],
    customPrompt: string,
    templateId: string | null = null,
    factoryData?: {
      products?: { name: string; fobPrice: string; landedPrice: string }[]
      certifications?: string[]
      moq?: string
      leadTime?: string
      sampleStatus?: string
    }
  ) {
    try {
      // Use camelCase - ApiClient auto-converts to snake_case
      const payload: Record<string, any> = {
        leadIds: leadIds,
        customPrompt: customPrompt || '',
        templateId: templateId,
      }
      // Factory data (camelCase -> auto-converted to snake_case by ApiClient)
      if (factoryData?.products?.length) payload.products = factoryData.products
      if (factoryData?.certifications?.length) payload.certifications = factoryData.certifications
      if (factoryData?.moq) payload.moq = factoryData.moq
      if (factoryData?.leadTime) payload.leadTime = factoryData.leadTime
      if (factoryData?.sampleStatus) payload.sampleStatus = factoryData.sampleStatus
      return await leadsApiClient.post('/generate-personalized-mass-emails', payload, {
        timeout: 120000,
      })
    } catch (error) {
      console.error('Error generating personalized mass emails:', error)
      throw error
    }
  }

  /**
   * Send personalized mass emails (no template rendering needed)
   */
  async sendPersonalizedMassEmails(
    emails: any[],
    provider: string,
    modifiedEmails: any[] = [],
    campaignContext?: {
      customPrompt?: string
      products?: { name: string; fobPrice: string; landedPrice: string }[]
      certifications?: string[]
      moq?: string
      leadTime?: string
      [key: string]: any
    }
  ) {
    try {
      // Use camelCase - ApiClient auto-converts to snake_case
      const payload: Record<string, any> = {
        emails: emails,
        provider: provider,
        modifiedEmails: modifiedEmails,
      }
      if (campaignContext?.customPrompt) payload.customPrompt = campaignContext.customPrompt
      // Factory data (persisted with campaign for analytics)
      if (campaignContext?.products?.length) payload.products = campaignContext.products
      if (campaignContext?.certifications?.length)
        payload.certifications = campaignContext.certifications
      if (campaignContext?.moq) payload.moq = campaignContext.moq
      if (campaignContext?.leadTime) payload.leadTime = campaignContext.leadTime
      return await leadsApiClient.post('/send-personalized-mass-emails', payload)
    } catch (error) {
      console.error('Error sending personalized mass emails:', error)
      throw error
    }
  }

  /**
   * Fetch email templates from User Settings service
   */
  async getEmailTemplates(channel = 'email', isActive = true, templateType?: string) {
    try {
      // Use camelCase - settingsApiClient auto-converts to snake_case
      const params: Record<string, string> = {
        channel,
        isActive: isActive.toString(),
      }
      if (templateType) {
        params.templateType = templateType
      }
      return await settingsApiClient.get('/templates', params)
    } catch (error) {
      console.error('Error fetching email templates:', error)
      throw error
    }
  }

  /**
   * Get a specific email template by ID
   */
  async getEmailTemplate(templateId: string) {
    try {
      return await settingsApiClient.get(`/templates/${templateId}`)
    } catch (error) {
      console.error('Error fetching email template:', error)
      throw error
    }
  }

  // ===== EMAIL THREAD METHODS =====

  /**
   * Get all email threads for a lead
   */
  async getLeadThreads(leadId: string, limit: number = 50) {
    try {
      return await leadsApiClient.get(`/${leadId}/threads`, { limit: limit.toString() })
    } catch (error) {
      console.error('Error fetching lead threads:', error)
      throw error
    }
  }

  /**
   * Get emails in a specific thread for a lead
   */
  async getLeadThreadDetail(leadId: string, threadId: string, limit: number = 50) {
    try {
      return await leadsApiClient.get(`/${leadId}/threads/${encodeURIComponent(threadId)}`, {
        limit: limit.toString(),
      })
    } catch (error) {
      console.error('Error fetching thread detail:', error)
      throw error
    }
  }

  /**
   * Send email with optional reply threading
   */
  async sendEmailWithReply(
    toEmail: string,
    subject: string,
    body: string,
    leadId: string,
    replyContext?: { threadId: string; rfcMessageId: string } | null
  ) {
    try {
      const requestBody: any = {
        toEmail,
        subject,
        body,
        leadId,
      }

      // Set provider based on auth provider
      const authProvider = localStorage.getItem('auth_provider')
      if (authProvider === 'google') {
        requestBody.provider = 'gmail'
      } else if (authProvider === 'microsoft') {
        requestBody.provider = 'outlook'
      }

      // Add reply context if provided
      if (replyContext) {
        requestBody.replyToThreadId = replyContext.threadId
        requestBody.replyToRfcMessageId = replyContext.rfcMessageId
      }

      return await leadsApiClient.post('/send-email', requestBody)
    } catch (error) {
      console.error('Error sending email with reply:', error)
      throw error
    }
  }

  // ===== SCHEDULED MASS EMAIL METHODS =====

  async scheduleMassEmail(data: Record<string, any>) {
    return await leadsApiClient.post('/schedule-mass-email', data)
  }

  async getScheduledMassEmails() {
    return await leadsApiClient.get('/scheduled-mass-emails')
  }

  async cancelScheduledMassEmail(scheduleId: number) {
    return await leadsApiClient.delete(`/scheduled-mass-emails/${scheduleId}`)
  }

  // === ImportYeti / Find Buyers ===

  async getSubscription() {
    return await leadsApiClient.get('/importyeti/subscription')
  }

  async csvKickoffOnboarding(): Promise<{
    status: 'complete' | 'already_complete' | 'already_running'
    buyersInCache?: number
    buyersEnriched?: number
    buyersWithContacts?: number
    buyersReady?: number
    competitorsEnriched?: number
    competitorsReady?: number
    pipelineCreated?: number
    message?: string
  }> {
    // CSV-bypass onboarding — skips PowerQuery + free-enrich, reads from
    // pre-populated 8007 cache. Blocking — allow up to 10 minutes.
    return await leadsApiClient.post(
      '/importyeti/onboarding/csv-kickoff',
      {},
      { timeout: 600_000, retries: 0 },
    )
  }

  async getHsCodes() {
    try {
      return await settingsApiClient.get('/hs-codes')
    } catch (error) {
      console.error('Error fetching HS codes:', error)
      return { hsCodes: [] }
    }
  }

  async getEnrichmentStatus(slugs: string[]): Promise<Record<string, { enrichmentStatus: string; quickScore: number | null; enrichedScore: number | null }>> {
    return await leadsApiClient.get(`/importyeti/enrichment-status`, { slugs: slugs.join(',') })
  }

  async addToPipeline(
    slugs: string[],
    searchParams: { hsCodes: string[]; products: string[]; maxResults: number },
  ) {
    return await leadsApiClient.post('/importyeti/add-to-pipeline', {
      slugs,
      hsCodes: searchParams.hsCodes,
      products: searchParams.products,
      maxResults: searchParams.maxResults,
    })
  }

  // === ImportYeti / Competitors ===

  async getCompetitors() {
    return await leadsApiClient.get('/importyeti/competitors')
  }

  async getCompetitorDetail(slug: string) {
    return await leadsApiClient.get(`/importyeti/competitor/${slug}`)
  }

  async trackCompetitor(slug: string, tracked: boolean) {
    return await leadsApiClient.post(`/importyeti/competitor/${slug}/track`, { isTracked: tracked })
  }

  async getLeadCompetitors(leadId: string): Promise<CompetitorExposureItem[]> {
    try {
      const data = await leadsApiClient.get(`/importyeti/buyer/${leadId}/competitors`)
      return data?.competitors ?? []
    } catch (error) {
      console.error('Error getting lead competitors:', error)
      throw error
    }
  }

  // Generate a two-pager report (buyers + contacts + AI outreach emails).
  // At least one of hsCode or productDescription must be provided.
  // Extended timeout: cold path now includes Perplexity filter + deep
  // enrichment + Apollo + LLM; HS 3924-like categories have been observed
  // taking ~140s, so 240s leaves comfortable headroom.
  async generateTwoPager(params: { hsCode?: string; productDescription?: string }) {
    return await leadsApiClient.post('/importyeti/two-pager', params, { timeout: 360000 })
  }

  // Generate two-pager reports for multiple HS codes in a single server-side call.
  // Up to 14 items; server runs 5 concurrently. Always resolves — per-item failures
  // are in result.error rather than throwing.
  async generateTwoPagerBatch(
    items: Array<{ hsCode: string }>,
  ): Promise<{
    results: Array<{
      hsCode: string
      data: Record<string, any> | null
      error: { hsCode: string; status: string; message: string; elapsedMs: number } | null
    }>
    total: number
    succeeded: number
    failed: number
    elapsedMs: number
  }> {
    return await leadsApiClient.post(
      '/importyeti/two-pager/batch',
      { items },
      { timeout: 600000 },
    )
  }
}

// Create singleton instance
const leadsApiService = new LeadsApiService()

export default leadsApiService
