'use client'

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { HelpCircle, Info } from 'lucide-react'

interface TooltipProps {
  children: React.ReactNode
  content: React.ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  type?: 'info' | 'help'
  maxWidth?: string
  showIcon?: boolean
  iconSize?: string
}

const Tooltip: React.FC<TooltipProps> = ({
  children,
  content,
  position = 'top',
  type = 'info',
  maxWidth = '250px',
  showIcon = true,
  iconSize = 'w-4 h-4',
}) => {
  const [isVisible, setIsVisible] = useState(false)

  const getPositionClasses = () => {
    switch (position) {
      case 'bottom':
        return 'top-full left-1/2 transform -translate-x-1/2 mt-2'
      case 'left':
        return 'right-full top-1/2 transform -translate-y-1/2 mr-2'
      case 'right':
        return 'left-full top-1/2 transform -translate-y-1/2 ml-2'
      default: // top
        return 'bottom-full left-1/2 transform -translate-x-1/2 mb-2'
    }
  }

  const getArrowClasses = () => {
    switch (position) {
      case 'bottom':
        return 'bottom-full left-1/2 transform -translate-x-1/2 border-l-transparent border-r-transparent border-b-deep'
      case 'left':
        return 'left-full top-1/2 transform -translate-y-1/2 border-t-transparent border-b-transparent border-l-deep'
      case 'right':
        return 'right-full top-1/2 transform -translate-y-1/2 border-t-transparent border-b-transparent border-r-deep'
      default: // top
        return 'top-full left-1/2 transform -translate-x-1/2 border-l-transparent border-r-transparent border-t-deep'
    }
  }

  const IconComponent = type === 'help' ? HelpCircle : Info

  return (
    <div className="relative inline-flex items-center">
      <div
        className="flex cursor-help items-center gap-1"
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        onFocus={() => setIsVisible(true)}
        onBlur={() => setIsVisible(false)}
        tabIndex={0}
      >
        {children}
        {showIcon && (
          <IconComponent
            className={`${iconSize} text-mute transition-colors hover:text-ink`}
          />
        )}
      </div>

      <AnimatePresence>
        {isVisible && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className={`absolute z-50 ${getPositionClasses()}`}
            style={{ maxWidth }}
          >
            {/* Tooltip Content */}
            <div className="rounded-lg bg-deep px-3 py-2 text-sm text-bone shadow-lg">
              {content}
            </div>

            {/* Tooltip Arrow */}
            <div className={`absolute h-0 w-0 border-4 ${getArrowClasses()}`} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// Specialized component for technical term explanations
interface TechTermTooltipProps {
  term: string
  explanation: string
  example?: string | null
  position?: 'top' | 'bottom' | 'left' | 'right'
}

const TechTermTooltip: React.FC<TechTermTooltipProps> = ({
  term,
  explanation,
  example = null,
  position = 'top',
}) => {
  const content = (
    <div>
      <div className="mb-1 font-medium">{term}</div>
      <div className="mb-2 text-bone/80">{explanation}</div>
      {example && (
        <div className="border-t border-bone/30 pt-2 text-xs text-bone/70">
          <strong>Example:</strong> {example}
        </div>
      )}
    </div>
  )

  return (
    <Tooltip content={content} position={position} type="help" maxWidth="300px">
      <span className="cursor-help border-b border-dashed border-mute">{term}</span>
    </Tooltip>
  )
}

export { Tooltip }
export default Tooltip
