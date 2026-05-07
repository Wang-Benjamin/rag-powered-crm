"""Temporal topology helpers for CRM.

Prelude intentionally uses one Temporal namespace today. Isolation is encoded
with environment-prefixed task queues, schedule IDs, and workflow IDs:

- main owns recurring shared-DB schedules.
- dev can run email workers on dev-prefixed queues.
- local workers are disabled by default; if explicitly enabled for email, use a
  developer-specific local prefix so two laptops do not poll the same queue.
"""

from __future__ import annotations

import getpass
import os
import re
from dataclasses import dataclass

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean environment flag."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "local"


def app_env() -> str:
    """Return Prelude's normalized runtime environment.

    APP_ENV is preferred. ENVIRONMENT remains supported because existing
    services already use it for Sentry/deploy metadata.
    """
    raw = (
        os.getenv("APP_ENV")
        or os.getenv("PRELUDE_ENV")
        or os.getenv("ENVIRONMENT")
        or "local"
    ).strip().lower()

    if raw in {"main", "prod", "production"}:
        return "main"
    if raw in {"dev", "development", "staging", "stage"}:
        return "dev"
    if raw in {"local", "localhost", "test", "testing"}:
        return "local"
    return _slug(raw)


def local_worker_id() -> str:
    explicit = os.getenv("TEMPORAL_LOCAL_WORKER_ID") or os.getenv("USER") or getpass.getuser()
    return _slug(explicit)


def queue_prefix(environment: str | None = None) -> str:
    environment = environment or app_env()
    if environment == "local":
        return f"local-{local_worker_id()}"
    return environment


@dataclass(frozen=True)
class TemporalTopology:
    app_env: str
    namespace: str
    queue_prefix: str
    scheduler_task_queue: str
    mass_email_task_queue: str
    summary_schedule_id: str
    signal_schedule_id: str
    workflow_id_prefix: str
    scheduler_owner: bool
    scheduler_worker_enabled: bool
    mass_email_worker_enabled: bool
    local_email_worker_allowed: bool

    @property
    def any_worker_enabled(self) -> bool:
        return self.scheduler_worker_enabled or self.mass_email_worker_enabled

    def validate_worker_startup(self) -> None:
        """Fail closed for unsafe worker topology."""
        if self.scheduler_worker_enabled and not self.scheduler_owner:
            raise RuntimeError(
                "Temporal scheduler worker can run only in APP_ENV=main with "
                "TEMPORAL_SCHEDULER_OWNER enabled."
            )
        if self.mass_email_worker_enabled and self.app_env == "local" and not self.local_email_worker_allowed:
            raise RuntimeError(
                "Local Temporal email workers are disabled by default. Set "
                "ALLOW_LOCAL_TEMPORAL_EMAIL_WORKER=true and a unique "
                "TEMPORAL_LOCAL_WORKER_ID only for explicit local email-worker testing."
            )


def get_temporal_topology() -> TemporalTopology:
    environment = app_env()
    namespace = os.getenv("TEMPORAL_NAMESPACE", "").strip()
    prefix = os.getenv("TEMPORAL_QUEUE_PREFIX", "").strip() or queue_prefix(environment)

    legacy_enabled = env_flag("ENABLE_TEMPORAL_WORKER", False)
    # Scheduler ownership requires explicit opt-in even on main: blue/green or
    # canary main replicas would otherwise both register and drive the shared
    # summary/signal schedules, double-firing against tenant data.
    scheduler_owner = environment == "main" and env_flag("TEMPORAL_SCHEDULER_OWNER", False)

    scheduler_enabled = env_flag(
        "ENABLE_TEMPORAL_SCHEDULER_WORKER",
        default=legacy_enabled and scheduler_owner,
    )
    mass_email_enabled = env_flag(
        "ENABLE_TEMPORAL_MASS_EMAIL_WORKER",
        default=legacy_enabled,
    )

    return TemporalTopology(
        app_env=environment,
        namespace=namespace,
        queue_prefix=prefix,
        scheduler_task_queue=os.getenv("SCHEDULER_TASK_QUEUE", f"{prefix}-crm-schedulers").strip(),
        mass_email_task_queue=os.getenv("MASS_EMAIL_TASK_QUEUE", f"{prefix}-crm-mass-email").strip(),
        summary_schedule_id=os.getenv("SUMMARY_SCHEDULE_ID", f"{prefix}-crm-summary-generation-daily").strip(),
        signal_schedule_id=os.getenv("SIGNAL_SCHEDULE_ID", f"{prefix}-crm-signal-evaluation-daily").strip(),
        workflow_id_prefix=os.getenv("TEMPORAL_WORKFLOW_ID_PREFIX", prefix).strip(),
        scheduler_owner=scheduler_owner,
        scheduler_worker_enabled=scheduler_enabled,
        mass_email_worker_enabled=mass_email_enabled,
        local_email_worker_allowed=env_flag("ALLOW_LOCAL_TEMPORAL_EMAIL_WORKER", False),
    )


def require_scheduler_owner() -> TemporalTopology:
    topology = get_temporal_topology()
    if not topology.scheduler_owner:
        raise RuntimeError(
            "Recurring shared-DB Temporal schedules may only be registered or "
            "triggered by APP_ENV=main."
        )
    return topology
