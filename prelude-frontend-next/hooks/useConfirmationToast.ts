'use client'

import { useState, useCallback } from 'react'

export interface ConfirmationToastOptions {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'default' | 'destructive' | 'warning'
  itemName?: string
  itemCount?: number
  onConfirm: () => void | Promise<void>
  onCancel?: () => void
}

export function useConfirmationToast() {
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [options, setOptions] = useState<ConfirmationToastOptions | null>(null)

  const confirm = useCallback((opts: ConfirmationToastOptions) => {
    setOptions(opts)
    setIsOpen(true)
  }, [])

  const handleConfirm = useCallback(async () => {
    if (!options) return

    setIsLoading(true)
    try {
      await options.onConfirm()
      setIsOpen(false)
      setOptions(null)
    } catch (error) {
      console.error('Confirmation action failed:', error)
      // Keep toast open on error so user is aware the action failed
    } finally {
      setIsLoading(false)
    }
  }, [options])

  const handleCancel = useCallback(() => {
    options?.onCancel?.()
    setIsOpen(false)
    setOptions(null)
  }, [options])

  const close = useCallback(() => {
    setIsOpen(false)
    setOptions(null)
  }, [])

  return {
    confirm,
    close,
    toastProps: {
      isOpen,
      isLoading,
      onConfirm: handleConfirm,
      onCancel: handleCancel,
      title: options?.title ?? '',
      description: options?.description,
      confirmLabel: options?.confirmLabel,
      cancelLabel: options?.cancelLabel,
      variant: options?.variant,
      itemName: options?.itemName,
      itemCount: options?.itemCount,
    },
  }
}

