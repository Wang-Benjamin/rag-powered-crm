/**
 * User Profile and Team Invitation Types
 * User account and team management type definitions
 */

export type InvitationStatus = 'pending' | 'accepted' | 'declined' | 'expired'

export type OnboardingStatus = 'not_started' | 'in_progress' | 'completed' | 'skipped'

export interface OnboardingProgress {
  stepsCompleted?: string[]
  skippedSteps?: string[]
  companyDataExists?: boolean
}

export interface UserProfile {
  email: string
  name?: string
  company?: string
  role?: string
  databaseName?: string
  isActive?: boolean
  lastLogin?: Date | string
  createdAt?: Date | string
  updatedAt?: Date | string
  onboardingStatus?: OnboardingStatus
  onboardingStep?: number
  onboardingProgress?: OnboardingProgress
  onboardingCompletedAt?: string
}

export interface TeamInvitation {
  id?: string
  email: string
  company: string
  role: string
  databaseName?: string
  status: InvitationStatus
  invitedBy?: string
  invitedAt?: Date | string
  expiresAt?: Date | string
  acceptedAt?: Date | string
}
