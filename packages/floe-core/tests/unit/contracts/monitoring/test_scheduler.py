"""Unit tests for async scheduler.

Tests the CheckScheduler class that manages periodic contract checks.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from floe_core.contracts.monitoring.config import (
    CheckIntervalConfig,
    MonitoringConfig,
)
from floe_core.contracts.monitoring.scheduler import CheckScheduler


@pytest.fixture
def monitoring_config() -> MonitoringConfig:
    """Create default monitoring configuration for tests.

    Returns:
        MonitoringConfig with default settings
    """
    return MonitoringConfig(
        enabled=True,
        mode="scheduled",
        check_intervals=CheckIntervalConfig(),
        check_timeout_seconds=30,
    )


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-001")
async def test_schedule_creates_periodic_task(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that schedule creates and runs a periodic task.

    Verifies that a scheduled callback executes multiple times
    at the specified interval.
    """
    scheduler = CheckScheduler(monitoring_config)
    call_count = 0

    async def callback() -> None:
        nonlocal call_count
        call_count += 1

    try:
        # Schedule task with 50ms interval
        await scheduler.schedule("test_task", callback, 0.05)

        # Wait for multiple executions
        await asyncio.sleep(0.15)

        # Should have executed at least 2 times (0ms, 50ms, 100ms)
        assert call_count >= 2
        assert scheduler.is_scheduled("test_task")
        assert "test_task" in scheduler.scheduled_tasks

    finally:
        scheduler.cancel_all()


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-001")
async def test_cancel_stops_scheduled_task(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that cancel stops a scheduled task.

    Verifies that after cancellation, no more executions occur.
    """
    scheduler = CheckScheduler(monitoring_config)
    call_count = 0

    async def callback() -> None:
        nonlocal call_count
        call_count += 1

    try:
        # Schedule task
        await scheduler.schedule("test_task", callback, 0.05)

        # Wait for first execution
        await asyncio.sleep(0.06)
        first_count = call_count

        # Cancel the task
        scheduler.cancel("test_task")

        # Wait to ensure no more executions
        await asyncio.sleep(0.1)

        # Count should not have increased
        assert call_count == first_count
        assert not scheduler.is_scheduled("test_task")
        assert "test_task" not in scheduler.scheduled_tasks

    finally:
        scheduler.cancel_all()


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-001")
async def test_cancel_all_stops_all_tasks(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that cancel_all stops all scheduled tasks.

    Verifies that multiple tasks are all stopped by cancel_all.
    """
    scheduler = CheckScheduler(monitoring_config)
    task1_count = 0
    task2_count = 0

    async def callback1() -> None:
        nonlocal task1_count
        task1_count += 1

    async def callback2() -> None:
        nonlocal task2_count
        task2_count += 1

    # Schedule two tasks
    await scheduler.schedule("task1", callback1, 0.05)
    await scheduler.schedule("task2", callback2, 0.05)

    # Wait for first execution
    await asyncio.sleep(0.06)
    first_count1 = task1_count
    first_count2 = task2_count

    # Cancel all tasks
    scheduler.cancel_all()

    # Wait to ensure no more executions
    await asyncio.sleep(0.1)

    # Counts should not have increased
    assert task1_count == first_count1
    assert task2_count == first_count2
    assert len(scheduler.scheduled_tasks) == 0
    assert not scheduler.is_scheduled("task1")
    assert not scheduler.is_scheduled("task2")


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-001")
async def test_is_scheduled_returns_correct_state(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that is_scheduled returns correct scheduling state.

    Verifies state transitions: not scheduled -> scheduled -> cancelled.
    """
    scheduler = CheckScheduler(monitoring_config)

    async def callback() -> None:
        pass

    try:
        # Initially not scheduled
        assert not scheduler.is_scheduled("test_task")

        # After scheduling
        await scheduler.schedule("test_task", callback, 0.05)
        assert scheduler.is_scheduled("test_task")

        # After cancellation
        scheduler.cancel("test_task")
        assert not scheduler.is_scheduled("test_task")

    finally:
        scheduler.cancel_all()


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-001")
async def test_scheduled_tasks_lists_all_active_tasks(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that scheduled_tasks property lists all active tasks.

    Verifies that the list updates correctly as tasks are added and removed.
    """
    scheduler = CheckScheduler(monitoring_config)

    async def callback() -> None:
        pass

    try:
        # Initially empty
        assert scheduler.scheduled_tasks == []

        # After scheduling first task
        await scheduler.schedule("task1", callback, 0.05)
        assert set(scheduler.scheduled_tasks) == {"task1"}

        # After scheduling second task
        await scheduler.schedule("task2", callback, 0.05)
        assert set(scheduler.scheduled_tasks) == {"task1", "task2"}

        # After cancelling one task
        scheduler.cancel("task1")
        assert set(scheduler.scheduled_tasks) == {"task2"}

        # After cancel_all
        scheduler.cancel_all()
        assert scheduler.scheduled_tasks == []

    finally:
        scheduler.cancel_all()


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-002")
async def test_no_overlap_guard_prevents_concurrent_execution(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that no-overlap guard prevents concurrent callback execution.

    Verifies that if a callback is still running when the next interval
    fires, the scheduler skips that execution instead of starting a
    second concurrent instance.
    """
    scheduler = CheckScheduler(monitoring_config)
    execution_count = 0
    concurrent_executions = 0
    currently_running = False
    event = asyncio.Event()

    async def slow_callback() -> None:
        nonlocal execution_count, concurrent_executions, currently_running

        if currently_running:
            concurrent_executions += 1
        currently_running = True
        execution_count += 1

        # Block until event is set
        await event.wait()

        currently_running = False

    try:
        # Schedule with 50ms interval
        await scheduler.schedule("slow_task", slow_callback, 0.05)

        # Wait for first execution to start
        await asyncio.sleep(0.01)

        # Verify task is in running_tasks
        assert "slow_task" in scheduler.running_tasks

        # Wait for interval to fire multiple times while callback is blocked
        await asyncio.sleep(0.15)

        # Unblock the callback
        event.set()

        # Wait for callback to complete
        await asyncio.sleep(0.05)

        # Should have executed only once despite multiple intervals passing
        assert execution_count == 1
        assert concurrent_executions == 0
        assert "slow_task" not in scheduler.running_tasks

    finally:
        event.set()  # Ensure callback can complete
        scheduler.cancel_all()
        await asyncio.sleep(0.05)  # Allow cleanup


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-001")
async def test_cancel_unknown_task_raises_key_error(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that cancelling an unknown task raises KeyError.

    Verifies that attempting to cancel a non-existent task fails
    with appropriate error.
    """
    scheduler = CheckScheduler(monitoring_config)

    with pytest.raises(KeyError, match="unknown_task"):
        scheduler.cancel("unknown_task")


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-001")
async def test_schedule_with_zero_interval_raises_value_error(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that scheduling with zero interval raises ValueError.

    Verifies that invalid interval values are rejected.
    """
    scheduler = CheckScheduler(monitoring_config)

    async def callback() -> None:
        pass

    try:
        with pytest.raises(ValueError, match="interval.*positive"):
            await scheduler.schedule("test_task", callback, 0.0)

    finally:
        scheduler.cancel_all()


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-001")
async def test_schedule_with_negative_interval_raises_value_error(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that scheduling with negative interval raises ValueError.

    Verifies that negative interval values are rejected.
    """
    scheduler = CheckScheduler(monitoring_config)

    async def callback() -> None:
        pass

    try:
        with pytest.raises(ValueError, match="interval.*positive"):
            await scheduler.schedule("test_task", callback, -1.0)

    finally:
        scheduler.cancel_all()


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-002")
async def test_running_tasks_property_tracks_executing_callbacks(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that running_tasks property correctly tracks executing callbacks.

    Verifies that tasks appear in running_tasks while executing and
    are removed after completion.
    """
    scheduler = CheckScheduler(monitoring_config)
    callback_started = asyncio.Event()
    callback_complete = asyncio.Event()

    async def callback() -> None:
        callback_started.set()
        await callback_complete.wait()

    try:
        # Schedule task
        await scheduler.schedule("test_task", callback, 0.05)

        # Wait for callback to start
        await callback_started.wait()

        # Should be in running_tasks
        assert "test_task" in scheduler.running_tasks

        # Complete the callback
        callback_complete.set()

        # Wait for callback to finish
        await asyncio.sleep(0.05)

        # Should no longer be in running_tasks
        assert "test_task" not in scheduler.running_tasks

    finally:
        callback_complete.set()  # Ensure callback can complete
        scheduler.cancel_all()
        await asyncio.sleep(0.05)  # Allow cleanup


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-001")
async def test_schedule_replaces_existing_task(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that scheduling a task with same name replaces existing task.

    Verifies that re-scheduling stops the old task and starts a new one.
    """
    scheduler = CheckScheduler(monitoring_config)
    first_count = 0
    second_count = 0

    async def first_callback() -> None:
        nonlocal first_count
        first_count += 1

    async def second_callback() -> None:
        nonlocal second_count
        second_count += 1

    try:
        # Schedule first task
        await scheduler.schedule("test_task", first_callback, 0.05)
        await asyncio.sleep(0.06)
        assert first_count >= 1

        # Re-schedule with different callback
        await scheduler.schedule("test_task", second_callback, 0.05)
        first_count_after_reschedule = first_count

        # Wait for new task to execute
        await asyncio.sleep(0.15)

        # First callback should not execute again
        assert first_count == first_count_after_reschedule
        # Second callback should execute
        assert second_count >= 1

    finally:
        scheduler.cancel_all()


@pytest.mark.asyncio
@pytest.mark.requirement("3D-FR-002")
async def test_callback_exception_does_not_stop_scheduling(
    monitoring_config: MonitoringConfig,
) -> None:
    """Test that callback exceptions don't stop the scheduler.

    Verifies that if a callback raises an exception, the scheduler
    continues to execute it on subsequent intervals.
    """
    scheduler = CheckScheduler(monitoring_config)
    call_count = 0

    async def failing_callback() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated error")

    try:
        # Schedule task that fails on first call
        await scheduler.schedule("failing_task", failing_callback, 0.05)

        # Wait for multiple intervals
        await asyncio.sleep(0.15)

        # Should have been called multiple times despite first failure
        assert call_count >= 2

    finally:
        scheduler.cancel_all()
