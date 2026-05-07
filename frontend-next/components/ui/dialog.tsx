'use client'

import * as React from 'react'
import { cn } from '@/utils/cn'
import { X } from 'lucide-react'

// Context for Dialog state management
interface DialogContextType {
  onOpenChange?: (open: boolean) => void
}

const DialogContext = React.createContext<DialogContextType | undefined>(undefined)

interface DialogProps {
  children: React.ReactNode
  open: boolean
  onOpenChange?: (open: boolean) => void
}

// Simple modal implementation without Radix UI
function Dialog({ children, open, onOpenChange }: DialogProps) {
  // Only render content when modal is open
  if (!open) return null

  return (
    <DialogContext.Provider value={{ onOpenChange }}>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm"
          onClick={() => onOpenChange?.(false)}
        />
        {React.Children.toArray(children).find(
          (child: any) => child?.type?.displayName === 'DialogContent'
        )}
      </div>
    </DialogContext.Provider>
  )
}

interface DialogTriggerProps extends React.HTMLAttributes<HTMLElement> {
  children: React.ReactElement
  onClick?: (e: React.MouseEvent) => void
}

function DialogTrigger({ children, onClick, ...props }: DialogTriggerProps) {
  return React.cloneElement(children, {
    onClick: (e: React.MouseEvent) => {
      onClick?.(e)
      ;(children.props as any).onClick?.(e)
    },
    ...props,
  } as any)
}

interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  onClose?: () => void
  isClosing?: boolean
}

const DialogContent = React.forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, children, onClose, ...props }, ref) => {
    const context = React.useContext(DialogContext)

    const handleClose = () => {
      // Call parent Dialog's onOpenChange for proper state management
      context?.onOpenChange?.(false)
      // Keep onClose for backward compatibility
      onClose?.()
    }

    return (
      <div
        ref={ref}
        className={cn(
          'dialog-scrollbar relative grid w-full gap-4 rounded-lg border border-rule bg-bone p-6 shadow-lg',
          className
        )}
        {...props}
      >
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 rounded-sm opacity-70 transition-opacity outline-none hover:opacity-100 focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none"
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Close</span>
        </button>
        {children}
      </div>
    )
  }
)

const DialogHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex flex-col space-y-1.5 text-center sm:text-left', className)}
      {...props}
    />
  )
)
DialogHeader.displayName = 'DialogHeader'

const DialogFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2', className)}
      {...props}
    />
  )
)
DialogFooter.displayName = 'DialogFooter'

const DialogTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => <h2 ref={ref} className={cn(className)} {...props} />
)
DialogTitle.displayName = 'DialogTitle'

const DialogDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p ref={ref} className={cn('text-sm text-muted-foreground', className)} {...props} />
))
DialogDescription.displayName = 'DialogDescription'

// Set display names for component identification
DialogContent.displayName = 'DialogContent'

export {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
}
