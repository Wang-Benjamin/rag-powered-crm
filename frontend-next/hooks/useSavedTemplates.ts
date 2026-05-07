import { useState, useEffect, useCallback, useMemo } from 'react'
import { templateApi } from '@/lib/api/emailprofiles'
import leadsApiService from '@/lib/api/leads'
import type { TemplateCategory } from '@/types/email/template'

interface SavedTemplate {
  id: string
  name: string
  subject: string
  body: string
  description?: string
  content?: string
  templateCategory?: TemplateCategory
  promptInstructions?: string
  performanceStats?: {
    totalSends?: number
    successRate?: number
  }
}

type TemplateType = 'crm' | 'leadgen'

interface UseSavedTemplatesParams {
  templateType: TemplateType
  enabled?: boolean
}

interface UseSavedTemplatesReturn {
  savedTemplates: SavedTemplate[]
  userTemplates: SavedTemplate[]
  selectedTemplate: SavedTemplate | null
  selectTemplate: (template: SavedTemplate | null) => void
  isLoading: boolean
  error: string | null
  reload: () => Promise<void>
}

/**
 * Shared hook for loading and managing saved email templates
 * Used by CRM, Deal, and Lead Gen mass email composers
 */
export const useSavedTemplates = ({
  templateType,
  enabled = true,
}: UseSavedTemplatesParams): UseSavedTemplatesReturn => {
  const [savedTemplates, setSavedTemplates] = useState<SavedTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<SavedTemplate | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTemplates = useCallback(async () => {
    if (!enabled) return

    setIsLoading(true)
    setError(null)

    try {
      let templates: SavedTemplate[]

      if (templateType === 'leadgen') {
        templates = await leadsApiService.getEmailTemplates('email', true, 'leadgen')
      } else {
        templates = await templateApi.listTemplates('email', true, templateType)
      }

      setSavedTemplates(templates)
    } catch (err: any) {
      console.error('Failed to load saved templates:', err)
      setError(err.message || 'Failed to load templates')
    } finally {
      setIsLoading(false)
    }
  }, [templateType, enabled])

  useEffect(() => {
    loadTemplates()
  }, [loadTemplates])

  const selectTemplate = useCallback((template: SavedTemplate | null) => {
    setSelectedTemplate(template)
  }, [])

  const userTemplates = useMemo(
    () => savedTemplates.filter((t) => t.templateCategory !== 'purpose'),
    [savedTemplates]
  )

  return {
    savedTemplates,
    userTemplates,
    selectedTemplate,
    selectTemplate,
    isLoading,
    error,
    reload: loadTemplates,
  }
}
