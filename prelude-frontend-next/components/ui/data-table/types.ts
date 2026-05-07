import { Row } from '@tanstack/react-table'
import React from 'react'

export interface FieldConfig {
  type: 'text' | 'email' | 'tel' | 'textarea' | 'currency' | 'date' | 'select' | 'number'
  label: string
  icon?: React.ComponentType<any>
  required?: boolean
  readonly?: boolean
  validation?: (value: any) => string | null
  options?: Array<{ value: string | number; label: string }>
  renderDisplay?: (value: any) => React.ReactNode
}

export interface DataTableColumnMeta {
  fieldConfig?: FieldConfig
  headerClassName?: string
  cellClassName?: string
}

export interface DataTableMeta<TData> {
  updateData: (row: Row<TData>, columnId: string, value: any) => Promise<void>
  onSaveSuccess?: (columnId: string) => void
  onSaveError?: (columnId: string, error: Error) => void
}
