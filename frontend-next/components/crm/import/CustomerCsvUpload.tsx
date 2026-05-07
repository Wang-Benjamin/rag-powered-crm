import React, { useState, useCallback } from 'react'
import {
  Upload,
  CheckCircle,
  AlertCircle,
  X,
  Download,
  ArrowRight,
  Users,
  RefreshCw,
  Eye,
  Settings,
} from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import ColumnMappingStep from './ColumnMappingStep'
import ImportPreviewStep from './ImportPreviewStep'
import { crmApiClient } from '@/lib/api/client'

interface AnalysisResult {
  suggestedMappings?: { [key: string]: string }
  sourceColumns: string[]
  crmFields: string[]
}

interface PreviewData {
  // Define based on what ImportPreviewStep expects
}

interface ImportResult {
  totalRows: number
  insertedRows: number
  skippedRows: number
  failedRows: number
  processingTimeMs: number
}

interface CustomerCsvUploadProps {
  onImportComplete?: (result: ImportResult) => void
  onClose: () => void
}

type Step = 'upload' | 'mapping' | 'preview' | 'importing' | 'complete'

interface TemplateRow {
  [key: string]: string
}

const CustomerCsvUpload: React.FC<CustomerCsvUploadProps> = ({ onImportComplete, onClose }) => {
  const t = useTranslations('crm')
  const tc = useTranslations('common')
  const [currentStep, setCurrentStep] = useState<Step>('upload')
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [columnMapping, setColumnMapping] = useState<{ [key: string]: string }>({})
  const [previewData, setPreviewData] = useState<PreviewData | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)

  // Template data based on CRM customer fields
  const generateTemplateData = (): TemplateRow[] => {
    return [
      {
        'Company Name': 'Example Corp',
        'Primary Contact': 'John Smith',
        'Email Address': 'john.smith@example.com',
        'Phone Number': '+1 (555) 123-4567',
        Industry: 'Technology',
        Location: 'San Francisco, CA',
        Status: 'active',
        'Client Type': 'enterprise',
        'Annual Recurring Revenue': '50000',
        'Contract Value': '100000',
        'Monthly Value': '4167',
        'Renewal Date': '2024-12-31',
        'Health Score': '85',
        'Churn Risk': 'low',
        'Satisfaction Score': '9.0',
        'Expansion Potential': 'high',
      },
      {
        'Company Name': 'Sample Inc',
        'Primary Contact': 'Jane Doe',
        'Email Address': 'jane.doe@sample.com',
        'Phone Number': '+1 (555) 987-6543',
        Industry: 'Finance',
        Location: 'New York, NY',
        Status: 'active',
        'Client Type': 'mid-market',
        'Annual Recurring Revenue': '25000',
        'Contract Value': '50000',
        'Monthly Value': '2083',
        'Renewal Date': '2024-06-30',
        'Health Score': '75',
        'Churn Risk': 'medium',
        'Satisfaction Score': '8.0',
        'Expansion Potential': 'medium',
      },
    ]
  }

  const downloadTemplate = () => {
    const templateData = generateTemplateData()
    const headers = Object.keys(templateData[0])

    // Create CSV content with proper escaping
    const csvContent = [
      headers.join(','),
      ...templateData.map((row) =>
        headers
          .map((header) => {
            const value = String(row[header] || '')
            // Always quote non-empty values to avoid parsing issues
            if (!value) return ''
            // Escape quotes by doubling them, then wrap in quotes
            return `"${value.replace(/"/g, '""')}"`
          })
          .join(',')
      ),
    ].join('\n')

    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', 'customer_import_template.csv')
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleFileUpload = async (file: File) => {
    if (!file) return

    const allowedTypes = [
      'text/csv',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ]

    if (!allowedTypes.includes(file.type)) {
      setError(t('import.csvUpload.fileError'))
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      console.log(
        '[CustomerCsvUpload] Uploading file:',
        file.name,
        'size:',
        file.size,
        'type:',
        file.type
      )

      const result = await crmApiClient.upload('/upload/analyze-csv', formData)

      setUploadedFile(file)
      setAnalysisResult(result)
      setColumnMapping(result.suggestedMappings || {})
      setCurrentStep('mapping')
    } catch (err) {
      console.error('[CustomerCsvUpload] Upload error:', err)
      setError((err as Error).message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      handleFileUpload(file)
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)

    const file = e.dataTransfer.files[0]
    handleFileUpload(file)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
  }, [])

  const handleMappingComplete = (mappings: { [key: string]: string }) => {
    setColumnMapping(mappings)
    setCurrentStep('preview')
  }

  const handlePreviewComplete = (preview: PreviewData) => {
    setPreviewData(preview)
    performImport()
  }

  const performImport = async () => {
    setCurrentStep('importing')
    setIsLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', uploadedFile!)
      // Note: FormData keys use snake_case to match backend API expectations
      // (FormData bypasses ApiClient's automatic case conversion)
      formData.append('column_mapping', JSON.stringify(columnMapping))
      formData.append('skip_duplicates', 'true')

      const result = await crmApiClient.upload('/upload/import-customers', formData)

      setImportResult(result)
      setCurrentStep('complete')

      // Notify parent component
      if (onImportComplete) {
        onImportComplete(result)
      }
    } catch (err) {
      setError((err as Error).message)
      setCurrentStep('preview') // Go back to preview on error
    } finally {
      setIsLoading(false)
    }
  }

  const resetUpload = () => {
    setCurrentStep('upload')
    setUploadedFile(null)
    setAnalysisResult(null)
    setColumnMapping({})
    setPreviewData(null)
    setImportResult(null)
    setError(null)
  }

  const renderUploadStep = () => (
    <div className="space-y-6">
      <div className="text-center">
        <Users className="mx-auto mb-4 h-12 w-12 text-mute" />
        <h3 className="mb-2 title-panel">
          {t('import.csvUpload.heading')}
        </h3>
        <p className="mb-4 text-mute">{t('import.csvUpload.description')}</p>

        {/* Download Template Section */}
        <div className="mb-6 rounded-lg border border-accent bg-accent-lo p-4">
          <div className="mb-2 flex items-center justify-center gap-3">
            <Download className="h-5 w-5 text-accent" />
            <span className="font-medium text-accent">{t('import.csvUpload.needTemplate')}</span>
          </div>
          <p className="mb-3 text-sm text-accent">{t('import.csvUpload.templateDescription')}</p>
          <Button
            onClick={downloadTemplate}
            variant="outline"
            size="sm"
            className="border-accent bg-bone text-accent hover:bg-paper"
          >
            <Download className="mr-2 h-4 w-4" />
            {t('import.downloadTemplate')}
          </Button>
        </div>
      </div>

      <div
        className={`rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          dragActive ? 'border-deep bg-paper' : 'border-rule hover:border-fog'
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <Upload className="mx-auto mb-4 h-12 w-12 text-mute" />
        <div className="space-y-2">
          <p className="title-block">
            {t('import.csvUpload.dropFile')}{' '}
            <label
              htmlFor="csv-file-input"
              className="cursor-pointer text-ink underline decoration-dotted hover:text-mute"
            >
              {t('import.csvUpload.browse')}
            </label>
          </p>
          <input
            id="csv-file-input"
            type="file"
            className="hidden"
            accept=".csv,.xlsx,.xls"
            onChange={handleFileSelect}
            disabled={isLoading}
          />
          <p className="text-sm text-mute">{t('import.csvUpload.fileFormats')}</p>
        </div>
      </div>

      <div className="rounded-lg bg-paper p-4">
        <h4 className="mb-2 title-block">{t('import.csvUpload.fileRequirements')}</h4>
        <div className="space-y-2 text-sm text-ink">
          <div>
            <span className="font-medium">{t('import.csvUpload.requiredFields')}</span>
            <ul className="mt-1 ml-4 space-y-1">
              <li>• {t('import.csvUpload.companyName')}</li>
            </ul>
          </div>
          <div>
            <span className="font-medium">{t('import.csvUpload.optionalFields')}</span>
            <p className="mt-1">{t('import.csvUpload.optionalFieldsList')}</p>
          </div>
        </div>
        <p className="mt-3 text-sm text-ink">{t('import.csvUpload.templateTip')}</p>
      </div>
    </div>
  )

  const renderStepIndicator = () => {
    const steps = [
      { id: 'upload', label: t('import.csvUpload.stepUpload'), icon: Upload },
      { id: 'mapping', label: t('import.csvUpload.stepMapping'), icon: Settings },
      { id: 'preview', label: t('import.csvUpload.stepPreview'), icon: Eye },
      { id: 'importing', label: t('import.csvUpload.stepImport'), icon: RefreshCw },
      { id: 'complete', label: t('import.csvUpload.stepComplete'), icon: CheckCircle },
    ]

    const currentIndex = steps.findIndex((step) => step.id === currentStep)

    return (
      <div className="mb-6 flex items-center justify-center space-x-4">
        {steps.map((step, index) => {
          const Icon = step.icon
          const isActive = index === currentIndex
          const isCompleted = index < currentIndex
          const isDisabled = index > currentIndex

          return (
            <div key={step.id} className="flex items-center">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full border-2 ${
                  isActive
                    ? 'border-deep bg-mute text-bone'
                    : isCompleted
                      ? 'border-accent bg-accent text-bone'
                      : 'border-rule text-mute'
                }`}
              >
                <Icon className="h-5 w-5" />
              </div>
              <span
                className={`ml-2 text-sm font-medium ${
                  isActive || isCompleted ? 'text-ink' : 'text-mute'
                }`}
              >
                {step.label}
              </span>
              {index < steps.length - 1 && <ArrowRight className="ml-4 h-4 w-4 text-rule" />}
            </div>
          )
        })}
      </div>
    )
  }

  const renderImportingStep = () => (
    <div className="space-y-6 text-center">
      <div className="flex justify-center">
        <RefreshCw className="h-16 w-16 animate-spin text-mute" />
      </div>
      <div>
        <h3 className="mb-2 title-panel">
          {t('import.csvUpload.importing')}
        </h3>
        <p className="text-mute">{t('import.csvUpload.importingDescription')}</p>
      </div>
    </div>
  )

  const renderCompleteStep = () => (
    <div className="space-y-6 text-center">
      <div className="flex justify-center">
        <CheckCircle className="h-16 w-16 text-accent" />
      </div>
      <div>
        <h3 className="mb-2 title-panel">
          {t('import.csvUpload.importComplete')}
        </h3>
        {importResult && (
          <div className="mb-4 rounded-lg bg-accent-lo p-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium text-accent">
                  {t('import.csvUpload.totalRows')}
                </span>
                <span className="ml-2 text-accent">{importResult.totalRows}</span>
              </div>
              <div>
                <span className="font-medium text-accent">{t('import.csvUpload.imported')}</span>
                <span className="ml-2 text-accent">{importResult.insertedRows}</span>
              </div>
              <div>
                <span className="font-medium text-accent">{t('import.csvUpload.skipped')}</span>
                <span className="ml-2 text-accent">{importResult.skippedRows}</span>
              </div>
              <div>
                <span className="font-medium text-accent">{t('import.csvUpload.failed')}</span>
                <span className="ml-2 text-accent">{importResult.failedRows}</span>
              </div>
            </div>
            <div className="mt-3 text-sm text-accent">
              {t('import.csvUpload.processingTime', {
                time: Math.round(importResult.processingTimeMs),
              })}
            </div>
          </div>
        )}
      </div>
      <div className="space-x-3">
        <Button onClick={resetUpload} variant="outline">
          {t('import.csvUpload.importAnother')}
        </Button>
        <Button onClick={onClose}>{tc('close')}</Button>
      </div>
    </div>
  )

  return (
    <Dialog open={true} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex max-h-[95vh] w-full max-w-4xl flex-col p-0" onClose={onClose}>
        {/* Modal Header */}
        <DialogHeader className="border-b border-rule p-6">
          <div className="flex items-center gap-4">
            <div>
              <DialogTitle className="title-page">
                {t('import.csvUpload.importTitle')}
              </DialogTitle>
              <DialogDescription className="text-sm text-mute">
                {t('import.csvUpload.importDescription')}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Step Indicator */}
        {currentStep !== 'upload' && (
          <div className="border-b border-rule bg-paper px-6 py-3">
            {renderStepIndicator()}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {error && (
            <div className="mb-6 rounded-lg border border-threat/25 bg-threat-lo p-4">
              <div className="flex items-start">
                <AlertCircle className="mt-0.5 mr-3 h-5 w-5 text-threat" />
                <div>
                  <h4 className="font-medium text-threat">Error</h4>
                  <p className="mt-1 text-sm text-threat">{error}</p>
                </div>
              </div>
            </div>
          )}

          {currentStep === 'upload' && <div>{renderUploadStep()}</div>}

          {currentStep === 'mapping' && analysisResult && (
            <div>
              <ColumnMappingStep
                analysisResult={analysisResult}
                onMappingComplete={handleMappingComplete}
                onBack={() => setCurrentStep('upload')}
              />
            </div>
          )}

          {currentStep === 'preview' && (
            <div>
              <ImportPreviewStep
                file={uploadedFile!}
                columnMapping={columnMapping}
                onPreviewComplete={handlePreviewComplete}
                onBack={() => setCurrentStep('mapping')}
              />
            </div>
          )}

          {currentStep === 'importing' && <div>{renderImportingStep()}</div>}

          {currentStep === 'complete' && <div>{renderCompleteStep()}</div>}

          {isLoading && currentStep !== 'importing' && (
            <div className="absolute inset-0 flex items-center justify-center bg-bone/75">
              <RefreshCw className="h-8 w-8 animate-spin text-mute" />
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default CustomerCsvUpload
