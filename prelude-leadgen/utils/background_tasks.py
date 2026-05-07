"""Tracked background tasks with retry and structured logging."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

# In-memory registry: key -> {"name", "status", "created_at", "task"}
_task_registry: dict[str, dict[str, Any]] = {}

_PRUNE_AGE_SECONDS = 600  # 10 minutes


def _prune_stale_tasks() -> None:
    """Remove completed/failed tasks older than 10 minutes."""
    now = datetime.now(timezone.utc)
    stale_keys = [
        key
        for key, entry in _task_registry.items()
        if entry["status"] in ("done", "failed")
        and (now - entry["created_at"]).total_seconds() > _PRUNE_AGE_SECONDS
    ]
    for key in stale_keys:
        del _task_registry[key]


def fire_tracked(
    name: str,
    coro_factory: Callable[[], Coroutine],
    *,
    retries: int = 2,
    retry_delay: float = 2.0,
    context: Optional[dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
) -> asyncio.Task:
    """
    Create an asyncio task with retry, logging, and tracking.

    Args:
        name: Human-readable task name for logs.
        coro_factory: Callable that returns a coroutine (NOT a coroutine object).
                      Must be callable multiple times for retry to work.
        retries: Max number of attempts (default 2).
        retry_delay: Seconds between retries (default 2.0).
        context: Optional dict of fields included in log lines.
        dedupe_key: Optional stable key for deduplication. When provided, if a
                    task with the same dedupe_key is already running, the existing
                    task is returned without spawning a new one.

    Returns:
        The created asyncio.Task (or existing task if deduplicated).
    """
    _prune_stale_tasks()

    ctx_str = f" {context}" if context else ""

    # Deduplication: return existing running task if same dedupe_key is active
    if dedupe_key is not None:
        for entry in _task_registry.values():
            if entry.get("dedupe_key") == dedupe_key and entry["status"] == "running":
                logger.info(
                    f"[BG:{name}] dedupe hit — returning existing task for key={dedupe_key!r}{ctx_str}"
                )
                return entry["task"]

    ts = datetime.now(timezone.utc)
    registry_key = dedupe_key if dedupe_key is not None else f"{name}:{ts.isoformat()}"

    async def _run() -> None:
        logger.info(f"[BG:{name}] started{ctx_str}")

        last_exc: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                await coro_factory()
                logger.info(
                    f"[BG:{name}] succeeded on attempt {attempt}/{retries}{ctx_str}"
                )
                _task_registry[registry_key]["status"] = "done"
                return
            except Exception as e:
                last_exc = e
                logger.warning(
                    f"[BG:{name}] attempt {attempt}/{retries} failed: "
                    f"{type(e).__name__}{ctx_str}"
                )
                if attempt < retries:
                    await asyncio.sleep(retry_delay)

        # All retries exhausted
        logger.error(
            f"[BG:{name}] failed after {retries} attempts: "
            f"{type(last_exc).__name__}{ctx_str}"
        )
        _task_registry[registry_key]["status"] = "failed"

    task = asyncio.create_task(_run(), name=f"bg:{name}")

    _task_registry[registry_key] = {
        "name": name,
        "status": "running",
        "created_at": ts,
        "context": context,
        "dedupe_key": dedupe_key,
        "task": task,
    }

    return task


def get_active_tasks() -> list[dict[str, Any]]:
    """Return a snapshot of the task registry (excluding the asyncio.Task object)."""
    return [
        {
            "name": entry["name"],
            "status": entry["status"],
            "created_at": entry["created_at"].isoformat(),
            "context": entry["context"],
        }
        for entry in _task_registry.values()
    ]
