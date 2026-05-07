'use client'

import * as React from 'react'
import { cn } from '@/utils/cn'
import { Button } from './button'

interface AlertDialogProps {
  children: React.ReactNode
  open: boolean
  onOpenChange: (open: boolean) => void
}

// Simple modal implementation without Radix UI
const AlertDialog: React.FC<AlertDialogProps> = ({ children, open, onOpenChange }) => {
  // Only render content when modal is open
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="fixed inset-0 bg-[oklch(0.180_0.020_265/0.45)] backdrop-blur-sm"
        onClick={() => onOpenChange?.(false)}
      />
      <div className="relative z-50 mx-4 w-full max-w-lg">
        {React.Children.toArray(children).find(
          (child: any) => child?.type?.displayName === 'AlertDialogContent'
        )}
      </div>
    </div>
  )
}

interface AlertDialogTriggerProps extends React.HTMLAttributes<HTMLElement> {
  children: React.ReactElement
  onClick?: (e: React.MouseEvent) => void
}

const AlertDialogTrigger: React.FC<AlertDialogTriggerProps> = ({ children, onClick, ...props }) =>
  React.cloneElement(children, {
    onClick: (e: React.MouseEvent) => {
      onClick?.(e)
      ;(children.props as any).onClick?.(e)
    },
    ...props,
  } as any)

const AlertDialogContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'grid w-full gap-4 rounded-lg border border-border bg-background p-6 shadow-lg',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
)
AlertDialogContent.displayName = 'AlertDialogContent'

const AlertDialogHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex flex-col space-y-2 text-center sm:text-left', className)}
      {...props}
    />
  )
)
AlertDialogHeader.displayName = 'AlertDialogHeader'

const AlertDialogFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2', className)}
      {...props}
    />
  )
)
AlertDialogFooter.displayName = 'AlertDialogFooter'

const AlertDialogTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h2 ref={ref} className={cn(className)} {...props} />
))
AlertDialogTitle.displayName = 'AlertDialogTitle'

const AlertDialogDescription = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('font-body text-sm text-muted-foreground', className)} {...props} />
))
AlertDialogDescription.displayName = 'AlertDialogDescription'

interface AlertDialogActionProps extends React.ComponentProps<typeof Button> {}

const AlertDialogAction: React.FC<AlertDialogActionProps> = ({ className, ...props }) => (
  <Button className={className} {...props} />
)
AlertDialogAction.displayName = 'AlertDialogAction'

interface AlertDialogCancelProps extends React.ComponentProps<typeof Button> {}

const AlertDialogCancel: React.FC<AlertDialogCancelProps> = ({ className, ...props }) => (
  <Button variant="outline" className={cn('mt-2 sm:mt-0', className)} {...props} />
)
AlertDialogCancel.displayName = 'AlertDialogCancel'

// Set display names for component identification
AlertDialogContent.displayName = 'AlertDialogContent'

export {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
}
