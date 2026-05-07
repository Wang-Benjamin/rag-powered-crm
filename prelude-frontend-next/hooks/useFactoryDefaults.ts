'use client'

import { useState, useEffect } from 'react'
import { useFactoryProfile, type ProductEntry } from './useFactoryProfile'

/**
 * Shared hook that fetches factory profile and manages trade-field state.
 * Used by all email composers (CRM + Lead Gen, single + mass).
 */
export function useFactoryDefaults() {
  const factoryDefaults = useFactoryProfile(true)

  const [products, setProducts] = useState<ProductEntry[]>([
    { name: '', fobPrice: '', landedPrice: '' },
  ])
  const [tradeCerts, setTradeCerts] = useState<string[]>([])
  const [moq, setMoq] = useState('')
  const [leadTime, setLeadTime] = useState('')
  const [sampleStatus, setSampleStatus] = useState<'ready' | 'in_production' | 'free_sample' | ''>('')

  const [defaultsApplied, setDefaultsApplied] = useState(false)
  useEffect(() => {
    if (defaultsApplied) return
    if (!factoryDefaults.products.length && factoryDefaults.certifications.length === 0) return
    if (factoryDefaults.products.length) setProducts(factoryDefaults.products)
    setTradeCerts(factoryDefaults.certifications)
    if (factoryDefaults.moq) setMoq(factoryDefaults.moq)
    if (factoryDefaults.leadTime) setLeadTime(factoryDefaults.leadTime)
    setDefaultsApplied(true)
  }, [defaultsApplied, factoryDefaults])

  return {
    products,
    setProducts,
    tradeCerts,
    setTradeCerts,
    moq,
    setMoq,
    leadTime,
    setLeadTime,
    sampleStatus,
    setSampleStatus,
  }
}
