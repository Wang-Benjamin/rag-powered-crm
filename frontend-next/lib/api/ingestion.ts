/**
 * Document ingestion API client.
 *
 * Thin wrapper over `settingsApiClient` for the four `/ingestion/*` routes
 * plus a dev-mode mock. In mock mode, the filename decides the story:
 *
 *   - `fail*`     → job transitions to `failed` after "processing".
 *   - `slow*`     → stays in `processing` long enough to show the spinner.
 *   - anything else → `processing` (one poll tick) → `ready_for_review`.
 *
 * Backend endpoints don't exist yet (they land in M3). Calling the real
 * client before the backend is deployed will 404 — that's fine, dev-mode
 * mock is the M2 path.
 */

import { settingsApiClient } from './client'
import type {
  CertificationDraft,
  CompanyProfileDraft,
  DraftPayload,
  IngestionJob,
  JobKind,
  JobStatus,
  ProductCatalogDraft,
} from '@/components/onboarding/customize-ai/ingestion/types'

// ===== dev-mode toggle =====
//
// Set NEXT_PUBLIC_INGESTION_MOCK=1 in .env.local to force the mock on. The
// mock is also enabled automatically if the env var is unset and we're in
// development mode AND the user passes `?mock=1` on the URL — handy for
// poking states in the dev demo page without restarting the dev server.

function isMockEnabled(): boolean {
  if (typeof window === 'undefined') return false
  if (process.env.NEXT_PUBLIC_INGESTION_MOCK === '1') return true
  if (process.env.NODE_ENV !== 'development') return false
  try {
    const params = new URLSearchParams(window.location.search)
    return params.get('mock') === '1'
  } catch {
    return false
  }
}

// ===== real client =====

async function realUpload(file: File, kind: JobKind): Promise<IngestionJob> {
  const form = new FormData()
  form.append('file', file)
  form.append('kind', kind)
  return settingsApiClient.upload<IngestionJob>('/ingestion/upload', form)
}

async function realGetJob(jobId: string): Promise<IngestionJob> {
  return settingsApiClient.get<IngestionJob>(`/ingestion/jobs/${jobId}`)
}

async function realCommit(jobId: string, payload: DraftPayload): Promise<{ success: boolean }> {
  return settingsApiClient.post<{ success: boolean }>(
    `/ingestion/jobs/${jobId}/commit`,
    { payload },
  )
}

async function realDiscard(jobId: string): Promise<{ success: boolean }> {
  return settingsApiClient.delete<{ success: boolean }>(`/ingestion/jobs/${jobId}`)
}

async function realApplyMapping(
  jobId: string,
  mapping: Record<string, string>,
): Promise<{ success: boolean; productCount: number }> {
  return settingsApiClient.post<{ success: boolean; productCount: number }>(
    `/ingestion/jobs/${jobId}/apply-mapping`,
    { mapping },
  )
}

// ===== mock client =====
//
// State lives on `globalThis` (hot-reload-safe) keyed by jobId. Each mock
// job advances on its own timer: immediately → `processing`, then after
// ~2.5s → `ready_for_review` (or `failed` if the filename starts with
// "fail"). "slow*" files stretch processing to ~8s so the polling UI is
// observable end-to-end.

interface MockJobRow {
  job: IngestionJob
  readyAt: number
  outcome: 'ready_for_review' | 'failed'
}

const MOCK_STATE_KEY = '__preludeIngestionMockJobs__'
function mockState(): Map<string, MockJobRow> {
  const g = globalThis as unknown as Record<string, unknown>
  if (!g[MOCK_STATE_KEY]) g[MOCK_STATE_KEY] = new Map()
  return g[MOCK_STATE_KEY] as Map<string, MockJobRow>
}

function makeId(): string {
  return 'mock-' + Math.random().toString(36).slice(2, 10)
}

