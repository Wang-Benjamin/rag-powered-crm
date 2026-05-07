'use client'

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/hooks/useAuth'
import type { Workspace, WorkspaceContextType, WorkspaceProviderProps } from '@/types/common'

const WorkspaceContext = createContext<WorkspaceContextType | null>(null)

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (!context) {
    throw new Error('useWorkspace must be used within WorkspaceProvider')
  }
  return context
}

export function WorkspaceProvider({ children, workspaceId }: WorkspaceProviderProps) {
  const { user } = useAuth()
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [availableWorkspaces, setAvailableWorkspaces] = useState<Workspace[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const loadWorkspace = useCallback(async () => {
    if (!user || !workspaceId) {
      setIsLoading(false)
      return
    }

    try {
      setIsLoading(true)

      // For now, create a mock workspace based on user email
      // In production, this would fetch from your backend
      const userEmail = user.email || (user as any).userEmail
      const mockWorkspace: Workspace = {
        id: workspaceId,
        name: `${userEmail}'s Workspace`,
        type: 'personal',
        ownerId: userEmail,
        createdAt: new Date(),
      }

      setWorkspace(mockWorkspace)

      // Mock available workspaces
      setAvailableWorkspaces([mockWorkspace])
    } catch (error) {
      console.error('Error loading workspace:', error)
    } finally {
      setIsLoading(false)
    }
  }, [user, workspaceId])

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

  const switchWorkspace = useCallback((newWorkspaceId: string) => {
    // Navigate to the new workspace
    window.location.href = `/workspace/${newWorkspaceId}/dashboard`
  }, [])

  const refreshWorkspaces = useCallback(async () => {
    await loadWorkspace()
  }, [loadWorkspace])

  const value: WorkspaceContextType = {
    workspaceId,
    workspace,
    isLoading,
    switchWorkspace,
    availableWorkspaces,
    refreshWorkspaces,
  }

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}
