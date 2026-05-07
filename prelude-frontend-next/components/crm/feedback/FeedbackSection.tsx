'use client'

import React, { useState, useEffect } from 'react'
import { Trash2, Check, LucideIcon } from 'lucide-react'
import { feedbackApi, FeedbackResponse, FeedbackCategory } from '@/lib/api/feedback'
import { Button } from '@/components/ui/button'
import { PageLoader } from '@/components/ui/page-loader'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from 'sonner'
import { useTranslations, useLocale } from 'next-intl'
import { ConfirmationToast } from '@/components/ui/confirmation-toast'
import { useConfirmationToast } from '@/hooks/useConfirmationToast'
import { StarRating } from './StarRating'
import { cn } from '@/utils/cn'

interface FeedbackSectionProps {
  title: string
  description: string
  customerId: number
  dealId?: number
  feedbackCategory: FeedbackCategory
  currentUserId?: number
  icon?: LucideIcon
  iconColor?: string
}

export function FeedbackSection({
  title,
  description,
  customerId,
  dealId,
  feedbackCategory,
  currentUserId,
  icon: Icon,
  iconColor = 'text-zinc-500',
}: FeedbackSectionProps) {
  const t = useTranslations('crm')
  const locale = useLocale()
  const [feedbackList, setFeedbackList] = useState<FeedbackResponse[]>([])
  const [userFeedback, setUserFeedback] = useState<FeedbackResponse | null>(null)
  const [rating, setRating] = useState<number>(0)
  const [feedbackText, setFeedbackText] = useState<string>('')
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const { confirm, toastProps } = useConfirmationToast()

  // Load feedback on mount
  useEffect(() => {
    loadFeedback()
  }, [customerId, dealId, feedbackCategory])

  const loadFeedback = async () => {
    setIsLoading(true)
    try {
      const data = await feedbackApi.getFeedbackByCategory(customerId, feedbackCategory, dealId)
      setFeedbackList(data)

      // Find user's own feedback
      const myFeedback = data.find((f) => f.employeeId === currentUserId)
      if (myFeedback) {
        setUserFeedback(myFeedback)
        setRating(myFeedback.rating)
        // Get the latest feedback text from history
        const latestFeedback = myFeedback.feedbackHistory[myFeedback.feedbackHistory.length - 1]
        setFeedbackText(latestFeedback?.text || '')
      } else {
        // Reset form if no existing feedback
        setUserFeedback(null)
        setRating(0)
        setFeedbackText('')
      }
    } catch (error: any) {
      console.error('Error loading feedback:', error)
      toast.error(t('toasts.error'), { description: error.message || t('feedback.loadFailed') })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (rating === 0) {
      toast.error(t('feedback.ratingRequired'), { description: t('feedback.selectRating') })
      return
    }

    setIsSubmitting(true)
    try {
      if (userFeedback) {
        // Update existing feedback
        await feedbackApi.updateFeedback(userFeedback.feedbackId, {
          rating,
          feedbackText: feedbackText || undefined,
        })
        toast(t('toasts.success'), { description: t('feedback.updated') })
      } else {
        // Create new feedback
        await feedbackApi.createFeedback({
          customerId: customerId,
          dealId: dealId,
          feedbackCategory: feedbackCategory,
          rating,
          feedbackText: feedbackText || undefined,
        })
        toast(t('toasts.success'), { description: t('feedback.submitted') })
      }

      // Reload feedback
      await loadFeedback()
    } catch (error: any) {
      console.error('Error submitting feedback:', error)
      toast.error(t('toasts.error'), { description: error.message || t('feedback.submitFailed') })
    } finally {
      setIsSubmitting(false)
    }
  }

  const confirmDelete = (feedbackId: number) => {
    confirm({
      title: t('feedback.deleteConfirm'),
      description: t('feedback.deleteDescription'),
      confirmLabel: t('feedback.deleteButton'),
      variant: 'destructive',
      onConfirm: async () => {
        try {
          await feedbackApi.deleteFeedback(feedbackId)
          toast(t('toasts.success'), { description: t('feedback.deleted') })

          // Reload feedback
          await loadFeedback()
        } catch (error: any) {
          console.error('Error deleting feedback:', error)
          toast.error(t('toasts.error'), { description: error.message || t('feedback.deleteFailed') })
        }
      },
    })
  }

  // Show all feedback in Team Feedback section (including current user's)
  const allTeamFeedback = feedbackList

  return (
    <>
      <Card className="h-full">
        <CardHeader>
          <div className="flex items-center gap-2">
            {Icon && <Icon className={cn('h-5 w-5', iconColor)} />}
            <CardTitle className="title-panel">{title}</CardTitle>
          </div>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {isLoading ? (
            <div className="py-4">
              <PageLoader label="Loading feedback" className="min-h-[160px]" />
            </div>
          ) : (
            <>
              {/* Your Feedback Form */}
              <div className="space-y-4">
                <h4 className="title-block">{t('feedback.yourRating')}</h4>
                <StarRating rating={rating} onRatingChange={setRating} size="lg" />

                <div className="space-y-2">
                  <label
                    htmlFor={`feedback-text-${feedbackCategory}`}
                    className="text-sm font-medium text-zinc-700"
                  >
                    {t('feedback.additionalComments')}
                  </label>
                  <Textarea
                    id={`feedback-text-${feedbackCategory}`}
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    placeholder={t('feedback.feedbackPlaceholder')}
                    rows={3}
                    className="resize-none"
                  />
                </div>

                <div className="flex gap-2">
                  <Button
                    onClick={handleSubmit}
                    disabled={isSubmitting || rating === 0}
                    loading={isSubmitting}
                    loadingText={userFeedback ? t('feedback.updating') : t('feedback.submitting')}
                    className="flex-1"
                  >
                    <Check className="mr-2 h-4 w-4" />
                    {userFeedback ? t('feedback.updateButton') : t('feedback.submitFeedback')}
                  </Button>

                  {userFeedback && (
                    <Button
                      variant="outline"
                      onClick={() => confirmDelete(userFeedback.feedbackId)}
                      className="text-red-600 hover:bg-red-50 hover:text-red-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>

              {/* Team Feedback */}
              {allTeamFeedback.length > 0 && (
                <div className="space-y-3 border-t pt-4">
                  <h4 className="title-block">
                    {t('feedback.teamFeedback')}
                  </h4>
                  <div className="space-y-3">
                    {allTeamFeedback.map((feedback) => {
                      const latestFeedback =
                        feedback.feedbackHistory[feedback.feedbackHistory.length - 1]
                      const isCurrentUser = feedback.employeeId === currentUserId
                      return (
                        <div
                          key={feedback.feedbackId}
                          className="space-y-2 rounded-lg bg-zinc-50 p-3"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-zinc-900">
                                {feedback.employeeName || t('feedback.teamMember')}
                                {isCurrentUser && (
                                  <span className="ml-1 text-xs text-zinc-600">
                                    {t('feedback.you')}
                                  </span>
                                )}
                              </span>
                              <StarRating rating={feedback.rating} readonly size="sm" />
                            </div>
                            <span className="text-xs text-zinc-500">
                              {new Date(feedback.updatedAt).toLocaleDateString(locale)}
                            </span>
                          </div>
                          {latestFeedback?.text && (
                            <p className="text-sm text-zinc-600">{latestFeedback.text}</p>
                          )}
                          {feedback.feedbackHistory.length > 1 && (
                            <details className="text-xs text-zinc-500">
                              <summary className="cursor-pointer hover:text-zinc-700">
                                {t('feedback.viewHistory', {
                                  count: feedback.feedbackHistory.length - 1,
                                })}
                              </summary>
                              <div className="mt-2 space-y-2 border-l-2 border-zinc-300 pl-2">
                                {feedback.feedbackHistory
                                  .slice(0, -1)
                                  .reverse()
                                  .map((entry, idx) => (
                                    <div key={idx} className="text-xs">
                                      <div className="text-zinc-500">
                                        {new Date(entry.timestamp).toLocaleString(locale)}
                                      </div>
                                      <div className="text-zinc-600">{entry.text}</div>
                                    </div>
                                  ))}
                              </div>
                            </details>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <ConfirmationToast {...toastProps} />
    </>
  )
}
