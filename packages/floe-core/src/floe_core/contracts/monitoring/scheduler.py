"""CheckScheduler - Periodic task scheduler for contract checks.

This module implements a scheduler for periodic execution of contract monitoring
checks. Ensures no overlapping executions and resilient error handling.

Epic: 3D Contract Monitoring (T027)
Requirements: FR-001, FR-002
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from floe_core.contracts.monitoring.config import MonitoringConfig

logger = structlog.get_logger(__name__)


class CheckScheduler:
    """Scheduler for periodic contract monitoring checks.

    Schedules asynchronous callbacks to run at regular intervals with:
    - No-overlap guard: skips execution if previous callback still running
    - Exception resilience: continues scheduling even if callback raises
    - Replace-on-reschedule: cancels old task when rescheduling same name

    Args:
        config: MonitoringConfig instance (currently unused but reserved for future use)

    Example:
        >>> scheduler = CheckScheduler(monitoring_config)
        >>> await scheduler.schedule("health_check", check_health, interval_seconds=60.0)
        >>> scheduler.is_scheduled("health_check")
        True
        >>> scheduler.cancel("health_check")
    """

    def __init__(self, config: MonitoringConfig) -> None:
        """Initialize scheduler.

        Args:
            config: Monitoring configuration
        """
        self._config = config
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._running: set[str] = set()
        self._logger = logger.bind(component="check_scheduler")

    async def schedule(
        self,
        task_name: str,
        callback: Callable[[], Awaitable[Any]],
        interval_seconds: float,
    ) -> None:
        """Schedule a periodic task with the given callback and interval.

        If a task with the same name already exists, cancels it first.

        Args:
            task_name: Unique identifier for this scheduled task
            callback: Async function to execute periodically
            interval_seconds: Seconds between executions (must be > 0)

        Raises:
            ValueError: If interval_seconds <= 0
        """
        if interval_seconds <= 0:
            msg = f"interval_seconds must be positive, got {interval_seconds}"
            raise ValueError(msg)

        # Cancel existing task with same name if present
        if task_name in self._tasks:
            self._logger.info(
                "replacing_existing_task",
                task_name=task_name,
                interval_seconds=interval_seconds,
            )
            self.cancel(task_name)

        # Create background task for periodic execution
        task = asyncio.create_task(
            self._run_periodic(task_name, callback, interval_seconds)
        )
        self._tasks[task_name] = task

        self._logger.info(
            "task_scheduled",
            task_name=task_name,
            interval_seconds=interval_seconds,
        )

    async def _run_periodic(
        self,
        task_name: str,
        callback: Callable[[], Awaitable[Any]],
        interval_seconds: float,
    ) -> None:
        """Execute callback periodically with no-overlap guard.

        Args:
            task_name: Task identifier for tracking
            callback: Async function to execute
            interval_seconds: Seconds to wait between executions
        """
        first_run = True
        while True:
            if not first_run:
                await asyncio.sleep(interval_seconds)
            else:
                first_run = False

            # No-overlap guard: skip if previous execution still running
            if task_name in self._running:
                self._logger.warning(
                    "callback_overrun",
                    task_name=task_name,
                    interval_seconds=interval_seconds,
                )
                continue

            # Mark as running
            self._running.add(task_name)

            try:
                # Execute callback - exceptions are caught and logged
                await callback()
            except Exception as e:
                self._logger.error(
                    "callback_error",
                    task_name=task_name,
                    error=str(e),
                    exc_info=True,
                )
            finally:
                # Always remove from running set
                self._running.discard(task_name)

    def is_scheduled(self, task_name: str) -> bool:
        """Check if a task is currently scheduled.

        Args:
            task_name: Task identifier to check

        Returns:
            True if task is scheduled, False otherwise
        """
        return task_name in self._tasks

    @property
    def scheduled_tasks(self) -> list[str]:
        """Get list of all scheduled task names.

        Returns:
            List of task names currently scheduled
        """
        return list(self._tasks.keys())

    @property
    def running_tasks(self) -> set[str]:
        """Get set of task names currently executing.

        Returns:
            Set of task names with callbacks currently running
        """
        return self._running.copy()

    def cancel(self, task_name: str) -> None:
        """Cancel a scheduled task.

        Args:
            task_name: Task identifier to cancel

        Raises:
            KeyError: If task_name is not scheduled
        """
        if task_name not in self._tasks:
            raise KeyError(f"Task not found: {task_name}")

        task = self._tasks.pop(task_name)
        task.cancel()

        self._logger.info("task_cancelled", task_name=task_name)

    def cancel_all(self) -> None:
        """Cancel all scheduled tasks."""
        for task_name in list(self._tasks.keys()):
            self.cancel(task_name)

        self._logger.info("all_tasks_cancelled")
