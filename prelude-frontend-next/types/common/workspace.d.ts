/**
 * Workspace Type Definitions
 * Types for workspace management
 */

/**
 * Workspace entity
 */
export interface Workspace {
  id: string
  name: string
  type: 'personal' | 'team'
  ownerId: string
  members?: string[]
  createdAt: Date
}

/**
 * Workspace Context Type - provided by WorkspaceProvider
 * Used by useWorkspace hook consumers
 */
export interface WorkspaceContextType {
  workspaceId: string
  workspace: Workspace | null
  isLoading: boolean
  switchWorkspace: (newWorkspaceId: string) => void
  availableWorkspaces: Workspace[]
  refreshWorkspaces: () => Promise<void>
}

/**
 * Workspace Provider Props
 */
export interface WorkspaceProviderProps {
  children: React.ReactNode
  workspaceId: string
}
