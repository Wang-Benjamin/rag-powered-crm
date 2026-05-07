'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useRouter } from '@/i18n/navigation'
import { useSearchParams, useParams } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { invitationsApi } from '@/lib/api/invitationsApi'
import PlatformTutorial from '@/components/onboarding/tutorial/PlatformTutorial'
import TutorialSelector from '@/components/onboarding/tutorial/TutorialSelector'
import { CustomizeAIQuestionnaire } from '@/components/onboarding/customize-ai/CustomizeAIQuestionnaire'
import {
  Users,
  UserPlus,
  Mail,
  Building2,
  Shield,
  AlertCircle,
  Loader2,
  RefreshCw,
  CheckCircle,
  BookOpen,
  PlayCircle,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { useTranslations } from 'next-intl'

export default function UserOnboardingPage() {
  const { user } = useAuth()
  const t = useTranslations('settings')
  const params = useParams()
  const router = useRouter()
  const workspaceId = (params?.workspaceId as string) || ''
  const searchParams = useSearchParams()

  // Get initial tab from URL params or default to 'team-organization'
  const initialTab = searchParams?.get('tab') || 'team-organization'
  const [activeTab, setActiveTab] = useState(initialTab)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [invitations, setInvitations] = useState<any[]>([])
  const [userNotFound, setUserNotFound] = useState(false)
  const [savedOnboardingStep, setSavedOnboardingStep] = useState(0)
  const [savedOnboardingStatus, setSavedOnboardingStatus] = useState<string | undefined>(undefined)
  const [formData, setFormData] = useState({
    email: '',
    role: 'viewer',
  })
  const [submitting, setSubmitting] = useState(false)
  const [memberToDelete, setMemberToDelete] = useState<any>(null)
  const [showRemoveModal, setShowRemoveModal] = useState(false)
  const [isRemoving, setIsRemoving] = useState(false)

  // Tutorial state
  const [tutorialSelectorOpen, setTutorialSelectorOpen] = useState(false)
  const [tutorialOpen, setTutorialOpen] = useState(false)
  const [selectedTutorial, setSelectedTutorial] = useState('dashboard')

  // Role options with descriptions
  const roleOptions = useMemo(
    () => [
      {
        value: 'admin',
        label: t('onboarding.roleAdmin'),
        description: t('onboarding.roleDescAdmin'),
      },
      {
        value: 'manager',
        label: t('onboarding.roleManager'),
        description: t('onboarding.roleDescManager'),
      },
      { value: 'user', label: t('onboarding.roleUser'), description: t('onboarding.roleDescUser') },
      {
        value: 'viewer',
        label: t('onboarding.roleViewer'),
        description: t('onboarding.roleDescViewer'),
      },
    ],
    [t]
  )

  const translateRole = (role: string) => roleOptions.find((r) => r.value === role)?.label ?? role

  // Update active tab when URL changes
  useEffect(() => {
    const tabFromUrl = searchParams?.get('tab')
    if (tabFromUrl && tabFromUrl !== activeTab) {
      setActiveTab(tabFromUrl)
    }
  }, [searchParams, activeTab])

  // Fetch current user's invitations on mount
  useEffect(() => {
    fetchUserInvitations()
  }, [user])

  const fetchUserInvitations = async (forceRefresh = false) => {
    if (!user?.email) return

    setLoading(true)
    setUserNotFound(false)

    try {
      const data = await invitationsApi.getUserInvitations(user.email, forceRefresh)
      const invitations = data.invitations || []

      // Extract saved onboarding state for wizard resume
      if (data.user?.onboardingStep != null) {
        setSavedOnboardingStep(data.user.onboardingStep)
      }
      if (data.user?.onboardingStatus) {
        setSavedOnboardingStatus(data.user.onboardingStatus)
      }

      setInvitations(invitations)
      setUserNotFound(invitations.length === 0)
    } catch (error) {
      console.error('Error fetching invitations:', error)
      setUserNotFound(true)
      toast.error(t('onboarding.toastFetchInvitationFailed'))
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await fetchUserInvitations(true)
    } finally {
      setRefreshing(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const validateEmail = (email: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return emailRegex.test(email)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateEmail(formData.email)) {
      toast.error(t('onboarding.toastInvalidEmail'))
      return
    }

    if (formData.email === user?.email) {
      toast.error(t('onboarding.toastCannotInviteSelf'))
      return
    }

    const existingInvitation = invitations.find((inv: any) => inv.email === formData.email)
    if (existingInvitation) {
      toast.error(t('onboarding.toastEmailAlreadyInvited'))
      return
    }

    setSubmitting(true)

    try {
      const currentUserInvitation = invitations.find((inv: any) => inv.email === user?.email) || {}

      // Database routing handled automatically via JWT - no databaseName needed per CLAUDE.md
      const invitationData = {
        email: formData.email,
        company: currentUserInvitation.company || 'prelude',
        role: formData.role,
      }

      const result = await invitationsApi.createInvitation(invitationData)

      if (result.success) {
        toast.success(t('onboarding.toastInviteSuccess', { email: formData.email }))

        // Check employee_info sync status and show warning if not synced
        if (result.employee_sync && !result.employee_sync.synced) {
          toast.warning(
            t('onboarding.toastInviteSyncWarning', { reason: result.employee_sync.reason }),
            { duration: 8000 }
          )
        }

        setFormData({ email: '', role: 'viewer' })
        await fetchUserInvitations(true)
      } else {
        toast.error(result.message || t('onboarding.toastCreateInvitationFailed'))
      }
    } catch (error: any) {
      console.error('Error creating invitation:', error)
      toast.error(error.message || t('onboarding.toastSendInvitationFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const currentUserInfo = invitations.find((inv: any) => inv.email === user?.email) || {}
  const isAdmin = currentUserInfo.role === 'admin'

  const handleRoleChange = async (email: string, newRole: string) => {
    try {
      await invitationsApi.updateInvitation(email, { role: newRole })
      toast.success(t('onboarding.toastRoleUpdateSuccess', { email }))
      fetchUserInvitations(true)
    } catch (error) {
      toast.error(t('onboarding.toastRoleUpdateFailed'))
    }
  }

  const handleRemoveMember = (invitation: any) => {
    setMemberToDelete(invitation)
    setShowRemoveModal(true)
  }

  const confirmRemoveMember = async () => {
    if (!memberToDelete) return
    try {
      setIsRemoving(true)
      await invitationsApi.deleteInvitation(memberToDelete.email)
      toast.success(t('onboarding.toastRemoveMemberSuccess', { email: memberToDelete.email }))
      setShowRemoveModal(false)
      setMemberToDelete(null)
      fetchUserInvitations(true)
    } catch (error) {
      toast.error(t('onboarding.toastRemoveMemberFailed'))
    } finally {
      setIsRemoving(false)
    }
  }

  // Tutorial handlers
  const handleOpenTutorialSelector = () => {
    setTutorialSelectorOpen(true)
  }

  const handleSelectTutorial = (tutorialType: string) => {
    setSelectedTutorial(tutorialType)
    setTutorialOpen(true)
    toast.success(t('onboarding.toastTutorialStarted', { tutorialType }))
  }

  const handleTutorialNavigate = (viewId: string) => {
    console.log(`Tutorial requesting navigation to: ${viewId}`)
  }

  const renderTeamOrganization = () => (
    <div className="space-y-6">
      {/* Current User Info Card */}
      <div className="rounded-lg border border-rule bg-bone shadow-sm">
        <div className="border-b border-rule px-6 py-4">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-ink" />
            <h3 className="title-panel">
              {t('onboarding.yourAccountInfo')}
            </h3>
          </div>
        </div>
        <div className="px-6 py-5">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-mute" />
            </div>
          ) : userNotFound ? (
            <div className="flex items-center gap-3 rounded-lg border border-gold bg-gold-lo p-4">
              <AlertCircle className="h-5 w-5 flex-shrink-0 text-gold" />
              <div>
                <p className="text-sm font-medium text-gold">
                  {t('onboarding.accountNotFound')}
                </p>
                <p className="mt-1 text-xs text-gold">{t('onboarding.contactAdmin')}</p>
              </div>
            </div>
          ) : currentUserInfo.email ? (
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
              <div>
                <p className="mb-1 text-xs font-medium text-mute">{t('onboarding.email')}</p>
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-mute" />
                  <p className="text-sm font-medium text-ink">{currentUserInfo.email}</p>
                </div>
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-mute">{t('onboarding.company')}</p>
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-mute" />
                  <p className="text-sm font-medium text-ink">{currentUserInfo.company}</p>
                </div>
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-mute">{t('onboarding.role')}</p>
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-mute" />
                  <p className="text-sm font-medium text-ink">
                    {translateRole(currentUserInfo.role)}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-mute">{t('onboarding.loadingAccount')}</p>
          )}
        </div>
      </div>

      {/* Invitation Form Card */}
      <div className="rounded-lg border border-rule bg-bone shadow-sm">
        <div className="border-b border-rule px-6 py-4">
          <div className="flex items-center gap-2">
            <UserPlus className="h-5 w-5 text-ink" />
            <h3 className="title-panel">
              {t('onboarding.inviteNewMember')}
            </h3>
          </div>
        </div>
        <div className="px-6 py-5">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="email" className="mb-1 block text-sm font-medium text-ink">
                  {t('onboarding.emailAddress')} *
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="colleague@company.com"
                  value={formData.email}
                  onChange={handleInputChange}
                  required
                  disabled={submitting || userNotFound}
                  className="w-full rounded-lg border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none disabled:cursor-not-allowed disabled:bg-cream"
                />
              </div>

              <div>
                <label htmlFor="role" className="mb-1 block text-sm font-medium text-ink">
                  {t('onboarding.role')} *
                </label>
                <select
                  id="role"
                  name="role"
                  value={formData.role}
                  onChange={handleInputChange}
                  disabled={submitting || userNotFound}
                  className="w-full rounded-lg border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none disabled:cursor-not-allowed disabled:bg-cream"
                >
                  {roleOptions
                    .filter((option) => isAdmin || option.value !== 'admin')
                    .map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                </select>
                <p className="mt-1 text-xs text-mute">
                  {roleOptions.find((r) => r.value === formData.role)?.description}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-rule pt-4">
              <p className="text-sm text-mute">
                {t('onboarding.newMemberWillJoin', {
                  company: currentUserInfo.company || 'your company',
                  database: currentUserInfo.databaseName || 'the database',
                })}
              </p>
              <button
                type="submit"
                disabled={submitting || userNotFound}
                className="inline-flex items-center justify-center rounded-lg bg-deep px-4 py-2 text-sm font-medium text-bone shadow-sm transition-all duration-200 hover:bg-deep hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('onboarding.sending')}
                  </>
                ) : (
                  <>
                    <UserPlus className="mr-2 h-4 w-4" />
                    {t('onboarding.inviteMember')}
                  </>
                )}
              </button>
            </div>

            {userNotFound && (
              <div className="flex items-center gap-3 rounded-lg border border-threat/25 bg-threat-lo p-4">
                <AlertCircle className="h-5 w-5 flex-shrink-0 text-threat" />
                <p className="text-sm text-threat">{t('onboarding.mustBeRegistered')}</p>
              </div>
            )}
          </form>
        </div>
      </div>

      {/* Team Members List Card */}
      <div className="rounded-lg border border-rule bg-bone shadow-sm">
        <div className="border-b border-rule px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-ink" />
              <h3 className="title-panel">
                {t('onboarding.teamMembers')} ({invitations.length})
              </h3>
            </div>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-ink transition-colors hover:bg-paper hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              {t('onboarding.refresh')}
            </button>
          </div>
        </div>
        <div className="px-6 py-5">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-mute" />
            </div>
          ) : invitations.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-rule">
                    <th className="pb-3 text-left text-xs font-medium tracking-wider text-mute uppercase">
                      {t('onboarding.tableHeaderEmail')}
                    </th>
                    <th className="pb-3 text-left text-xs font-medium tracking-wider text-mute uppercase">
                      {t('onboarding.tableHeaderCompany')}
                    </th>
                    <th className="pb-3 text-left text-xs font-medium tracking-wider text-mute uppercase">
                      {t('onboarding.tableHeaderRole')}
                    </th>
                    <th className="pb-3 text-left text-xs font-medium tracking-wider text-mute uppercase">
                      {t('onboarding.tableHeaderDatabase')}
                    </th>
                    <th className="pb-3 text-left text-xs font-medium tracking-wider text-mute uppercase">
                      {t('onboarding.tableHeaderJoined')}
                    </th>
                    {isAdmin && (
                      <th className="pb-3 text-left text-xs font-medium tracking-wider text-mute uppercase">
                        {t('onboarding.tableHeaderActions')}
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-fog">
                  {invitations.map((invitation: any, index: number) => (
                    <tr key={invitation.id || index} className="transition-colors hover:bg-paper">
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <Mail className="h-4 w-4 text-mute" />
                          <span className="text-sm text-ink">{invitation.email}</span>
                          {invitation.email === user?.email && (
                            <span className="rounded bg-cream px-2 py-0.5 text-xs font-medium text-ink">
                              {t('onboarding.you')}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 text-sm text-ink">{invitation.company}</td>
                      <td className="py-3">
                        {isAdmin &&
                        invitation.role !== 'admin' &&
                        invitation.email !== user?.email ? (
                          <select
                            value={invitation.role}
                            onChange={(e) => handleRoleChange(invitation.email, e.target.value)}
                            className="cursor-pointer rounded-lg border border-rule px-2 py-1 text-xs font-medium focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none"
                          >
                            <option value="manager">{t('onboarding.roleManager')}</option>
                            <option value="user">{t('onboarding.roleUser')}</option>
                            <option value="viewer">{t('onboarding.roleViewer')}</option>
                          </select>
                        ) : (
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                              invitation.role === 'admin'
                                ? 'bg-cream text-ink'
                                : invitation.role === 'manager'
                                  ? 'bg-cream text-ink'
                                  : invitation.role === 'user'
                                    ? 'bg-accent-lo text-accent'
                                    : 'bg-cream text-ink'
                            }`}
                          >
                            {translateRole(invitation.role)}
                          </span>
                        )}
                      </td>
                      <td className="py-3 text-sm text-ink">{invitation.databaseName}</td>
                      <td className="py-3 text-sm text-mute">
                        {invitation.createdAt
                          ? (() => {
                              try {
                                return new Date(invitation.createdAt).toLocaleDateString()
                              } catch (e) {
                                return 'Invalid Date'
                              }
                            })()
                          : 'N/A'}
                      </td>
                      {isAdmin && (
                        <td className="py-3">
                          {invitation.role !== 'admin' && invitation.email !== user?.email ? (
                            <button
                              onClick={() => handleRemoveMember(invitation)}
                              className="rounded p-1.5 text-threat transition-colors hover:bg-threat-lo hover:text-threat"
                              title={t('onboarding.removeMember')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          ) : null}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-12 text-center">
              <Users className="mx-auto mb-3 h-12 w-12 text-fog" />
              <p className="font-medium text-mute">{t('onboarding.noTeamMembers')}</p>
              <p className="mt-1 text-sm text-mute">{t('onboarding.inviteFirst')}</p>
            </div>
          )}
        </div>
      </div>

      {/* Remove Member Confirmation Modal */}
      {showRemoveModal && memberToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-lg bg-bone shadow-2xl">
            <div className="border-b border-rule px-6 py-4">
              <h3 className="title-page">
                {t('onboarding.removeTeamMember')}
              </h3>
            </div>
            <div className="px-6 py-5">
              <p className="text-sm text-ink">
                {t('onboarding.removeConfirm', { email: memberToDelete.email })}
              </p>
            </div>
            <div className="flex items-center justify-end gap-3 border-t border-rule px-6 py-4">
              <button
                onClick={() => {
                  setShowRemoveModal(false)
                  setMemberToDelete(null)
                }}
                disabled={isRemoving}
                className="rounded-lg px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-paper disabled:opacity-50"
              >
                {t('onboarding.cancel')}
              </button>
              <button
                onClick={confirmRemoveMember}
                disabled={isRemoving}
                className="inline-flex items-center rounded-lg bg-threat px-4 py-2 text-sm font-medium text-bone transition-colors hover:bg-threat disabled:opacity-50"
              >
                {isRemoving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('onboarding.removing')}
                  </>
                ) : (
                  <>
                    <Trash2 className="mr-2 h-4 w-4" />
                    {t('onboarding.remove')}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )

  const renderPersonalOnboarding = () => (
    <div className="space-y-6">
      {/* Platform Tutorial Card */}
      <div className="overflow-hidden rounded-lg bg-deep shadow-md">
        <div className="px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-1 items-start gap-4">
              <div className="rounded-xl bg-bone/20 p-3 backdrop-blur-sm">
                <BookOpen className="h-8 w-8 text-bone" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-xl font-bold text-bone">
                  {t('onboarding.newToPlatform')}
                </h3>
                <p className="mb-3 text-sm text-bone/90">{t('onboarding.tutorialDescription')}</p>
                <div className="flex flex-wrap items-center gap-2 text-xs text-bone/80">
                  <span className="flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" />
                    {t('onboarding.tutorialModules')}
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" />
                    {t('onboarding.spotlightGuidance')}
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" />
                    {t('onboarding.interactiveLearning')}
                  </span>
                </div>
              </div>
            </div>
            <button
              onClick={handleOpenTutorialSelector}
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-xl bg-bone px-6 py-3 font-semibold text-deep shadow-lg transition-all hover:scale-105 hover:bg-cream hover:shadow-xl"
            >
              <PlayCircle className="h-5 w-5" />
              {t('onboarding.chooseTutorial')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )

  const renderCustomizeAI = () => (
    <div className="space-y-6">
      <CustomizeAIQuestionnaire
        key={savedOnboardingStep}
        userEmail={user?.email}
        initialStep={savedOnboardingStep}
        onboardingStatus={savedOnboardingStatus}
        onComplete={() => {
          toast.success(t('onboarding.toastAiPreferencesSaved'))
          router.push(`/workspace/${workspaceId}/crm`)
        }}
        onSkip={() => {
          toast(t('onboarding.toastAiPreferencesSkipped'))
          router.push(`/workspace/${workspaceId}/crm`)
        }}
      />
    </div>
  )

  const renderContent = () => {
    if (activeTab === 'personal-onboarding') {
      return renderPersonalOnboarding()
    }
    if (activeTab === 'customize-ai') {
      return renderCustomizeAI()
    }
    return renderTeamOrganization()
  }

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        {renderContent()}
      </motion.div>

      {/* Tutorial Selector */}
      <TutorialSelector
        isOpen={tutorialSelectorOpen}
        onClose={() => setTutorialSelectorOpen(false)}
        onSelectTutorial={handleSelectTutorial}
      />

      {/* Platform Tutorial */}
      <PlatformTutorial
        isOpen={tutorialOpen}
        onClose={() => setTutorialOpen(false)}
        tutorialType={selectedTutorial}
        onNavigate={handleTutorialNavigate}
      />
    </div>
  )
}
