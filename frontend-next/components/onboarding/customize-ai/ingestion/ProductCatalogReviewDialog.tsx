'use client'

/**
 * Product catalog review dialog (M5 + M6).
 *
 * Hosts a :code:`<DocumentDropzone />` followed by the editable
 * :code:`<ProductCatalogReviewTable />`. On commit, calls
 * :code:`ingestionApi.commit(jobId, {products})` — the backend performs the
 * authoritative bulk insert into ``product_catalog``.
 *
 * CSV/XLSX uploads land directly in the review table (the backend proposes a
 * column mapping, applies it, and materialises products in one pass). A
 * "Re-map columns" button in the table header re-opens the mapping modal
 * for the rare case the LLM misidentified a whole column.
 */

import { useCallback, useState } from 'react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { Columns } from 'lucide-react'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { DocumentDropzone } from './DocumentDropzone'
import { ProductCatalogReviewTable } from './ProductCatalogReviewTable'
import { ColumnMappingModal } from './ColumnMappingModal'
import { ingestionApi } from '@/lib/api/ingestion'
import type { DraftPayload, JobKind, ProductCatalogDraft, ProductRecordDraft } from './types'

interface ProductCatalogReviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Fired after commit succeeds; lets the wizard update any local count badge. */
  onCommitted?: (insertedCount: number) => void
  /**
   * Which catalog lane to use. Defaults to the PDF lane for back-compat with
   * M5. Pass `'auto'` to accept either format in a single drop zone — the
   * storefront's combined upload portal uses this so the user doesn't pick
   * PDF vs CSV up-front.
   */
  kind?: Extract<JobKind, 'product_pdf' | 'product_csv'> | 'auto'
}

interface CsvContext {
  sourceHeaders: string[]
  sampleRows: Record<string, string>[]
  currentMapping: Record<string, string>
  rowCount?: number
  fileExt?: string
}

