'use client'

import { useMemo } from 'react'
import { EmailTemplateCard } from './EmailTemplateCard'
import type { EmailTemplate } from '@/types/email'

interface SimpleTemplateListProps {
  templates: EmailTemplate[]
  selectedTemplate: EmailTemplate | null
  onTemplateSelect: (template: EmailTemplate) => void
  onDeleteTemplate?: (template: EmailTemplate) => void
}

export function SimpleTemplateList({
  templates,
  selectedTemplate,
  onTemplateSelect,
  onDeleteTemplate,
}: SimpleTemplateListProps) {
  // Build a map of template IDs to names for parent lookup
  const templateNameMap = useMemo(() => {
    const map = new Map<string, string>()
    templates.forEach((t) => map.set(t.id, t.name))
    return map
  }, [templates])

  if (templates.length === 0) {
    return null
  }

  return (
    <div className="space-y-1">
      {templates.map((template) => {
        // Get parent name for variations (level === 1)
        const parentName =
          template.level === 1 && template.parentId
            ? templateNameMap.get(template.parentId)
            : undefined

        return (
          <EmailTemplateCard
            key={template.id}
            template={template}
            isSelected={selectedTemplate?.id === template.id}
            onSelect={() => onTemplateSelect(template)}
            onDelete={onDeleteTemplate ? () => onDeleteTemplate(template) : undefined}
            parentName={parentName}
          />
        )
      })}
    </div>
  )
}

