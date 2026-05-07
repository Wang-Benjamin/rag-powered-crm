'use client'

import React, { useState } from 'react'
import { Star } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { cn } from '@/utils/cn'

interface StarRatingProps {
  rating: number
  onRatingChange?: (rating: number) => void
  readonly?: boolean
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

const sizeClasses = {
  sm: 'w-4 h-4',
  md: 'w-5 h-5',
  lg: 'w-6 h-6',
}

export function StarRating({
  rating,
  onRatingChange,
  readonly = false,
  size = 'md',
  showLabel = false,
}: StarRatingProps) {
  const t = useTranslations('crm')
  const [hoveredStar, setHoveredStar] = useState<number>(0)

  const handleClick = (starIndex: number) => {
    if (!readonly && onRatingChange) {
      onRatingChange(starIndex)
    }
  }

  const handleMouseEnter = (starIndex: number) => {
    if (!readonly) {
      setHoveredStar(starIndex)
    }
  }

  const handleMouseLeave = () => {
    if (!readonly) {
      setHoveredStar(0)
    }
  }

  const displayRating = hoveredStar || rating

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((starIndex) => (
          <button
            key={starIndex}
            type="button"
            onClick={() => handleClick(starIndex)}
            onMouseEnter={() => handleMouseEnter(starIndex)}
            onMouseLeave={handleMouseLeave}
            disabled={readonly}
            className={cn(
              'transition-all duration-150',
              !readonly && 'cursor-pointer hover:scale-110',
              readonly && 'cursor-default'
            )}
            aria-label={t('starRating.rateStar', { count: starIndex })}
          >
            <Star
              className={cn(
                sizeClasses[size],
                'transition-colors duration-150',
                starIndex <= displayRating
                  ? 'fill-yellow-400 text-yellow-400'
                  : 'fill-none text-zinc-300'
              )}
            />
          </button>
        ))}
      </div>
      {showLabel && rating > 0 && (
        <span className="text-sm text-zinc-600">
          {t('starRating.labelStar', { count: rating })}
        </span>
      )}
    </div>
  )
}
