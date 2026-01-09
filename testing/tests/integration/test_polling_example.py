"""Example integration tests demonstrating polling utilities.

This module shows the correct way to wait for async operations in tests,
using polling utilities instead of hardcoded time.sleep() calls.

DO NOT use time.sleep() in tests. Use the polling utilities instead:
- wait_for_condition: For arbitrary conditions
- wait_for_service: For K8s service readiness

Example of WRONG approach (DO NOT DO THIS):
    import time
    def test_bad_example():
        start_service()
        time.sleep(5)  # BAD: race condition, wastes time
        assert service.is_ready()

Example of CORRECT approach:
    from testing.fixtures.polling import wait_for_condition
    def test_good_example():
        start_service()
        assert wait_for_condition(
            lambda: service.is_ready(),
            timeout=30.0,
            description="service readiness"
        )
"""

from __future__ import annotations

import pytest

from testing.fixtures.polling import (
    PollingConfig,
    PollingTimeoutError,
    wait_for_condition,
)


class TestPollingExamples:
    """Example tests demonstrating polling utility usage."""

    @pytest.mark.requirement("9c-FR-017")
    def test_wait_for_condition_success(self) -> None:
        """Demonstrate wait_for_condition with immediate success.

        The condition returns True immediately, so no polling is needed.
        This shows the simplest usage pattern.
        """
        call_count = 0

        def condition() -> bool:
            nonlocal call_count
            call_count += 1
            return True  # Immediate success

        result = wait_for_condition(
            condition,
            timeout=5.0,
            description="immediate condition",
        )

        assert result is True
        assert call_count == 1

    @pytest.mark.requirement("9c-FR-017")
    def test_wait_for_condition_delayed_success(self) -> None:
        """Demonstrate wait_for_condition with delayed success.

        The condition returns False initially, then True after a few calls.
        This simulates an async operation completing.
        """
        call_count = 0

        def condition() -> bool:
            nonlocal call_count
            call_count += 1
            # Return True after 3 calls
            return call_count >= 3

        result = wait_for_condition(
            condition,
            timeout=5.0,
            interval=0.1,  # Fast polling for test speed
            description="delayed condition",
        )

        assert result is True
        assert call_count >= 3

    @pytest.mark.requirement("9c-FR-017")
    def test_wait_for_condition_timeout_raises(self) -> None:
        """Demonstrate timeout behavior when raise_on_timeout=True.

        When the condition never becomes True, PollingTimeoutError is raised.
        This is the default behavior for fail-fast testing.
        """

        def never_true() -> bool:
            return False

        with pytest.raises(PollingTimeoutError) as exc_info:
            wait_for_condition(
                never_true,
                timeout=0.3,  # Short timeout for test speed
                interval=0.1,
                description="never-true condition",
            )

        assert "never-true condition" in str(exc_info.value)
        assert exc_info.value.timeout == pytest.approx(0.3)

    @pytest.mark.requirement("9c-FR-017")
    def test_wait_for_condition_timeout_returns_false(self) -> None:
        """Demonstrate timeout behavior when raise_on_timeout=False.

        When the condition never becomes True, False is returned instead
        of raising an exception. Use this when you want to handle timeout
        gracefully.
        """

        def never_true() -> bool:
            return False

        result = wait_for_condition(
            never_true,
            timeout=0.3,
            interval=0.1,
            description="never-true condition",
            raise_on_timeout=False,
        )

        assert result is False

    @pytest.mark.requirement("9c-FR-017")
    def test_wait_for_condition_exception_handling(self) -> None:
        """Demonstrate exception handling during polling.

        If the condition raises an exception, polling continues until timeout.
        The last exception is included in the timeout error for debugging.
        """
        call_count = 0

        def flaky_condition() -> bool:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Service not ready")
            return True

        result = wait_for_condition(
            flaky_condition,
            timeout=5.0,
            interval=0.1,
            description="flaky service",
        )

        assert result is True
        assert call_count >= 3

    @pytest.mark.requirement("9c-FR-017")
    def test_polling_config_usage(self) -> None:
        """Demonstrate PollingConfig for reusable configuration.

        Use PollingConfig when you have consistent polling settings
        across multiple wait operations.
        """
        config = PollingConfig(
            timeout=5.0,
            interval=0.2,
            description="configured operation",
        )

        # Config is immutable (frozen=True)
        with pytest.raises(Exception):  # noqa: B017
            config.timeout = 10.0  # type: ignore[misc]

        assert config.timeout == pytest.approx(5.0)
        assert config.interval == pytest.approx(0.2)

    @pytest.mark.requirement("9c-FR-017")
    def test_polling_pattern_async_job(self) -> None:
        """Demonstrate polling pattern for async job completion.

        This pattern is common when waiting for K8s Jobs, background tasks,
        or database operations to complete.
        """

        # Simulate an async job
        class MockJob:
            def __init__(self) -> None:
                self._status = "pending"
                self._check_count = 0

            def status(self) -> str:
                self._check_count += 1
                if self._check_count >= 2:
                    self._status = "complete"
                return self._status

        job = MockJob()

        # Wait for job completion using polling
        result = wait_for_condition(
            lambda: job.status() == "complete",
            timeout=5.0,
            interval=0.1,
            description="job completion",
        )

        assert result is True
        assert job._status == "complete"

    @pytest.mark.requirement("9c-FR-017")
    def test_polling_pattern_database_ready(self) -> None:
        """Demonstrate polling pattern for database readiness.

        Use this pattern when waiting for a database to be ready
        after deployment or restart.
        """

        # Simulate database becoming ready
        class MockDatabase:
            def __init__(self) -> None:
                self._ready = False
                self._ping_count = 0

            def ping(self) -> bool:
                self._ping_count += 1
                if self._ping_count >= 3:
                    self._ready = True
                return self._ready

        db = MockDatabase()

        # Wait for database to be ready
        result = wait_for_condition(
            db.ping,
            timeout=5.0,
            interval=0.1,
            description="database readiness",
        )

        assert result is True
        assert db._ready is True
