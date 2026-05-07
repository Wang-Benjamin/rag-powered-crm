export interface ScheduledMassEmail {
  scheduleId: number
  jobId: string
  emailType: 'template' | 'personalized'
  status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled' | 'failed'
  scheduledAt: string
  createdAt: string
  totalRecipients: number
  templateName?: string
  sent: number
  failed: number
  payload?: Record<string, any>
}
