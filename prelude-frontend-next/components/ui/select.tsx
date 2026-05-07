'use client'

import * as React from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/utils/cn'

interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  children: React.ReactNode
  value?: string
  onValueChange?: (value: string) => void
  size?: 'sm' | 'default' | 'lg'
}

// Enhanced Select implementation using native HTML select with modern styling
function Select({
  children,
  value,
  onValueChange,
  className,
  size = 'default',
  ...props
}: SelectProps) {
  const sizeClasses = {
    sm: 'h-8 px-2 py-1 text-xs pr-6',
    default: 'h-9 px-3 py-2 text-sm pr-8',
    lg: 'h-10 px-4 py-2 text-base pr-10',
  }

  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onValueChange?.(e.target.value)}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border border-rule bg-bone text-ink shadow-sm transition-all duration-200',
          'hover:border-mute hover:bg-cream',
          'focus:border-accent focus:outline-none',
          'disabled:cursor-not-allowed disabled:bg-paper disabled:opacity-50',
          'cursor-pointer appearance-none',
          sizeClasses[size],
          className
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className={cn(
          'pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 transform opacity-50 transition-transform duration-200',
          size === 'sm' ? 'h-3 w-3' : size === 'lg' ? 'h-5 w-5' : 'h-4 w-4'
        )}
      />
    </div>
  )
}

interface SelectContentProps {
  children: React.ReactNode
}

function SelectContent({ children, ...props }: SelectContentProps) {
  return <>{children}</>
}

interface SelectItemProps extends React.OptionHTMLAttributes<HTMLOptionElement> {
  children: React.ReactNode
  value: string
}

function SelectItem({ children, value, ...props }: SelectItemProps) {
  return (
    <option value={value} {...props}>
      {children}
    </option>
  )
}

export { Select, SelectItem }
