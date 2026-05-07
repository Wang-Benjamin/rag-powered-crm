import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  ArrowLeft,
  CheckCircle,
  AlertTriangle,
  Info,
  X,
  Settings,
  Sparkles,
  Zap,
} from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface MappingSuggestion {
  sourceColumn: string
  targetColumn: string | null
  confidence: number
  mappingType: string
}

interface SourceColumnInfo {
  name: string
  originalPosition: number
  dataType: string
  sampleValues: any[]
  nullPercentage: number
}

interface AnalysisResult {
  sourceColumns: string[]
  crmFields: string[]
  suggestedMappings?: Record<string, string>
  mappingSuggestions?: MappingSuggestion[]
  overallConfidence?: number
  recommendedFlow?: 'QUICK_UPLOAD' | 'SHOW_MAPPING_UI' | 'REQUIRE_REVIEW'
  sourceColumnsInfo?: SourceColumnInfo[]
}

interface ColumnMappingStepProps {
  analysisResult: AnalysisResult
  onMappingComplete: (mappings: Record<string, string>) => void
  onBack: () => void
}

interface FieldDescriptions {
  [key: string]: string
}

const ColumnMappingStep: React.FC<ColumnMappingStepProps> = ({
  analysisResult,
  onMappingComplete,
  onBack,
}) => {
  const t = useTranslations('crm')
  const tc = useTranslations('common')

  const [mappings, setMappings] = useState<Record<string, string>>({})
  const [isValid, setIsValid] = useState<boolean>(false)

  // Get confidence for a source column
  const getColumnConfidence = (sourceColumn: string): MappingSuggestion | undefined => {
    return analysisResult.mappingSuggestions?.find((s) => s.sourceColumn === sourceColumn)
  }

  // Get confidence badge color
  const getConfidenceBadgeVariant = (
    confidence: number
  ): 'default' | 'secondary' | 'destructive' | 'outline' => {
    if (confidence >= 90) return 'default'
    if (confidence >= 70) return 'secondary'
    if (confidence >= 50) return 'outline'
    return 'destructive'
  }

  // Get confidence label
  const getConfidenceLabel = (confidence: number): string => {
    if (confidence >= 90) return t('import.columnMapping.confidenceHigh')
    if (confidence >= 70) return t('import.columnMapping.confidenceGood')
    if (confidence >= 50) return t('import.columnMapping.confidenceFair')
    return t('import.columnMapping.confidenceLow')
  }

  // CRM field descriptions for better UX
  const descKeys = [
    'company',
    'primaryContact',
    'email',
    'phone',
    'location',
    'status',
    'clientType',
    'healthScore',
  ] as const
  const fieldDescriptions: FieldDescriptions = {}
  for (const key of descKeys) {
    fieldDescriptions[key] = t(`import.columnMapping.fieldDescriptions.${key}`)
  }

  const requiredFields: string[] = ['company']

  useEffect(() => {
    // Initialize mappings with suggested mappings
    setMappings(analysisResult.suggestedMappings || {})
  }, [analysisResult])

  useEffect(() => {
    // Check if all required fields are mapped
    const mappedFields = Object.values(mappings)
    const hasAllRequired = requiredFields.every((field) => mappedFields.includes(field))
    setIsValid(hasAllRequired)
  }, [mappings])

  const handleMappingChange = (sourceColumn: string, targetField: string): void => {
    setMappings((prev) => {
      const newMappings = { ...prev }

      // Remove this target field from any other source column
      Object.keys(newMappings).forEach((key) => {
        if (newMappings[key] === targetField) {
          delete newMappings[key]
        }
      })

      // Set the new mapping (or remove if targetField is empty)
      if (targetField) {
        newMappings[sourceColumn] = targetField
      } else {
        delete newMappings[sourceColumn]
      }

      return newMappings
    })
  }

  const handleContinue = (): void => {
    onMappingComplete(mappings)
  }

  const getMappedSourceColumn = (targetField: string): string | undefined => {
    return Object.keys(mappings).find((key) => mappings[key] === targetField)
  }

  const getUnmappedSourceColumns = (): string[] => {
    return analysisResult.sourceColumns.filter((col) => !mappings[col])
  }

  const getUnmappedRequiredFields = (): string[] => {
    const mappedFields = Object.values(mappings)
    return requiredFields.filter((field) => !mappedFields.includes(field))
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <Settings className="mx-auto mb-4 h-12 w-12 text-mute" />
        <h3 className="mb-2 title-panel">
          {t('import.columnMapping.title')}
        </h3>
        <p className="text-mute">{t('import.columnMapping.description')}</p>
      </div>

      {/* Status Summary */}
      <div className="rounded-lg bg-paper p-4">
        <div
          className={`grid ${analysisResult.overallConfidence !== undefined ? 'grid-cols-4' : 'grid-cols-3'} gap-4 text-sm`}
        >
          <div className="text-center">
            <div className="font-medium text-ink">{analysisResult.sourceColumns.length}</div>
            <div className="text-mute">{t('import.columnMapping.sourceColumns')}</div>
          </div>
          <div className="text-center">
            <div className="font-medium text-ink">{Object.keys(mappings).length}</div>
            <div className="text-mute">{t('import.columnMapping.mappedColumns')}</div>
          </div>
          <div className="text-center">
            <div className={`font-medium ${isValid ? 'text-accent' : 'text-gold'}`}>
              {getUnmappedRequiredFields().length === 0
                ? t('import.columnMapping.ready')
                : t('import.columnMapping.missingRequired')}
            </div>
            <div className="text-mute">{tc('status')}</div>
          </div>
          {analysisResult.overallConfidence !== undefined && (
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 font-medium text-ink">
                {analysisResult.overallConfidence >= 0.7 && (
                  <Sparkles className="h-4 w-4 text-gold" />
                )}
                {Math.round(analysisResult.overallConfidence * 100)}%
              </div>
              <div className="text-mute">{t('import.columnMapping.confidence')}</div>
            </div>
          )}
        </div>
      </div>

      {/* Validation Messages */}
      {getUnmappedRequiredFields().length > 0 && (
        <div className="rounded-lg border border-gold bg-gold-lo p-4">
          <div className="flex items-start">
            <AlertTriangle className="mt-0.5 mr-3 h-5 w-5 text-gold" />
            <div>
              <h4 className="font-medium text-gold">
                {t('import.columnMapping.requiredMissing')}
              </h4>
              <p className="mt-1 text-sm text-gold">
                {t('import.columnMapping.requiredMissingDesc', {
                  fields: getUnmappedRequiredFields().join(', '),
                })}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Mapping Interface */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Source Columns */}
        <div>
          <h4 className="mb-3 title-block">
            {t('import.columnMapping.yourFileColumns')}
          </h4>
          <div className="max-h-96 space-y-2 overflow-y-auto">
            {analysisResult.sourceColumns.map((column, index) => {
              const mappedTo = mappings[column]
              const suggestionInfo = getColumnConfidence(column)
              const confidence = suggestionInfo?.confidence || 0
              return (
                <div
                  key={index}
                  className={`rounded-lg border p-3 ${
                    mappedTo ? 'border-rule bg-paper' : 'border-rule bg-bone'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-ink">{column}</span>
                      {suggestionInfo && confidence > 0 && (
                        <Badge variant={getConfidenceBadgeVariant(confidence)} className="text-xs">
                          {suggestionInfo.mappingType === 'AI' && <Zap className="mr-1 h-3 w-3" />}
                          {confidence}%
                        </Badge>
                      )}
                    </div>
                    {mappedTo && (
                      <span className="rounded bg-cream px-2 py-1 text-xs text-ink">
                        → {mappedTo}
                      </span>
                    )}
                  </div>
                  <select
                    value={mappedTo || ''}
                    onChange={(e) => handleMappingChange(column, e.target.value)}
                    className="mt-2 w-full rounded border border-rule p-2 text-sm"
                  >
                    <option value="">{t('import.columnMapping.selectCrmField')}</option>
                    {analysisResult.crmFields.map((field) => (
                      <option
                        key={field}
                        value={field}
                        disabled={
                          getMappedSourceColumn(field) !== undefined &&
                          getMappedSourceColumn(field) !== column
                        }
                      >
                        {field}{' '}
                        {requiredFields.includes(field)
                          ? `(${t('import.columnMapping.required')})`
                          : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )
            })}
          </div>
        </div>

        {/* CRM Fields */}
        <div>
          <h4 className="mb-3 title-block">{t('import.columnMapping.crmFields')}</h4>
          <div className="max-h-96 space-y-2 overflow-y-auto">
            {analysisResult.crmFields.map((field, index) => {
              const mappedSource = getMappedSourceColumn(field)
              const isRequired = requiredFields.includes(field)

              return (
                <div
                  key={index}
                  className={`rounded-lg border p-3 ${
                    mappedSource
                      ? 'border-accent bg-accent-lo'
                      : isRequired
                        ? 'border-gold bg-gold-lo'
                        : 'border-rule bg-bone'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <span className="font-medium text-ink">{field}</span>
                      {isRequired && (
                        <span className="ml-2 rounded bg-threat-lo px-2 py-1 text-xs text-threat">
                          {t('import.columnMapping.required')}
                        </span>
                      )}
                    </div>
                    {mappedSource ? (
                      <div className="flex items-center">
                        <CheckCircle className="mr-1 h-4 w-4 text-accent" />
                        <span className="text-xs text-accent">{mappedSource}</span>
                      </div>
                    ) : isRequired ? (
                      <AlertTriangle className="h-4 w-4 text-gold" />
                    ) : null}
                  </div>
                  {fieldDescriptions[field] && (
                    <p className="mt-1 text-xs text-mute">{fieldDescriptions[field]}</p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Auto-mapping suggestions */}
      {Object.keys(analysisResult.suggestedMappings || {}).length > 0 && (
        <div className="rounded-lg border border-rule bg-paper p-4">
          <div className="flex items-start">
            <Info className="mt-0.5 mr-3 h-5 w-5 text-mute" />
            <div>
              <h4 className="title-block">
                {t('import.columnMapping.autoDetected')}
              </h4>
              <p className="mt-1 text-sm text-ink">
                {t('import.columnMapping.autoDetectedDesc', {
                  count: Object.keys(analysisResult.suggestedMappings || {}).length,
                })}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Unmapped columns warning */}
      {getUnmappedSourceColumns().length > 0 && (
        <div className="rounded-lg border border-gold bg-gold-lo p-4">
          <div className="flex items-start">
            <AlertTriangle className="mt-0.5 mr-3 h-5 w-5 text-gold" />
            <div>
              <h4 className="font-medium text-gold">
                {t('import.columnMapping.unmappedColumns')}
              </h4>
              <p className="mt-1 text-sm text-gold">
                {t('import.columnMapping.unmappedColumnsDesc', {
                  columns: getUnmappedSourceColumns().join(', '),
                })}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-between border-t pt-4">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {tc('back')}
        </Button>
        <Button
          onClick={handleContinue}
          disabled={!isValid}
          className={isValid ? '' : 'cursor-not-allowed opacity-50'}
        >
          {t('import.columnMapping.continueToPreview')}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

export default ColumnMappingStep