export function ProductCatalogReviewDialog({
  open,
  onOpenChange,
  onCommitted,
  kind = 'product_pdf',
}: ProductCatalogReviewDialogProps) {
  const t = useTranslations('settings.customizeAi.ingestion.productReview')

  const [jobId, setJobId] = useState<string | null>(null)
  const [products, setProducts] = useState<ProductRecordDraft[]>([])
  const [saving, setSaving] = useState(false)
  const [csvContext, setCsvContext] = useState<CsvContext | null>(null)
  const [remapOpen, setRemapOpen] = useState(false)

  const reset = useCallback(() => {
    setJobId(null)
    setProducts([])
    setSaving(false)
    setCsvContext(null)
    setRemapOpen(false)
  }, [])

  const acceptAttrs =
    kind === 'product_csv'
      ? { accept: 'text/csv,.csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', acceptLabel: 'CSV · XLSX' }
      : kind === 'auto'
        ? {
            accept:
              'application/pdf,.pdf,text/csv,.csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            acceptLabel: 'PDF · CSV · XLSX',
          }
        : { accept: 'application/pdf,.pdf', acceptLabel: 'PDF' }

  // In `auto` mode the dropzone resolves the lane per-file by extension —
  // .pdf → product_pdf, otherwise CSV/XLSX. The CSV-context branch in
  // `handleReady` keys off the response payload, not the static prop, so
  // re-mapping still works for spreadsheets dropped through this entry.
  const dropzoneKind: JobKind | ((file: File) => JobKind) =
    kind === 'auto'
      ? (file: File) =>
          file.name.toLowerCase().endsWith('.pdf') ? 'product_pdf' : 'product_csv'
      : kind

  const handleReady = useCallback((draft: DraftPayload, id: string) => {
    const catalog = draft as ProductCatalogDraft & {
      rowCount?: number
      fileExt?: string
    }
    setJobId(id)
    setProducts(Array.isArray(catalog.products) ? catalog.products : [])

    // CSV-lane payloads carry `sourceHeaders` (for re-mapping); PDF payloads
    // never do. Keying off the payload instead of the static `kind` prop
    // keeps `auto` mode working — a spreadsheet dropped through the
    // unified portal still gets the column-mapping affordance.
    if (catalog.sourceHeaders) {
      setCsvContext({
        sourceHeaders: catalog.sourceHeaders,
        sampleRows: catalog.sampleRows ?? [],
        currentMapping: catalog.columnMapping ?? catalog.proposedMapping ?? {},
        rowCount: catalog.rowCount,
        fileExt: catalog.fileExt,
      })
    } else {
      setCsvContext(null)
    }
  }, [])

  const handleFailed = useCallback(() => {
    // Error UI is already shown by the dropzone; nothing else to do here.
  }, [])

  const handleRemap = useCallback(
    async (mapping: Record<string, string>) => {
      if (!jobId) return
      await ingestionApi.applyMapping(jobId, mapping)
      const refreshed = await ingestionApi.getJob(jobId)
      const catalog = (refreshed.draftPayload ?? {}) as ProductCatalogDraft
      setProducts(Array.isArray(catalog.products) ? catalog.products : [])
      setCsvContext((prev) =>
        prev ? { ...prev, currentMapping: catalog.columnMapping ?? mapping } : prev,
      )
      setRemapOpen(false)
    },
    [jobId],
  )

  const handleCommit = useCallback(async () => {
    if (!jobId) return
    const payload: ProductCatalogDraft = { products }
    setSaving(true)
    try {
      const res = await ingestionApi.commit(jobId, payload as unknown as DraftPayload)
      const count = (res as { inserted_count?: number }).inserted_count ?? products.length
      toast.success(t('toast.success', { count }))
      onCommitted?.(count)
      reset()
      onOpenChange(false)
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('product catalog commit failed', err)
      toast.error(t('toast.failed'))
    } finally {
      setSaving(false)
    }
  }, [jobId, products, t, onCommitted, reset, onOpenChange])

  const handleClose = useCallback(
    (next: boolean) => {
      if (!next && jobId && products.length === 0) {
        // Abandoned before review — best-effort discard so the job row doesn't
        // linger in `ready_for_review`.
        void ingestionApi.discard(jobId).catch(() => {})
      }
      if (!next) reset()
      onOpenChange(next)
    },
    [jobId, products.length, reset, onOpenChange],
  )

  const commitDisabled = saving || !jobId || products.length === 0

  return (
    <>
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="max-h-[90vh] w-[min(1100px,95vw)] max-w-[1100px] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="title-page">{t('title')}</DialogTitle>
            <p className="text-sm text-zinc-600">{t('subtitle')}</p>
          </DialogHeader>

          <div className="space-y-4">
            <DocumentDropzone
              kind={dropzoneKind}
              accept={acceptAttrs.accept}
              acceptLabel={acceptAttrs.acceptLabel}
              maxSizeMB={50}
              onReady={handleReady}
              onFailed={handleFailed}
            />

            {jobId && products.length > 0 ? (
              <div className="space-y-2">
                {csvContext ? (
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setRemapOpen(true)}
                      className="gap-1"
                    >
                      <Columns className="h-4 w-4" />
                      {t('remapColumns')}
                    </Button>
                  </div>
                ) : null}
                <ProductCatalogReviewTable
                  products={products}
                  onChange={setProducts}
                  onUploadImage={undefined}
                />
              </div>
            ) : null}
          </div>

          <DialogFooter className="mt-2">
            <Button type="button" variant="outline" onClick={() => handleClose(false)}>
              {t('cancel')}
            </Button>
            <Button
              type="button"
              onClick={handleCommit}
              disabled={commitDisabled}
            >
              {saving
                ? t('commit')
                : products.length > 0
                  ? t('commitWithCount', { count: products.length })
                  : t('commit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {csvContext ? (
        <ColumnMappingModal
          open={remapOpen}
          onOpenChange={setRemapOpen}
          headers={csvContext.sourceHeaders}
          sampleRows={csvContext.sampleRows}
          proposedMapping={csvContext.currentMapping}
          rowCount={csvContext.rowCount}
          fileExt={csvContext.fileExt}
          onApply={handleRemap}
        />
      ) : null}
    </>
  )
}
