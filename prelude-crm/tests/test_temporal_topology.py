"""Tests for single-namespace Temporal topology resolution."""

import pytest

from temporal_workflows.topology import get_temporal_topology


_TEMPORAL_ENV_VARS = [
    "APP_ENV",
    "PRELUDE_ENV",
    "ENVIRONMENT",
    "TEMPORAL_NAMESPACE",
    "TEMPORAL_QUEUE_PREFIX",
    "TEMPORAL_WORKFLOW_ID_PREFIX",
    "TEMPORAL_LOCAL_WORKER_ID",
    "SCHEDULER_TASK_QUEUE",
    "MASS_EMAIL_TASK_QUEUE",
    "SUMMARY_SCHEDULE_ID",
    "SIGNAL_SCHEDULE_ID",
    "TEMPORAL_SCHEDULER_OWNER",
    "ENABLE_TEMPORAL_WORKER",
    "ENABLE_TEMPORAL_SCHEDULER_WORKER",
    "ENABLE_TEMPORAL_MASS_EMAIL_WORKER",
    "ALLOW_LOCAL_TEMPORAL_EMAIL_WORKER",
]


@pytest.fixture(autouse=True)
def clean_temporal_env(monkeypatch):
    for name in _TEMPORAL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_local_defaults_disable_workers_and_use_developer_queue(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("TEMPORAL_LOCAL_WORKER_ID", "James Local")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "prelude-crm.xtjsl")

    topology = get_temporal_topology()

    assert topology.app_env == "local"
    assert topology.namespace == "prelude-crm.xtjsl"
    assert topology.scheduler_worker_enabled is False
    assert topology.mass_email_worker_enabled is False
    assert topology.scheduler_owner is False
    assert topology.mass_email_task_queue == "local-james-local-crm-mass-email"
    assert topology.scheduler_task_queue == "local-james-local-crm-schedulers"


def test_main_legacy_worker_flag_enables_scheduler_and_email(monkeypatch):
    monkeypatch.setenv("APP_ENV", "main")
    monkeypatch.setenv("ENABLE_TEMPORAL_WORKER", "true")
    monkeypatch.setenv("TEMPORAL_SCHEDULER_OWNER", "true")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "prelude-crm.xtjsl")

    topology = get_temporal_topology()

    assert topology.scheduler_owner is True
    assert topology.scheduler_worker_enabled is True
    assert topology.mass_email_worker_enabled is True
    assert topology.scheduler_task_queue == "main-crm-schedulers"
    assert topology.mass_email_task_queue == "main-crm-mass-email"
    assert topology.summary_schedule_id == "main-crm-summary-generation-daily"
    assert topology.signal_schedule_id == "main-crm-signal-evaluation-daily"


def test_main_without_explicit_owner_does_not_own_scheduler(monkeypatch):
    """Main must not auto-own the scheduler; the env flag is mandatory."""
    monkeypatch.setenv("APP_ENV", "main")
    monkeypatch.setenv("ENABLE_TEMPORAL_WORKER", "true")

    topology = get_temporal_topology()

    assert topology.scheduler_owner is False
    assert topology.scheduler_worker_enabled is False


def test_dev_email_worker_uses_dev_queue_and_cannot_own_scheduler(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ENABLE_TEMPORAL_MASS_EMAIL_WORKER", "true")
    monkeypatch.setenv("TEMPORAL_SCHEDULER_OWNER", "true")

    topology = get_temporal_topology()

    assert topology.scheduler_owner is False
    assert topology.scheduler_worker_enabled is False
    assert topology.mass_email_worker_enabled is True
    assert topology.mass_email_task_queue == "dev-crm-mass-email"


def test_dev_scheduler_worker_fails_closed(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ENABLE_TEMPORAL_SCHEDULER_WORKER", "true")

    topology = get_temporal_topology()

    with pytest.raises(RuntimeError, match="scheduler worker can run only"):
        topology.validate_worker_startup()


def test_local_email_worker_requires_explicit_allow(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("TEMPORAL_LOCAL_WORKER_ID", "james")
    monkeypatch.setenv("ENABLE_TEMPORAL_MASS_EMAIL_WORKER", "true")

    topology = get_temporal_topology()

    with pytest.raises(RuntimeError, match="Local Temporal email workers are disabled"):
        topology.validate_worker_startup()

    monkeypatch.setenv("ALLOW_LOCAL_TEMPORAL_EMAIL_WORKER", "true")
    topology = get_temporal_topology()
    topology.validate_worker_startup()
    assert topology.mass_email_task_queue == "local-james-crm-mass-email"
