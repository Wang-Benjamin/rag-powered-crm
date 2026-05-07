"""Redis-based job tracker for mass email and other background tasks."""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from utils.redis_cache import get_cache

logger = logging.getLogger(__name__)


class RedisJobTracker:
    """
    Persistent job tracker using Redis.

    Replaces in-memory dictionaries that lose state on server restart.
    Supports multiple workers and automatic expiration.
    """

    def __init__(self, job_type: str = "email", ttl: int = 86400):
        """
        Initialize job tracker.

        Args:
            job_type: Type of jobs to track (e.g., "email", "workflow")
            ttl: Time-to-live for jobs in seconds (default: 24 hours)
        """
        self.job_type = job_type
        self.ttl = ttl
        self.cache = get_cache()

    def _job_key(self, job_id: str) -> str:
        """Generate Redis key for job."""
        return f"job:{self.job_type}:{job_id}"

    def create_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """
        Create a new job.

        Args:
            job_id: Unique job identifier
            job_data: Job data dictionary

        Returns:
            True if created successfully
        """
        try:
            # Add metadata
            job_data["created_at"] = datetime.now(timezone.utc).isoformat()
            job_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            job_data["job_id"] = job_id

            key = self._job_key(job_id)
            success = self.cache.set(key, job_data, ttl=self.ttl)

            if success:
                logger.info(f"Created job {job_id} (type: {self.job_type})")
            else:
                logger.warning(f"Failed to create job {job_id} (Redis unavailable)")

            return success

        except Exception as e:
            logger.error(f"Error creating job {job_id}: {e}")
            return False

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update existing job data.

        Args:
            job_id: Job identifier
            updates: Fields to update

        Returns:
            True if updated successfully
        """
        try:
            key = self._job_key(job_id)
            job_data = self.get_job(job_id)

            if not job_data:
                logger.warning(f"Cannot update non-existent job {job_id}")
                return False

            # Merge updates
            job_data.update(updates)
            job_data["updated_at"] = datetime.now(timezone.utc).isoformat()

            success = self.cache.set(key, job_data, ttl=self.ttl)

            if success:
                logger.debug(f"Updated job {job_id}")
            else:
                logger.warning(f"Failed to update job {job_id} (Redis unavailable)")

            return success

        except Exception as e:
            logger.error(f"Error updating job {job_id}: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job data.

        Args:
            job_id: Job identifier

        Returns:
            Job data dict or None if not found
        """
        try:
            key = self._job_key(job_id)
            job_data = self.cache.get(key)

            if job_data:
                logger.debug(f"Retrieved job {job_id}")
            else:
                logger.debug(f"Job {job_id} not found")

            return job_data

        except Exception as e:
            logger.error(f"Error retrieving job {job_id}: {e}")
            return None

    def delete_job(self, job_id: str) -> bool:
        """
        Delete job.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted successfully
        """
        try:
            key = self._job_key(job_id)
            success = self.cache.delete(key)

            if success:
                logger.info(f"Deleted job {job_id}")
            else:
                logger.warning(f"Failed to delete job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Error deleting job {job_id}: {e}")
            return False

    def job_exists(self, job_id: str) -> bool:
        """Check if job exists."""
        return self.get_job(job_id) is not None

    def update_progress(
        self,
        job_id: str,
        sent: int,
        total: int,
        status: str = "in_progress"
    ) -> bool:
        """
        Update job progress.

        Args:
            job_id: Job identifier
            sent: Number of items processed
            total: Total number of items
            status: Job status

        Returns:
            True if updated successfully
        """
        progress_pct = (sent / total * 100) if total > 0 else 0

        updates = {
            "sent": sent,
            "total": total,
            "status": status,
            "progress": round(progress_pct, 1)
        }

        return self.update_job(job_id, updates)

    def mark_completed(self, job_id: str, final_stats: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark job as completed.

        Args:
            job_id: Job identifier
            final_stats: Optional final statistics

        Returns:
            True if updated successfully
        """
        updates = {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }

        if final_stats:
            updates.update(final_stats)

        return self.update_job(job_id, updates)

    def mark_failed(self, job_id: str, error: str) -> bool:
        """
        Mark job as failed.

        Args:
            job_id: Job identifier
            error: Error message

        Returns:
            True if updated successfully
        """
        updates = {
            "status": "failed",
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat()
        }

        return self.update_job(job_id, updates)


# Global job trackers
_mass_email_tracker: Optional[RedisJobTracker] = None
_workflow_tracker: Optional[RedisJobTracker] = None


def get_email_job_tracker() -> RedisJobTracker:
    """Get or create email job tracker."""
    global _mass_email_tracker
    if _mass_email_tracker is None:
        _mass_email_tracker = RedisJobTracker(job_type="email", ttl=86400)
    return _mass_email_tracker


def get_workflow_job_tracker() -> RedisJobTracker:
    """Get or create workflow job tracker."""
    global _workflow_tracker
    if _workflow_tracker is None:
        _workflow_tracker = RedisJobTracker(job_type="workflow", ttl=86400)
    return _workflow_tracker
