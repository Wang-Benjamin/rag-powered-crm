import { useState, KeyboardEvent } from 'react'
import { useTranslations } from 'next-intl'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface ProductEntry {
  name: string
  fobPrice: string
  landedPrice: string
}

export type SampleStatus = 'ready' | 'in_production' | 'free_sample' | ''

export interface FactoryDataFieldsProps {
  variant: 'trade'
  products: ProductEntry[]
  certifications: string[]
  moq?: string
  leadTime?: string
  sampleStatus?: SampleStatus
  onProductsChange: (value: ProductEntry[]) => void
  onCertificationsChange: (value: string[]) => void
  onMoqChange?: (value: string) => void
  onLeadTimeChange?: (value: string) => void
  onSampleStatusChange?: (value: SampleStatus) => void
  /** Default collapsed -- pre-populated from factory profile */
  defaultCollapsed?: boolean
  /**
   * V2 compose shell: pass `defaultOpen` to start expanded (overrides
   * `defaultCollapsed`) and `eyebrow` to render an `.eyebrow-mono` style
   * label that becomes the disclose-header text.
   */
  defaultOpen?: boolean
  eyebrow?: string
}

const SAMPLE_STATUS_OPTIONS: { value: SampleStatus; labelKey: string }[] = [
  { value: 'ready', labelKey: 'tradeFields.sampleReady' },
  { value: 'in_production', labelKey: 'tradeFields.sampleInProduction' },
  { value: 'free_sample', labelKey: 'tradeFields.sampleFree' },
]

