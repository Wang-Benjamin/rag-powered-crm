'use client'

/**
 * Column-mapping modal (M6).
 *
 * Sits between the CSV/XLSX dropzone's "ready" state and the shared
 * `<ProductCatalogReviewTable />`. Shows every source header with a proposed
 * mapping (from `ingestion_jobs.draft_payload.proposed_mapping`) and the
 * first few sample values so the user can quickly correct wrong guesses.
 *
 * Apply calls `ingestionApi.applyMapping` which turns the confirmed mapping
 * into product rows; the parent swaps this modal out for the review table
 * once the response resolves.
 */

import { useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Select, SelectItem } from '@/components/ui/select'
import { cn } from '@/utils/cn'

// The display options in the modal. "spec" is a sentinel — on Apply it
// expands to `specs.<source_header>` so the backend sees the schema-exact
// string. Kept lock-step with the allowed targets in
// `services.document_ingestion.product_csv_mapper`.
const BASIC_OPTIONS = [
  'name',
  'description',
  'moq',
  'price_range.min',
  'price_range.max',
  'price_range.currency',
  'price_range.unit',
  'image_url',
  'hs_code_suggestion',
] as const

type BasicOption = (typeof BASIC_OPTIONS)[number]
type SelectValue = BasicOption | 'spec' | 'ignore'

function toSelectValue(raw: string | undefined): SelectValue {
  if (!raw) return 'ignore'
  if ((BASIC_OPTIONS as readonly string[]).includes(raw)) return raw as BasicOption
  if (raw === 'ignore') return 'ignore'
  if (raw.startsWith('specs.')) return 'spec'
  return 'ignore'
}

function finalTarget(header: string, value: SelectValue): string {
  if (value === 'spec') return `specs.${header}`
  return value
}

interface ColumnMappingModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  headers: string[]
  sampleRows: Record<string, string>[]
  proposedMapping: Record<string, string>
  rowCount?: number
  fileExt?: string
  onApply: (mapping: Record<string, string>) => Promise<void>
}

export function ColumnMappingModal({
  open,
  onOpenChange,
  headers,
  sampleRows,
  proposedMapping,
  rowCount,
  fileExt,
  onApply,
}: ColumnMappingModalProps) {
  const t = useTranslations('settings.customizeAi.ingestion.columnMapping')

  const [selections, setSelections] = useState<Record<string, SelectValue>>(() => {
    const init: Record<string, SelectValue> = {}
    for (const h of headers) init[h] = toSelectValue(proposedMapping[h])
    return init
  })
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Row-level sample values. Trim to 3 per header for display.
  const samplesByHeader = useMemo(() => {
    const out: Record<string, string[]> = {}
    for (const h of headers) {
      const values: string[] = []
      for (const row of sampleRows) {
        const v = row?.[h]
        if (v && values.length < 3) values.push(v)
      }
      out[h] = values
    }
    return out
  }, [headers, sampleRows])

  // How many source columns are mapped to `name` — must be exactly 1 to apply.
  const nameCount = useMemo(
    () => Object.values(selections).filter((v) => v === 'name').length,
    [selections],
  )

  const handleApply = async () => {
    setError(null)
    if (nameCount !== 1) {
      setError(t('errorNameRequired'))
      return
    }
    const finalMapping: Record<string, string> = {}
    for (const h of headers) {
      finalMapping[h] = finalTarget(h, selections[h] ?? 'ignore')
    }
    setApplying(true)
    try {
      await onApply(finalMapping)
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('apply-mapping failed', err)
      setError(t('errorApplyFailed'))
    } finally {
      setApplying(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] w-[min(900px,95vw)] max-w-[900px] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="title-page">{t('title')}</DialogTitle>
          <p className="text-sm text-zinc-600">{t('subtitle')}</p>
          <div className="mt-2 flex gap-2 text-xs text-zinc-500">
            {typeof rowCount === 'number' ? (
              <span className="rounded bg-zinc-100 px-2 py-0.5">
                {t('rowCount', { count: rowCount })}
              </span>
            ) : null}
            {fileExt ? (
              <span className="rounded bg-zinc-100 px-2 py-0.5 uppercase">
                {fileExt.replace('.', '')}
              </span>
            ) : null}
          </div>
        </DialogHeader>

        <div className="mt-2 overflow-hidden rounded-md border border-zinc-200">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs uppercase text-zinc-500">
              <tr>
                <th className="px-3 py-2 text-left font-medium">{t('colSourceHeader')}</th>
                <th className="px-3 py-2 text-left font-medium">{t('colSampleValues')}</th>
                <th className="px-3 py-2 text-left font-medium">{t('colTargetField')}</th>
              </tr>
            </thead>
            <tbody>
              {headers.map((h, i) => {
                const value = selections[h] ?? 'ignore'
                return (
                  <tr
                    key={`${h}-${i}`}
                    className={cn(
                      'border-t border-zinc-100',
                      value === 'ignore' && 'bg-zinc-50/50',
                    )}
                  >
                    <td className="px-3 py-2 align-top">
                      <div className="font-medium text-zinc-900">{h}</div>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <div className="text-xs text-zinc-600">
                        {samplesByHeader[h].length > 0 ? (
                          samplesByHeader[h].map((v, idx) => (
                            <div key={idx} className="truncate" title={v}>
                              {v}
                            </div>
                          ))
                        ) : (
                          <span className="text-zinc-400">—</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <Select
                        size="sm"
                        value={value}
                        onValueChange={(next) =>
                          setSelections((prev) => ({ ...prev, [h]: next as SelectValue }))
                        }
                        className="w-[180px]"
                      >
                        {BASIC_OPTIONS.map((opt) => (
                          <SelectItem key={opt} value={opt}>
                            {t(`target.${opt}`)}
                          </SelectItem>
                        ))}
                        <SelectItem value="spec">{t('target.spec')}</SelectItem>
                        <SelectItem value="ignore">{t('target.ignore')}</SelectItem>
                      </Select>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {error ? (
          <p className="mt-2 text-sm text-red-600">{error}</p>
        ) : null}

        <DialogFooter className="mt-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t('cancel')}
          </Button>
          <Button
            type="button"
            onClick={handleApply}
            disabled={applying || nameCount !== 1}
          >
            {applying ? t('applying') : t('apply')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
