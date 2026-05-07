'use client'

import { useState, useEffect } from 'react'
import { settingsApiClient } from '@/lib/api/client'

export interface ProductEntry {
  name: string
  fobPrice: string
  landedPrice: string
}

interface FactoryDefaults {
  moq: string
  leadTime: string
  certifications: string[]
  products: ProductEntry[]
}

const EMPTY_DEFAULTS: FactoryDefaults = {
  moq: '',
  leadTime: '',
  certifications: [],
  products: [],
}

/**
 * Fetches factory profile defaults for pre-populating trade email fields.
 * Only fetches when enabled (i.e., user is a trade user with zh locale).
 */
export function useFactoryProfile(enabled: boolean): FactoryDefaults {
  const [defaults, setDefaults] = useState<FactoryDefaults>(EMPTY_DEFAULTS)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false

    async function fetchDefaults() {
      try {
        const [profileRes, certsRes] = await Promise.all([
          settingsApiClient.get<{
            companyProfile?: Record<string, any>
            factoryDetails?: Record<string, any>
          }>('/factory-profile'),
          settingsApiClient.get<{
            certifications?: Array<{ certType?: string }>
          }>('/certifications'),
        ])

        if (cancelled) return

        const factoryDetails = profileRes?.factoryDetails || {}
        const certs = certsRes?.certifications || []

        // Parse products array from factory_details
        const rawProducts = factoryDetails.products || []
        const products: ProductEntry[] = (Array.isArray(rawProducts) ? rawProducts : [])
          .filter((p: any) => p?.name || p?.fobPrice || p?.landedPrice)
          .map((p: any) => ({
            name: p.name || '',
            fobPrice: p.fobPrice || p.fob_price || '',
            landedPrice: p.landedPrice || p.landed_price || '',
          }))

        setDefaults({
          moq: factoryDetails.moq ? String(factoryDetails.moq) : '',
          leadTime: factoryDetails.leadTime || factoryDetails.lead_time || '',
          products,
          certifications: certs.map((c) => c.certType).filter((name): name is string => !!name),
        })
      } catch (err) {
        // Factory profile not set up yet — use empty defaults
        if (!cancelled) setDefaults(EMPTY_DEFAULTS)
      }
    }

    fetchDefaults()
    return () => {
      cancelled = true
    }
  }, [enabled])

  return defaults
}
