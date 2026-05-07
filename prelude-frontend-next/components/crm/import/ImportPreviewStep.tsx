import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  ArrowLeft,
  Eye,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Users,
  FileText,
} from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { PageLoader } from '@/components/ui/page-loader'
import { crmApiClient } from '@/lib/api/client'

interface PreviewData {
  previewData: Record<string, any>[]
  totalRows: number
  readyForImport: boolean
}

interface ImportPreviewStepProps {
  file: File
  columnMapping: Record<string, string>
  onPreviewComplete: (previewData: PreviewData) => void
  onBack: () => void
}

const ImportPreviewStep: React.FC<ImportPreviewStepProps> = ({
  file,
  columnMapping,
  onPreviewComplete,
  onBack,
}) => {
  const t = useTranslations('crm')
  const tc = useTranslations('common')

  const [previewData, setPreviewData] = useState<PreviewData | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadPreview()
  }, [])

  const loadPreview = async (): Promise<void> => {
    setIsLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      // Note: FormData keys use snake_case to match backend API expectations
      // (FormData bypasses ApiClient's automatic case conversion)
      formData.append('column_mapping', JSON.stringify(columnMapping))
      formData.append('sample_size', '10')

      const result = await crmApiClient.upload('/upload/preview-import', formData)

      setPreviewData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  const handleContinue = (): void => {
    if (previewData) {
      onPreviewComplete(previewData)
    }
  }

  const renderPreviewTable = (): React.ReactElement => {
    if (!previewData || !previewData.previewData.length) {
      return (
        <div className="py-8 text-center text-mute">{t('import.preview.noPreviewData')}</div>
      )
    }

    const columns = Object.keys(previewData.previewData[0])
    const requiredFields = ['company']

    return (
      <div className="overflow-x-auto">
        <table className="min-w-full rounded-lg border border-rule">
          <thead className="bg-paper">
            <tr>
              {columns.map((column, index) => {
                const isRequired = requiredFields.includes(column)
                return (
                  <th
                    key={index}
                    className={`border-b px-4 py-3 text-left text-xs font-medium tracking-wider text-mute uppercase ${
                      isRequired ? 'bg-paper' : ''
                    }`}
                  >
                    <div className="flex items-center">
                      {column}
                      {isRequired && (
                        <span className="ml-1 rounded bg-cream px-1 py-0.5 text-xs text-ink">
                          {tc('required')}
                        </span>
                      )}
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-rule bg-bone">
            {previewData.previewData.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-paper">
                {columns.map((column, colIndex) => {
                  const value = row[column]
                  const isEmpty = !value || (typeof value === 'string' && value.trim() === '')
                  const isRequired = requiredFields.includes(column)

                  return (
                    <td
                      key={colIndex}
                      className={`border-b px-4 py-3 text-sm ${
                        isEmpty && isRequired ? 'bg-threat-lo text-threat' : 'text-ink'
                      }`}
                    >
                      {isEmpty ? (
                        <span className="text-mute italic">
                          {isRequired
                            ? t('import.preview.missingRequiredData')
                            : t('import.preview.empty')}
                        </span>
                      ) : (
                        <span className="block max-w-xs truncate" title={String(value)}>
                          {String(value)}
                        </span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const renderValidationSummary = (): React.ReactElement | null => {
    if (!previewData) return null

    const hasValidData = previewData.readyForImport
    const requiredFields = ['company']

    // Check for missing required data in preview
    let missingDataRows = 0
    previewData.previewData.forEach((row) => {
      const hasMissingRequired = requiredFields.some(
        (field) => !row[field] || (typeof row[field] === 'string' && row[field].trim() === '')
      )
      if (hasMissingRequired) missingDataRows++
    })

    return (
      <div
        className={`rounded-lg p-4 ${hasValidData ? 'border border-accent bg-accent-lo' : 'border border-gold bg-gold-lo'}`}
      >
        <div className="flex items-start">
          {hasValidData ? (
            <CheckCircle className="mt-0.5 mr-3 h-5 w-5 text-accent" />
          ) : (
            <AlertCircle className="mt-0.5 mr-3 h-5 w-5 text-gold" />
          )}
          <div className="flex-1">
            <h4 className={`font-medium ${hasValidData ? 'text-accent' : 'text-gold'}`}>
              {hasValidData
                ? t('import.preview.validationPassed')
                : t('import.preview.validationIssues')}
            </h4>
            <div className={`mt-1 text-sm ${hasValidData ? 'text-accent' : 'text-gold'}`}>
              {hasValidData ? (
                <p>{t('import.preview.validationPassedDesc')}</p>
              ) : (
                <div>
                  <p>{t('import.preview.issuesFound')}</p>
                  {missingDataRows > 0 && (
                    <p className="mt-1">
                      {t('import.preview.missingRequiredRows', { count: missingDataRows })}
                    </p>
                  )}
                  <p className="mt-1">{t('import.preview.skippedRows')}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-6 text-center">
        <div>
          <PageLoader label={t('import.preview.generatingPreview')} className="min-h-[180px]" />
          <p className="text-mute">{t('import.preview.generatingDescription')}</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6 text-center">
        <div className="rounded-lg border border-threat/25 bg-threat-lo p-4">
          <div className="flex items-start">
            <AlertCircle className="mt-0.5 mr-3 h-5 w-5 text-threat" />
            <div>
              <h4 className="font-medium text-threat">{t('import.preview.previewError')}</h4>
              <p className="mt-1 text-sm text-threat">{error}</p>
            </div>
          </div>
        </div>
        <div className="flex justify-between">
          <Button variant="outline" onClick={onBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('import.preview.backToMapping')}
          </Button>
          <Button onClick={loadPreview}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {t('import.preview.retryPreview')}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <Eye className="mx-auto mb-4 h-12 w-12 text-mute" />
        <h3 className="mb-2 title-panel">{t('import.preview.title')}</h3>
        <p className="text-mute">{t('import.preview.description')}</p>
      </div>

      {/* Summary Stats */}
      {previewData && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-paper p-4 text-center">
            <FileText className="mx-auto mb-2 h-6 w-6 text-mute" />
            <div className="text-sm text-mute">{t('import.preview.file')}</div>
            <div className="font-medium text-ink">{file.name}</div>
          </div>
          <div className="rounded-lg bg-paper p-4 text-center">
            <Users className="mx-auto mb-2 h-6 w-6 text-mute" />
            <div className="text-sm text-ink">{t('import.preview.totalRows')}</div>
            <div className="font-medium text-deep">{previewData.totalRows}</div>
          </div>
          <div className="rounded-lg bg-accent-lo p-4 text-center">
            <CheckCircle className="mx-auto mb-2 h-6 w-6 text-accent" />
            <div className="text-sm text-accent">{t('import.preview.previewRows')}</div>
            <div className="font-medium text-accent">{previewData.previewData.length}</div>
          </div>
          <div className="rounded-lg bg-paper p-4 text-center">
            <Eye className="mx-auto mb-2 h-6 w-6 text-mute" />
            <div className="text-sm text-ink">{t('import.preview.mappedFields')}</div>
            <div className="font-medium text-ink">{Object.keys(columnMapping).length}</div>
          </div>
        </div>
      )}

      {/* Validation Summary */}
      {renderValidationSummary()}

      {/* Column Mapping Summary */}
      {Object.keys(columnMapping).length > 0 && (
        <div className="rounded-lg bg-paper p-4">
          <h4 className="mb-3 title-block">{t('import.preview.columnMappings')}</h4>
          <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
            {Object.entries(columnMapping).map(([source, target]) => (
              <div
                key={source}
                className="flex items-center justify-between rounded bg-bone px-3 py-2"
              >
                <span className="text-mute">{source}</span>
                <ArrowRight className="mx-2 h-4 w-4 text-mute" />
                <span className="font-medium text-ink">{target}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Preview Table */}
      <div>
        <h4 className="mb-3 title-block">{t('import.preview.dataPreview')}</h4>
        <div className="overflow-hidden rounded-lg border border-rule">
          {renderPreviewTable()}
        </div>
      </div>

      {/* Import Options */}
      <div className="rounded-lg bg-paper p-4">
        <h4 className="mb-2 title-block">{t('import.preview.importSettings')}</h4>
        <div className="space-y-1 text-sm text-ink">
          <div>{t('import.preview.duplicateSkip')}</div>
          <div>{t('import.preview.missingSkip')}</div>
          <div>{t('import.preview.invalidClean')}</div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-between border-t pt-4">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('import.preview.backToMapping')}
        </Button>
        <Button
          onClick={handleContinue}
          disabled={!previewData}
          className="bg-accent hover:bg-accent"
        >
          {t('import.preview.startImport')}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

export default ImportPreviewStep
