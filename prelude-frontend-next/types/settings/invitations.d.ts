/**
 * Invitation Type Definitions
 * Types for team invitation management
 */

import type { UserProfile, TeamInvitation } from './profile'

/**
 * Invitation data for creating/updating invitations
 * Note: databaseName is optional - database routing is handled automatically via JWT per CLAUDE.md
 */
export interface InvitationData {
  email: string
  company: string
  role: string
  databaseName?: string
}

/**
 * User invitations response from API
 */
export interface UserInvitationsResponse {
  user: UserProfile | null
  invitations: TeamInvitation[]
}
