'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent } from '@/components/ui/card'
import { Tooltip } from '@/components/ui/tooltip'
import { ArrowUp, ArrowDown, Minus } from 'lucide-react'
import type { ThreatLevel } from '@/types/leads/bol'

const THREAT_VARIANT: Record<ThreatLevel, 'danger' | 'warning' | 'neutral' | 'secondary'> = {
  HIGH: 'danger',
  GROWING: 'warning',
  DECLINING: 'secondary',
  MODERATE: 'neutral',
  LOW: 'secondary',
}

export const THREAT_DESCRIPTION_KEYS = {
  HIGH: 'bol.competitors.threatHigh',
  GROWING: 'bol.competitors.threatGrowing',
  DECLINING: 'bol.competitors.threatDeclining',
  MODERATE: 'bol.competitors.threatModerate',
  LOW: 'bol.competitors.threatLow',
} as const satisfies Record<ThreatLevel, string>

export const THREAT_LEVEL_KEYS = {
  HIGH: 'bol.competitors.threatLevelHigh',
  GROWING: 'bol.competitors.threatLevelGrowing',
  DECLINING: 'bol.competitors.threatLevelDeclining',
  MODERATE: 'bol.competitors.threatLevelModerate',
  LOW: 'bol.competitors.threatLevelLow',
} as const satisfies Record<ThreatLevel, string>

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 text-xs font-medium tracking-wider text-zinc-500 uppercase dark:text-zinc-400">
      {children}
    </h3>
  )
}

function TrendValue({ value }: { value: number | null | undefined }) {
  const t = useTranslations('leads')
  if (value == null) {
    return <span className="text-zinc-400">{'\u2014'}</span>
  }
  if (value > 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-green-600 dark:text-green-400">
        <ArrowUp className="h-3.5 w-3.5" />
        {t('bol.competitorDrawer.trendUp', { value })}
      </span>
    )
  }
  if (value < 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-red-600 dark:text-red-400">
        <ArrowDown className="h-3.5 w-3.5" />
        {t('bol.competitorDrawer.trendDown', { value })}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-zinc-400">
      <Minus className="h-3.5 w-3.5" />
      {t('bol.competitorDrawer.trendFlat')}
    </span>
  )
}

function MetricCard({
  label,
  children,
  tooltip,
}: {
  label: string
  children: React.ReactNode
  tooltip?: string
}) {
  return (
    <Card>
      <CardContent className="px-3 py-2.5">
        <div className="mb-1 flex items-center gap-1">
          {tooltip ? (
            <Tooltip content={tooltip} position="top" showIcon={true} iconSize="w-3 h-3">
              <p className="text-[10px] font-semibold tracking-wide text-muted-foreground uppercase">{label}</p>
            </Tooltip>
          ) : (
            <p className="text-[10px] font-semibold tracking-wide text-muted-foreground uppercase">{label}</p>
          )}
        </div>
        <div className="text-xl font-bold leading-tight tabular-nums">
          {children ?? '\u2014'}
        </div>
      </CardContent>
    </Card>
  )
}