const FactoryDataFields: React.FC<FactoryDataFieldsProps> = ({
  products,
  certifications,
  moq,
  leadTime,
  sampleStatus = '',
  onProductsChange,
  onCertificationsChange,
  onMoqChange,
  onLeadTimeChange,
  onSampleStatusChange,
  defaultCollapsed = true,
  defaultOpen,
  eyebrow,
}) => {
  const t = useTranslations('email')
  // `defaultOpen` overrides `defaultCollapsed` when explicitly set.
  const initialCollapsed = defaultOpen !== undefined ? !defaultOpen : defaultCollapsed
  const [collapsed, setCollapsed] = useState(initialCollapsed)
  const [certInput, setCertInput] = useState('')

  const addCert = (value: string) => {
    const trimmed = value.trim().toUpperCase()
    if (trimmed && !certifications.includes(trimmed)) {
      onCertificationsChange([...certifications, trimmed])
    }
    setCertInput('')
  }

  const handleCertKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addCert(certInput)
    } else if (e.key === 'Backspace' && !certInput && certifications.length > 0) {
      onCertificationsChange(certifications.slice(0, -1))
    }
  }

  const updateProduct = (
    idx: number,
    field: 'name' | 'fobPrice' | 'landedPrice',
    value: string
  ) => {
    const updated = [...products]
    updated[idx] = { ...updated[idx], [field]: value }
    onProductsChange(updated)
  }

  return (
    <div className="space-y-3">
      {/* Collapsible factory data */}
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        <span className={`transition-transform ${collapsed ? '' : 'rotate-90'}`}>▶</span>
        {eyebrow ?? t('contextFields.sectionLabel')}
        {eyebrow && products.length > 0 && (
          <span className="ml-1 font-mono text-[11px] text-muted-foreground">· {products.length}</span>
        )}
      </button>

      {!collapsed && (
        <div className="space-y-3">
          {/* Products + FOB Prices */}
          <div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5">
                <span className="min-w-0 flex-1 text-[11px] text-muted-foreground">
                  {t('tradeFields.productNamePlaceholder')}
                </span>
                <span className="w-28 text-[11px] text-muted-foreground">
                  {t('tradeFields.fobLabel')}
                </span>
                <span className="w-28 text-[11px] text-muted-foreground">
                  {t('tradeFields.landedLabel')}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    onProductsChange([...products, { name: '', fobPrice: '', landedPrice: '' }])
                  }
                  className="shrink-0 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
                >
                  + {t('tradeFields.addProduct')}
                </button>
              </div>
              {products.map((product, idx) => (
                <div key={idx} className="flex items-center gap-1.5">
                  <Input
                    value={product.name}
                    onChange={(e) => updateProduct(idx, 'name', e.target.value)}
                    placeholder={t('tradeFields.productNamePlaceholder')}
                    className="min-w-0 flex-1 border-border"
                  />
                  <Input
                    value={product.fobPrice}
                    onChange={(e) => updateProduct(idx, 'fobPrice', e.target.value)}
                    placeholder={t('tradeFields.fobPricePlaceholder')}
                    className="w-28 border-border"
                  />
                  <Input
                    value={product.landedPrice}
                    onChange={(e) => updateProduct(idx, 'landedPrice', e.target.value)}
                    placeholder={t('tradeFields.landedPricePlaceholder')}
                    className="w-28 border-border"
                  />
                  {products.length > 1 && (
                    <button
                      type="button"
                      onClick={() => onProductsChange(products.filter((_, i) => i !== idx))}
                      className="shrink-0 px-0.5 text-sm text-zinc-400 hover:text-zinc-600"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* MOQ + Lead Time */}
          <div className="flex gap-3">
            {onMoqChange && (
              <div className="flex-1">
                <Label htmlFor="moq-input" className="mb-1.5 block text-sm">
                  {t('tradeFields.moqLabel')}
                </Label>
                <Input
                  id="moq-input"
                  value={moq || ''}
                  onChange={(e) => onMoqChange(e.target.value)}
                  placeholder={t('tradeFields.moqPlaceholder')}
                  className="border-border"
                />
              </div>
            )}
            {onLeadTimeChange && (
              <div className="flex-1">
                <Label htmlFor="leadtime-input" className="mb-1.5 block text-sm">
                  {t('tradeFields.leadTimeLabel')}
                </Label>
                <Input
                  id="leadtime-input"
                  value={leadTime || ''}
                  onChange={(e) => onLeadTimeChange(e.target.value)}
                  placeholder={t('tradeFields.leadTimePlaceholder')}
                  className="border-border"
                />
              </div>
            )}
          </div>

          {/* Sample Status */}
          {onSampleStatusChange && (
            <div>
              <Label className="mb-1.5 block text-sm">{t('tradeFields.sampleStatusLabel')}</Label>
              <div className="flex flex-wrap gap-1.5">
                {SAMPLE_STATUS_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() =>
                      onSampleStatusChange(sampleStatus === opt.value ? '' : opt.value)
                    }
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                      sampleStatus === opt.value
                        ? 'border-zinc-700 bg-zinc-800 text-white dark:border-zinc-300 dark:bg-zinc-200 dark:text-zinc-900'
                        : 'border-zinc-300 bg-white text-zinc-600 hover:border-zinc-400 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
                    }`}
                  >
                    {t(opt.labelKey as any)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Certifications */}
          <div>
            <Label className="mb-1.5 block text-sm">{t('tradeFields.certificationsLabel')}</Label>
            <div
              className="flex min-h-[38px] cursor-text flex-wrap items-center gap-1.5 rounded-md border border-border bg-background p-2"
              onClick={() => document.getElementById('cert-input')?.focus()}
            >
              {certifications.map((cert) => (
                <span
                  key={cert}
                  className="inline-flex items-center gap-1 rounded-md border border-zinc-300 bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"
                >
                  {cert}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      onCertificationsChange(certifications.filter((c) => c !== cert))
                    }}
                    className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                  >
                    ×
                  </button>
                </span>
              ))}
              <input
                id="cert-input"
                type="text"
                value={certInput}
                onChange={(e) => setCertInput(e.target.value)}
                onKeyDown={handleCertKeyDown}
                onBlur={() => {
                  if (certInput.trim()) addCert(certInput)
                }}
                placeholder={
                  certifications.length === 0 ? t('tradeFields.certificationsPlaceholder') : ''
                }
                className="min-w-[80px] flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default FactoryDataFields
