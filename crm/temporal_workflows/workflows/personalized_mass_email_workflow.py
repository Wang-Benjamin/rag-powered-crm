"""
Personalized Mass Email Workflow - CRM Service
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Any, Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_workflows.activities.email_activities import (
        send_single_email_activity,
        update_writing_style_activity,
        update_campaign_email_status_activity,
        finalize_campaign_status_activity,
    )


@dataclass
class PersonalizedMassEmailWorkflowInput:
    """Input parameters for PersonalizedMassEmailWorkflow."""
    job_id: str
    emails: List[Dict[str, Any]]
    provider: Optional[str]
    user_email: str
    user_name: str
    modified_emails: List[Dict[str, Any]]
    campaign_id: Optional[str] = None


@workflow.defn(name="PersonalizedMassEmailWorkflow")
class PersonalizedMassEmailWorkflow:
    """Workflow to send pre-generated personalized emails."""

    def __init__(self):
        self._job_id = ""
        self._total = 0
        self._sent = 0
        self._failed = 0
        self._errors = []
        self._status = "pending"

    @workflow.run
    async def run(self, input: PersonalizedMassEmailWorkflowInput) -> Dict[str, Any]:
        self._job_id = input.job_id
        self._total = len(input.emails)
        self._sent = 0
        self._failed = 0
        self._errors = []
        self._status = "in_progress"

        job_id = input.job_id
        total = len(input.emails)

        workflow.logger.info(f"[CRM] Personalized mass email job {job_id} started | {total} emails")

        sent = 0
        failed = 0
        errors = []

        email_retry_policy = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=10),
            maximum_interval=timedelta(minutes=2),
            non_retryable_error_types=["ValueError"]
        )

        for i, email_data in enumerate(input.emails):
            client_name = email_data.get('client_name', 'Unknown')
            to_email = email_data.get('to_email')
            subject = email_data.get('subject')
            body = email_data.get('body')
            client_id = email_data.get('client_id')

            try:
                send_result = await workflow.execute_activity(
                    send_single_email_activity,
                    args=[{
                        'to_email': to_email,
                        'subject': subject,
                        'body': body,
                        'customer_id': client_id,
                        'deal_id': email_data.get('deal_id'),
                        'provider': input.provider,
                        'user_email': input.user_email,
                        'user_name': input.user_name
                    }],
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=email_retry_policy
                )

                if send_result.get('success'):
                    sent += 1
                    self._sent += 1
                    workflow.logger.info(f"[CRM] [{job_id}] {i+1}/{total} sent to {client_name}")
                    if input.campaign_id and client_id:
                        await workflow.execute_activity(
                            update_campaign_email_status_activity,
                            args=[{
                                'campaign_id': input.campaign_id,
                                'customer_id': client_id,
                                'status': 'sent',
                                'email_id': send_result.get('email_id'),
                                'user_email': input.user_email,
                            }],
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=RetryPolicy(maximum_attempts=3)
                        )
                else:
                    failed += 1
                    self._failed += 1
                    error_msg = f"{client_name}: {send_result.get('error', 'Unknown error')}"
                    errors.append(error_msg)
                    self._errors.append(error_msg)
                    self._errors = self._errors[-10:]
                    workflow.logger.warning(f"[CRM] [{job_id}] {i+1}/{total} failed - {error_msg}")
                    if input.campaign_id and client_id:
                        await workflow.execute_activity(
                            update_campaign_email_status_activity,
                            args=[{
                                'campaign_id': input.campaign_id,
                                'customer_id': client_id,
                                'status': 'failed',
                                'error_message': send_result.get('error', 'Unknown error'),
                                'user_email': input.user_email,
                            }],
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=RetryPolicy(maximum_attempts=3)
                        )

            except Exception as e:
                failed += 1
                self._failed += 1
                error_msg = f"{client_name}: {str(e)}"
                errors.append(error_msg)
                self._errors.append(error_msg)
                self._errors = self._errors[-10:]
                workflow.logger.error(f"[CRM] [{job_id}] {i+1}/{total} error - {error_msg}")
                if input.campaign_id and client_id:
                    await workflow.execute_activity(
                        update_campaign_email_status_activity,
                        args=[{
                            'campaign_id': input.campaign_id,
                            'customer_id': client_id,
                            'status': 'failed',
                            'error_message': str(e),
                            'user_email': input.user_email,
                        }],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RetryPolicy(maximum_attempts=3)
                    )

            # Anti-spam delay
            if i < total - 1:
                delay = workflow.random().uniform(35, 45)
                await workflow.sleep(timedelta(seconds=delay))

        # Finalize campaign status based on all send results
        if input.campaign_id:
            await workflow.execute_activity(
                finalize_campaign_status_activity,
                args=[{
                    'campaign_id': input.campaign_id,
                    'user_email': input.user_email,
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )

        # Update writing style with user-edited emails only
        if input.modified_emails and len(input.modified_emails) > 0:
            email_samples = [
                {'subject': e.get('subject'), 'body': e.get('body')}
                for e in input.modified_emails
            ]
            await workflow.execute_activity(
                update_writing_style_activity,
                args=[input.user_email, email_samples],
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )

        self._status = "completed"
        workflow.logger.info(f"[CRM] Personalized mass email job {job_id} completed | {sent}/{total} sent | {failed} failed")

        return {
            'job_id': job_id,
            'total': total,
            'sent': sent,
            'failed': failed,
            'errors': errors
        }

    @workflow.query
    def get_progress(self) -> dict:
        """Return current workflow progress for polling endpoint."""
        return {
            "job_id": self._job_id,
            "status": self._status,
            "total": self._total,
            "sent": self._sent,
            "failed": self._failed,
            "errors": self._errors[-10:],
            "progress_percentage": int((self._sent + self._failed) / self._total * 100) if self._total > 0 else 0,
        }
