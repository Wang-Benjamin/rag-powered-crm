'use client'

import { useTranslations } from 'next-intl'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { productCatalogApi, type ProductCatalogInput } from '@/lib/api/productCatalog'
import { PendingProductsHeader } from './PendingProductsHeader'
import { ProductEditDialog } from './ProductEditDialog'
import { StorefrontCatalog } from './StorefrontCatalog'
import { StorefrontDraftView } from './StorefrontDraftView'
import type { Product, StorefrontView } from './types'

const STORAGE_KEY = 'storefront_page'

export function StorefrontClient() {
  const t = useTranslations('storefront')
  const [view, setView] = useState<StorefrontView>('draft')
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [leavingIds, setLeavingIds] = useState<Set<string>>(new Set())
  const [enteringIds, setEnteringIds] = useState<Set<string>>(new Set())

  // Manual-add / per-row edit modal state. `editing` is the row being
  // edited; `null` + `dialogOpen=true` means manual-add ('create').
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Product | null>(null)

  const refetch = useCallback(async () => {
    try {
      const list = await productCatalogApi.list()
      setProducts(list)
    } catch (err) {
      console.error('product-catalog: list failed', err)
      toast.error(t('catalogToasts.fetchFailed'))
    }
  }, [t])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    productCatalogApi
      .list()
      .then((list) => {
        if (cancelled) return
        setProducts(list)
      })
      .catch((err) => {
        if (cancelled) return
        console.error('product-catalog: list failed', err)
        toast.error(t('catalogToasts.fetchFailed'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [t])

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved === 'draft' || saved === 'pending' || saved === 'live') setView(saved)
    } catch {}
  }, [])

  const switchView = (next: StorefrontView) => {
    setView(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {}
  }

  const pending = useMemo(() => products.filter((p) => p.status === 'pending'), [products])
  const live = useMemo(() => products.filter((p) => p.status === 'live'), [products])

  // Stagger the per-id leave → swap → enter animation, exactly like before.
  // The only change is that the swap step is now a real backend call rather
  // than an in-memory mutation. We optimistically apply the post-publish
  // shape so the user sees 已上线 immediately; if the network call fails the
  // toast surfaces it and we refetch to reconcile.
  const publish = useCallback(
    async (ids: string[]) => {
      if (ids.length === 0) return
      setLeavingIds(new Set(ids))

      let serverProducts: Product[] = []
      try {
        serverProducts = await productCatalogApi.publishBulk(ids)
      } catch (err) {
        console.error('product-catalog: publish failed', err)
        toast.error(t('catalogToasts.publishFailed'))
        setLeavingIds(new Set())
        await refetch()
        return
      }

      const byId = new Map(serverProducts.map((p) => [p.productId, p]))
      ids.forEach((id, i) => {
        setTimeout(() => {
          setProducts((prev) =>
            prev.map((p) => {
              if (p.productId !== id) return p
              const updated = byId.get(id)
              return updated ?? { ...p, status: 'live' as const, publishedAt: new Date().toISOString() }
            }),
          )
          setLeavingIds((prev) => {
            const n = new Set(prev)
            n.delete(id)
            return n
          })
          setEnteringIds((prev) => new Set(prev).add(id))
          setTimeout(() => {
            setEnteringIds((prev) => {
              const n = new Set(prev)
              n.delete(id)
              return n
            })
          }, 320)
        }, 260 + i * 60)
      })
    },
    [refetch, t],
  )

  const openManualAdd = useCallback(() => {
    setEditing(null)
    setDialogOpen(true)
  }, [])

  const openEdit = useCallback((product: Product) => {
    setEditing(product)
    setDialogOpen(true)
  }, [])

  const handleDialogSubmit = useCallback(
    async (input: ProductCatalogInput) => {
      if (editing && editing.productId) {
        const updated = await productCatalogApi.update(editing.productId, input)
        setProducts((prev) =>
          prev.map((p) => (p.productId === updated.productId ? updated : p)),
        )
        toast.success(t('catalogToasts.updated'))
      } else {
        const created = await productCatalogApi.create(input)
        setProducts((prev) => [created, ...prev])
        toast.success(t('catalogToasts.created'))
      }
    },
    [editing, t],
  )

  const handleDialogDelete = useCallback(
    async (product: Product) => {
      if (!product.productId) return
      const targetId = product.productId
      try {
        await productCatalogApi.remove(targetId)
        setProducts((prev) => prev.filter((p) => p.productId !== targetId))
        toast.success(t('catalogToasts.deleted'))
      } catch (err) {
        console.error('product-catalog: delete failed', err)
        toast.error(t('catalogToasts.deleteFailed'))
        throw err
      }
    },
    [t],
  )

  const counts = { pending: pending.length, live: live.length }

  return (
    <div className="h-full overflow-y-auto bg-bone">
      <div className="mx-auto max-w-[960px] px-6 py-10">
        {/* Page head */}
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="mb-1 font-display text-3xl text-deep">
              {t('page.title')}
            </h1>
            <div className="max-w-xl text-sm text-mute">{t('page.subtitle')}</div>
          </div>
          <div
            role="tablist"
            aria-label={t('page.title')}
            className="inline-flex rounded-full border border-rule bg-paper p-0.5"
          >
            {(['draft', 'pending', 'live'] as const).map((key) => {
              const on = view === key
              const badge = key !== 'draft' ? counts[key] : null
              return (
                <button
                  key={key}
                  role="tab"
                  aria-selected={on}
                  onClick={() => switchView(key)}
                  className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                    on ? 'bg-deep text-bone shadow-sm' : 'text-mute hover:text-deep'
                  }`}
                >
                  <span>{t(`states.${key}`)}</span>
                  {badge !== null && (
                    <span
                      className={`text-xs ${on ? 'text-bone/70' : 'text-mute'}`}
                    >
                      {badge}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* Active view */}
        {view === 'draft' && <StorefrontDraftView />}
        {view === 'pending' && (
          <>
            <PendingProductsHeader
              onAddManual={openManualAdd}
              onCommitted={() => {
                toast.success(t('catalogToasts.imported'))
                void refetch()
              }}
            />
            <StorefrontCatalog
              status="pending"
              products={pending}
              onPublish={publish}
              onEditProduct={openEdit}
              leavingIds={leavingIds}
              enteringIds={enteringIds}
            />
          </>
        )}
        {view === 'live' && (
          <StorefrontCatalog
            status="live"
            products={live}
            onPublish={() => {}}
            leavingIds={leavingIds}
            enteringIds={enteringIds}
          />
        )}

        <ProductEditDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          mode={editing ? 'edit' : 'create'}
          initial={editing}
          onSubmit={handleDialogSubmit}
          onDelete={handleDialogDelete}
        />

        {loading && view !== 'draft' && (
          <div className="text-center text-xs text-mute">{t('catalogToasts.loading')}</div>
        )}
      </div>
    </div>
  )
}
