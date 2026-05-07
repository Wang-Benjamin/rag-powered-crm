/**
 * Product catalog API client.
 *
 * Thin wrapper over `settingsApiClient` for the `/product-catalog/*` routes
 * that back the storefront 待上线 / 已上线 tabs. The shape mirrors what the
 * backend stores in the `product_catalog` table — distinct from the
 * wizard's flat `factory_details.products` (which still drives the
 * mass-email composer defaults via `useFactoryProfile`).
 */

import { settingsApiClient } from './client'
import type { PriceRange } from '@/components/onboarding/customize-ai/ingestion/types'

export type ProductCatalogStatus = 'pending' | 'live'

export interface ProductCatalogItem {
  productId: string
  name: string
  description?: string | null
  specs: Record<string, string>
  imageUrl?: string | null
  moq?: number | null
  priceRange?: PriceRange | null
  hsCode?: string | null
  sourceJobId?: string | null
  status: ProductCatalogStatus
  publishedAt?: string | null
  createdAt: string
  updatedAt: string
}

/** Fields the user can write directly (manual add / edit). */
export interface ProductCatalogInput {
  name: string
  description?: string | null
  specs?: Record<string, string>
  imageUrl?: string | null
  moq?: number | null
  priceRange?: PriceRange | null
  hsCode?: string | null
}

interface ListResponse {
  success: boolean
  products: ProductCatalogItem[]
}

interface ItemResponse {
  success: boolean
  product: ProductCatalogItem
}

interface BulkPublishResponse {
  success: boolean
  publishedCount: number
  products: ProductCatalogItem[]
}

export const productCatalogApi = {
  async list(status?: ProductCatalogStatus): Promise<ProductCatalogItem[]> {
    const res = await settingsApiClient.get<ListResponse>(
      '/product-catalog',
      status ? { status } : undefined,
    )
    return res.products ?? []
  },

  async create(input: ProductCatalogInput): Promise<ProductCatalogItem> {
    const res = await settingsApiClient.post<ItemResponse>('/product-catalog', input)
    return res.product
  },

  async update(
    productId: string,
    patch: Partial<ProductCatalogInput>,
  ): Promise<ProductCatalogItem> {
    const res = await settingsApiClient.patch<ItemResponse>(
      `/product-catalog/${productId}`,
      patch,
    )
    return res.product
  },

  async remove(productId: string): Promise<void> {
    await settingsApiClient.delete(`/product-catalog/${productId}`)
  },

  async publish(productId: string): Promise<ProductCatalogItem> {
    const res = await settingsApiClient.post<ItemResponse>(
      `/product-catalog/${productId}/publish`,
    )
    return res.product
  },

  async publishBulk(productIds: string[]): Promise<ProductCatalogItem[]> {
    if (productIds.length === 0) return []
    const res = await settingsApiClient.post<BulkPublishResponse>(
      '/product-catalog/publish-bulk',
      { productIds },
    )
    return res.products ?? []
  },
}