function mockPayloadFor(kind: JobKind): DraftPayload {
  switch (kind) {
    case 'company_profile':
      return {
        companyNameEn: 'Fujian Harbor Shoes Co., Ltd.',
        companyNameLocal: '福建海港鞋业有限公司',
        yearFounded: 2008,
        headquartersLocation: 'Quanzhou, Fujian, China',
        employeeCountRange: '200-500',
        businessType: 'manufacturer',
        productDescription:
          'Sports and casual footwear for global private-label and OEM brands. Specializes in vulcanized rubber and EVA-injected outsoles.',
        mainMarkets: ['United States', 'Germany', 'United Kingdom', 'Brazil'],
        factoryLocation: 'Jinjiang Industrial Park, Quanzhou',
        factorySizeSqm: 18500,
        productionCapacity: '500,000 pairs per month',
        certificationsMentioned: ['ISO 9001', 'BSCI', 'REACH'],
        keyCustomersMentioned: ['Decathlon', 'Puma (private label)'],
      } satisfies CompanyProfileDraft
    case 'product_csv':
      // Runner auto-applies the mapping, so the dropzone's `ready` payload
      // already carries materialised products. `sourceHeaders` + `sampleRows`
      // stick around on the draft so the "Re-map columns" button can re-open
      // the mapping modal with current state.
      return {
        products: [
          {
            name: 'Runner X1',
            moq: 300,
            specs: { Material: 'EVA' },
            imageUrl: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=300&q=70',
            priceRange: { min: 4.8, currency: 'USD', unit: 'piece' },
          },
          {
            name: 'Trainer Pro 2',
            moq: 200,
            specs: { Material: 'Mesh + EVA' },
            priceRange: { min: 5.8, currency: 'USD', unit: 'piece' },
          },
          {
            name: 'Canvas Low',
            moq: 500,
            specs: { Material: 'Canvas' },
            imageUrl: 'https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?auto=format&fit=crop&w=300&q=70',
            priceRange: { min: 2.9, currency: 'USD', unit: 'piece' },
          },
        ],
        columnMapping: {
          'Product Name (EN)': 'name',
          'MOQ pcs': 'moq',
          'FOB $': 'price_range.min',
          'Material': 'specs.Material',
          'Photo URL': 'image_url',
          'Notes': 'ignore',
        },
        proposedMapping: {
          'Product Name (EN)': 'name',
          'MOQ pcs': 'moq',
          'FOB $': 'price_range.min',
          'Material': 'specs.Material',
          'Photo URL': 'image_url',
          'Notes': 'ignore',
        },
        sourceHeaders: ['Product Name (EN)', 'MOQ pcs', 'FOB $', 'Material', 'Photo URL', 'Notes'],
        sampleRows: [
          { 'Product Name (EN)': 'Runner X1', 'MOQ pcs': '300', 'FOB $': '4.80', 'Material': 'EVA', 'Photo URL': 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=300&q=70', 'Notes': 'popular' },
          { 'Product Name (EN)': 'Trainer Pro 2', 'MOQ pcs': '200', 'FOB $': '5.80', 'Material': 'Mesh + EVA', 'Photo URL': '', 'Notes': '' },
          { 'Product Name (EN)': 'Canvas Low', 'MOQ pcs': '500', 'FOB $': '2.90', 'Material': 'Canvas', 'Photo URL': 'https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?auto=format&fit=crop&w=300&q=70', 'Notes': '' },
        ],
        rowCount: 3,
        fileExt: '.csv',
      } satisfies ProductCatalogDraft
    case 'product_pdf':
      return {
        products: [
          {
            name: 'Hiker HZ-7',
            description: 'Waterproof hiking boot with Vibram-like rubber outsole and reinforced toe cap.',
            specs: { Material: 'Full-grain leather', Outsole: 'Vulcanized rubber', Waterproof: 'Yes', 'Size range': '39-46' },
            imageUrl: 'https://images.unsplash.com/photo-1520639888713-7851133b1ed0?auto=format&fit=crop&w=300&q=70',
            moq: 300,
            priceRange: { min: 7.2, max: 8.5, currency: 'USD', unit: 'pair' },
          },
          {
            name: 'Court Classic',
            description: 'Low-top canvas court shoe, unisex sizing 36–45.',
            specs: { Upper: 'Canvas', Outsole: 'Vulcanized rubber', 'Size range': '36-45' },
            imageUrl: 'https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?auto=format&fit=crop&w=300&q=70',
            moq: 500,
            priceRange: { min: 3.1, max: 3.8, currency: 'USD', unit: 'pair' },
          },
          {
            name: 'Trail Runner Lite',
            description: 'Lightweight trail shoe with breathable mesh upper.',
            specs: { Upper: 'Breathable mesh', 'Drop (mm)': '8' },
            moq: 250,
            priceRange: { min: 5.6, max: 6.5, currency: 'USD', unit: 'pair' },
          },
        ],
      } satisfies ProductCatalogDraft
    case 'certification':
      return {
        certType: 'ISO 9001',
        certNumber: 'CN-9001-2023-04482',
        issuingBody: 'SGS China',
        issueDate: '2023-06-14',
        expiryDate: '2026-06-13',
        notes: 'Scope: manufacture of sports footwear and related components.',
      } satisfies CertificationDraft
  }
}

function classifyByFilename(name: string): 'fail' | 'slow' | 'normal' {
  const n = name.toLowerCase()
  if (n.startsWith('fail')) return 'fail'
  if (n.startsWith('slow')) return 'slow'
  return 'normal'
}

async function mockUpload(file: File, kind: JobKind): Promise<IngestionJob> {
  const classification = classifyByFilename(file.name)
  const delayMs = classification === 'slow' ? 8000 : 2500
  const jobId = makeId()
  const job: IngestionJob = {
    jobId,
    kind,
    status: 'processing',
    sourceUrl: `mock://${kind}/${jobId}/${file.name}`,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
  mockState().set(jobId, {
    job,
    readyAt: Date.now() + delayMs,
    outcome: classification === 'fail' ? 'failed' : 'ready_for_review',
  })
  // Simulate the server round-trip.
  await new Promise((r) => setTimeout(r, 400))
  return { ...job }
}

async function mockGetJob(jobId: string): Promise<IngestionJob> {
  const row = mockState().get(jobId)
  if (!row) throw new Error(`mock ingestion: unknown job ${jobId}`)
  const now = Date.now()
  if (now < row.readyAt) return { ...row.job }

  // Terminal transition — once, then persist.
  if (row.job.status === 'processing') {
    if (row.outcome === 'failed') {
      row.job = {
        ...row.job,
        status: 'failed' as JobStatus,
        error: 'mock extractor failure (filename started with "fail")',
        updatedAt: new Date().toISOString(),
      }
    } else {
      row.job = {
        ...row.job,
        status: 'ready_for_review' as JobStatus,
        draftPayload: mockPayloadFor(row.job.kind),
        updatedAt: new Date().toISOString(),
      }
    }
    mockState().set(jobId, row)
  }
  return { ...row.job }
}

async function mockCommit(jobId: string, _payload: DraftPayload): Promise<{ success: boolean }> {
  const row = mockState().get(jobId)
  if (!row) throw new Error(`mock ingestion: unknown job ${jobId}`)
  row.job = { ...row.job, status: 'committed' as JobStatus, updatedAt: new Date().toISOString() }
  mockState().set(jobId, row)
  return { success: true }
}

async function mockApplyMapping(
  jobId: string,
  mapping: Record<string, string>,
): Promise<{ success: boolean; productCount: number }> {
  const row = mockState().get(jobId)
  if (!row) throw new Error(`mock ingestion: unknown job ${jobId}`)
  // Fake a brief round-trip for the UI.
  await new Promise((r) => setTimeout(r, 400))
  // Synthesize a plausible products list from the mapping + mock sample rows.
  const current = (row.job.draftPayload as ProductCatalogDraft | undefined) ?? {
    products: [],
  }
  const products: ProductCatalogDraft['products'] = [
    {
      name: 'Runner X1',
      moq: 300,
      specs: mapping['Material'] === 'specs.Material' ? { Material: 'EVA' } : {},
      imageUrl: mapping['Photo URL'] === 'image_url'
        ? 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=300&q=70'
        : undefined,
      priceRange: { min: 4.8, currency: 'USD', unit: 'piece' },
    },
    {
      name: 'Trainer Pro 2',
      moq: 200,
      specs: mapping['Material'] === 'specs.Material' ? { Material: 'Mesh + EVA' } : {},
      priceRange: { min: 5.8, currency: 'USD', unit: 'piece' },
    },
    {
      name: 'Canvas Low',
      moq: 500,
      specs: mapping['Material'] === 'specs.Material' ? { Material: 'Canvas' } : {},
      imageUrl: mapping['Photo URL'] === 'image_url'
        ? 'https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?auto=format&fit=crop&w=300&q=70'
        : undefined,
      priceRange: { min: 2.9, currency: 'USD', unit: 'piece' },
    },
  ]
  row.job = {
    ...row.job,
    draftPayload: {
      ...current,
      products,
      columnMapping: mapping,
    } satisfies ProductCatalogDraft,
    updatedAt: new Date().toISOString(),
  }
  mockState().set(jobId, row)
  return { success: true, productCount: products.length }
}

async function mockDiscard(jobId: string): Promise<{ success: boolean }> {
  const row = mockState().get(jobId)
  if (!row) return { success: true }
  row.job = { ...row.job, status: 'discarded' as JobStatus, updatedAt: new Date().toISOString() }
  mockState().set(jobId, row)
  return { success: true }
}

// ===== public surface =====

export const ingestionApi = {
  async upload(file: File, kind: JobKind): Promise<IngestionJob> {
    return isMockEnabled() ? mockUpload(file, kind) : realUpload(file, kind)
  },
  async getJob(jobId: string): Promise<IngestionJob> {
    return isMockEnabled() ? mockGetJob(jobId) : realGetJob(jobId)
  },
  async commit(jobId: string, payload: DraftPayload): Promise<{ success: boolean }> {
    return isMockEnabled() ? mockCommit(jobId, payload) : realCommit(jobId, payload)
  },
  async discard(jobId: string): Promise<{ success: boolean }> {
    return isMockEnabled() ? mockDiscard(jobId) : realDiscard(jobId)
  },
  async applyMapping(
    jobId: string,
    mapping: Record<string, string>,
  ): Promise<{ success: boolean; productCount: number }> {
    return isMockEnabled()
      ? mockApplyMapping(jobId, mapping)
      : realApplyMapping(jobId, mapping)
  },
  /** Exposed for tests / the dev demo page. */
  _isMockEnabled: isMockEnabled,
}
