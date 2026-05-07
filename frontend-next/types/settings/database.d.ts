/**
 * Database Management Types
 * Database status and table management type definitions
 */

export interface DatabaseStatus {
  connected: boolean
  databaseName: string
  totalTables: number
  completedTables: number
  missingTables: string[]
  progress: number
}

export interface DatabaseTable {
  name: string
  exists: boolean
  rowCount: number
  required: boolean
  description: string
}

export interface TableContent {
  tableName: string
  columns: string[]
  rows: Record<string, any>[]
  totalRows: number
  sampleSize: number
}
