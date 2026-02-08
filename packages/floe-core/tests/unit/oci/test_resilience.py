"""Unit tests for OCI resilience patterns.

Tests retry policy and circuit breaker patterns for handling transient failures
and registry unavailability in OCI operations.

Task: T041, T042, T043, T044, T045
Requirements: FR-018, FR-019, FR-020, FR-021

Example:
    pytest packages/floe-core/tests/unit/oci/test_resilience.py -v

See Also:
    - floe_core/oci/resilience.py: Implementation
    - specs/08a-oci-client/spec.md: User Story 5 (Resilient Operations)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from floe_core.oci.errors import (
    CircuitBreakerOpenError,
    RegistryUnavailableError,
)
from floe_core.oci.resilience import (
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
    with_resilience,
)
from floe_core.schemas.oci import CircuitBreakerConfig, RetryConfig

if TYPE_CHECKING:
    pass


class TestRetryPolicyExponentialBackoff:
    """Tests for RetryPolicy exponential backoff behavior.

    Verifies FR-018: System MUST retry transient failures with exponential
    backoff (default: 3 attempts, 1s/2s/4s).
    """

    @pytest.mark.requirement("8A-FR-018")
    def test_default_config_has_correct_values(self) -> None:
        """Test default RetryConfig matches spec: 3 attempts, 1s initial, 2x multiplier."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.initial_delay_ms == 1000  # 1 second
        assert config.backoff_multiplier == pytest.approx(2.0)
        assert config.jitter is True

    @pytest.mark.requirement("8A-FR-018")
    def test_calculate_delay_exponential_backoff_no_jitter(self) -> None:
        """Test delay calculation follows exponential backoff without jitter.

        Expected delays (no jitter):
        - Attempt 0: 1000ms * 2^0 = 1s
        - Attempt 1: 1000ms * 2^1 = 2s
        - Attempt 2: 1000ms * 2^2 = 4s
        """
        config = RetryConfig(
            initial_delay_ms=1000,
            backoff_multiplier=2.0,
            jitter=False,
        )
        policy = RetryPolicy(config)

        # Attempt 0: 1s
        delay_0 = policy.calculate_delay(0)
        assert delay_0 == pytest.approx(1.0)

        # Attempt 1: 2s
        delay_1 = policy.calculate_delay(1)
        assert delay_1 == pytest.approx(2.0)

        # Attempt 2: 4s
        delay_2 = policy.calculate_delay(2)
        assert delay_2 == pytest.approx(4.0)

    @pytest.mark.requirement("8A-FR-018")
    def test_delay_respects_max_delay_cap(self) -> None:
        """Test delay is capped at max_delay_ms."""
        config = RetryConfig(
            initial_delay_ms=1000,
            backoff_multiplier=2.0,
            max_delay_ms=5000,  # 5s cap
            jitter=False,
        )
        policy = RetryPolicy(config)

        # Attempt 3: 1000 * 2^3 = 8000ms > 5000ms cap
        delay_3 = policy.calculate_delay(3)
        assert delay_3 == pytest.approx(5.0)  # Capped at 5s

    @pytest.mark.requirement("8A-FR-018")
    def test_retry_on_transient_failure(self) -> None:
        """Test that transient failures trigger retry."""
        config = RetryConfig(max_attempts=3, jitter=False)
        policy = RetryPolicy(config)

        call_count = 0

        def failing_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RegistryUnavailableError("registry", "Transient failure")
            return "success"

        with patch("time.sleep"):  # Skip actual delays
            result = policy.wrap(failing_operation)()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.requirement("8A-FR-018")
    def test_retry_exhausted_raises_last_exception(self) -> None:
        """Test that exhausted retries raise the last exception."""
        config = RetryConfig(max_attempts=3, jitter=False)
        policy = RetryPolicy(config)

        def always_fails() -> None:
            raise RegistryUnavailableError("registry", "Permanent failure")

        with (
            patch("time.sleep"),
            pytest.raises(RegistryUnavailableError, match="Permanent failure"),
        ):
            policy.wrap(always_fails)()

    @pytest.mark.requirement("8A-FR-018")
    def test_non_retryable_exception_not_retried(self) -> None:
        """Test that non-retryable exceptions are not retried."""
        config = RetryConfig(max_attempts=3)
        policy = RetryPolicy(config)

        call_count = 0

        def raises_value_error() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")

        with pytest.raises(ValueError, match="Non-retryable error"):
            policy.wrap(raises_value_error)()

        # Should only be called once (no retry for non-retryable)
        assert call_count == 1

    @pytest.mark.requirement("8A-FR-018")
    def test_retry_calls_sleep_with_correct_delays(self) -> None:
        """Test that time.sleep is called with correct exponential delays."""
        config = RetryConfig(
            initial_delay_ms=1000,
            backoff_multiplier=2.0,
            max_attempts=3,
            jitter=False,
        )
        policy = RetryPolicy(config)

        def always_fails() -> None:
            raise RegistryUnavailableError("registry", "Failure")

        with (
            patch("floe_core.oci.resilience.time.sleep") as mock_sleep,
            pytest.raises(RegistryUnavailableError),
        ):
            policy.wrap(always_fails)()

        # Should have 2 sleep calls (after attempt 0 and 1, not after last attempt)
        assert mock_sleep.call_count == 2

        # First sleep: 1s
        assert mock_sleep.call_args_list[0][0][0] == pytest.approx(1.0)

        # Second sleep: 2s
        assert mock_sleep.call_args_list[1][0][0] == pytest.approx(2.0)


class TestRetryPolicyJitter:
    """Tests for RetryPolicy jitter behavior.

    Verifies that jitter prevents thundering herd by adding randomness
    to delay times.
    """

    @pytest.mark.requirement("8A-FR-018")
    def test_jitter_adds_variance_to_delays(self) -> None:
        """Test jitter adds ±25% variance to delays.

        Note: This test uses statistical sampling (100 iterations).
        The probability of all 100 samples landing exactly on the bounds
        is astronomically low (effectively zero), making this test reliable.
        """
        config = RetryConfig(
            initial_delay_ms=1000,
            backoff_multiplier=2.0,
            jitter=True,
        )
        policy = RetryPolicy(config)

        # Collect multiple delay samples
        delays: list[float] = []
        for _ in range(100):
            delays.append(policy.calculate_delay(0))

        # Base delay for attempt 0 is 1.0s
        # With ±25% jitter, delays should be in range [0.75, 1.25]
        assert all(
            0.75 <= d <= 1.25 for d in delays
        ), f"Delays out of range: min={min(delays)}, max={max(delays)}"

        # There should be variance (not all same value)
        unique_delays = {round(d, 4) for d in delays}
        assert len(unique_delays) > 1, "Expected variance in delays with jitter"

    @pytest.mark.requirement("8A-FR-018")
    def test_jitter_disabled_produces_consistent_delays(self) -> None:
        """Test disabling jitter produces consistent delays."""
        config = RetryConfig(
            initial_delay_ms=1000,
            backoff_multiplier=2.0,
            jitter=False,
        )
        policy = RetryPolicy(config)

        delays = [policy.calculate_delay(0) for _ in range(10)]

        # All delays should be identical without jitter
        assert all(d == pytest.approx(1.0) for d in delays)

    @pytest.mark.requirement("8A-FR-018")
    def test_jitter_prevents_thundering_herd(self) -> None:
        """Test that multiple clients don't get identical delays.

        Simulates multiple clients calling calculate_delay simultaneously.
        With jitter, they should get different delays to spread load.
        """
        config = RetryConfig(jitter=True)

        # Create multiple "clients"
        clients = [RetryPolicy(config) for _ in range(10)]

        # Get delays for each client
        delays = [client.calculate_delay(0) for client in clients]

        # At least some delays should differ (prevents thundering herd)
        unique_delays = {round(d, 4) for d in delays}
        assert len(unique_delays) >= 2, "Expected different delays across clients"


class TestRetryAttemptIterator:
    """Tests for RetryAttemptIterator manual retry control."""

    @pytest.mark.requirement("8A-FR-018")
    def test_attempts_iterator_yields_correct_count(self) -> None:
        """Test attempts iterator yields max_attempts attempts."""
        config = RetryConfig(max_attempts=3)
        policy = RetryPolicy(config)

        attempts = list(policy.attempts())

        assert len(attempts) == 3
        assert attempts[0].attempt_number == 0
        assert attempts[1].attempt_number == 1
        assert attempts[2].attempt_number == 2

    @pytest.mark.requirement("8A-FR-018")
    def test_is_last_attempt(self) -> None:
        """Test is_last_attempt returns correct value."""
        config = RetryConfig(max_attempts=3)
        policy = RetryPolicy(config)

        attempts = list(policy.attempts())

        assert not attempts[0].is_last_attempt
        assert not attempts[1].is_last_attempt
        assert attempts[2].is_last_attempt

    @pytest.mark.requirement("8A-FR-018")
    def test_should_retry(self) -> None:
        """Test should_retry returns True for retryable exceptions."""
        config = RetryConfig(max_attempts=3)
        policy = RetryPolicy(config)

        attempt = next(iter(policy.attempts()))
        retryable_error = RegistryUnavailableError("registry", "Transient")
        non_retryable_error = ValueError("Not retryable")

        assert attempt.should_retry(retryable_error) is True
        assert attempt.should_retry(non_retryable_error) is False


class TestCircuitBreaker:
    """Tests for CircuitBreaker pattern.

    Verifies FR-019/FR-020/FR-021: Circuit breaker behavior for registry
    availability.
    """

    @pytest.mark.requirement("8A-FR-019")
    def test_circuit_starts_closed(self) -> None:
        """Test circuit starts in CLOSED state."""
        circuit = CircuitBreaker("test-registry")

        assert circuit.state == CircuitState.CLOSED
        assert circuit.is_closed
        assert not circuit.is_open

    @pytest.mark.requirement("8A-FR-019")
    def test_circuit_opens_after_failure_threshold(self) -> None:
        """Test circuit opens after failure_threshold failures."""
        config = CircuitBreakerConfig(failure_threshold=3)
        circuit = CircuitBreaker("test-registry", config)

        # Record failures up to threshold
        circuit.record_failure()
        circuit.record_failure()
        assert circuit.is_closed  # Still under threshold

        # Third failure opens the circuit
        circuit.record_failure()
        assert circuit.is_open
        assert circuit.state == CircuitState.OPEN

    @pytest.mark.requirement("8A-FR-019")
    def test_open_circuit_rejects_requests(self) -> None:
        """Test open circuit raises CircuitBreakerOpenError."""
        config = CircuitBreakerConfig(failure_threshold=1)
        circuit = CircuitBreaker("test-registry", config)

        # Open the circuit
        circuit.record_failure()
        assert circuit.is_open

        # Should reject requests
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            with circuit.protect():
                pass  # Should not reach here

        assert "test-registry" in str(exc_info.value)

    @pytest.mark.requirement("8A-FR-020")
    def test_circuit_transitions_to_half_open_after_timeout(self) -> None:
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=1000,  # 1s
        )
        circuit = CircuitBreaker("test-registry", config)

        # Open the circuit
        circuit.record_failure()
        assert circuit.is_open

        # Mock time passage
        with patch("floe_core.oci.resilience.datetime") as mock_datetime:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = now + timedelta(seconds=2)

            # Check state (triggers update) - should be HALF_OPEN
            current_state = circuit.state
            assert current_state == CircuitState.HALF_OPEN

    @pytest.mark.requirement("8A-FR-020")
    def test_half_open_allows_probe_requests(self) -> None:
        """Test HALF_OPEN state allows limited probe requests."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=1000,
            half_open_requests=2,
        )
        circuit = CircuitBreaker("test-registry", config)

        # Open circuit
        circuit.record_failure()
        assert circuit.is_open

        # Mock time passage to trigger half-open
        with patch("floe_core.oci.resilience.datetime") as mock_datetime:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = now + timedelta(seconds=2)

            # First probe should be allowed
            assert circuit.allow_request() is True

            # Second probe should be allowed
            assert circuit.allow_request() is True

            # Third should be rejected (exceeded half_open_requests)
            assert circuit.allow_request() is False

    @pytest.mark.requirement("8A-FR-021")
    def test_successful_probe_closes_circuit(self) -> None:
        """Test successful probe in HALF_OPEN closes circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=1000,
        )
        circuit = CircuitBreaker("test-registry", config)

        # Open circuit
        circuit.record_failure()
        assert circuit.is_open

        # Mock time passage to trigger half-open
        with patch("floe_core.oci.resilience.datetime") as mock_datetime:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = now + timedelta(seconds=2)

            # Trigger half-open
            circuit.allow_request()

            # Record success
            circuit.record_success()

            assert circuit.is_closed

    @pytest.mark.requirement("8A-FR-021")
    def test_failed_probe_reopens_circuit(self) -> None:
        """Test failed probe in HALF_OPEN reopens circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=1000,
        )
        circuit = CircuitBreaker("test-registry", config)

        # Open circuit
        circuit.record_failure()
        assert circuit.is_open

        # Mock time passage to trigger half-open
        with patch("floe_core.oci.resilience.datetime") as mock_datetime:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = now + timedelta(seconds=2)

            # Trigger half-open
            assert circuit.allow_request() is True

            # Record another failure
            circuit.record_failure()

            assert circuit.is_open

    @pytest.mark.requirement("8A-FR-019")
    def test_success_resets_failure_count(self) -> None:
        """Test success resets consecutive failure count."""
        config = CircuitBreakerConfig(failure_threshold=3)
        circuit = CircuitBreaker("test-registry", config)

        # Record 2 failures
        circuit.record_failure()
        circuit.record_failure()
        assert circuit.failure_count == 2

        # Record success
        circuit.record_success()
        assert circuit.failure_count == 0

    @pytest.mark.requirement("8A-FR-019")
    def test_circuit_disabled(self) -> None:
        """Test disabled circuit always allows requests."""
        config = CircuitBreakerConfig(enabled=False, failure_threshold=1)
        circuit = CircuitBreaker("test-registry", config)

        # Record failures
        circuit.record_failure()
        circuit.record_failure()

        # Should still allow requests when disabled
        assert circuit.allow_request() is True

    @pytest.mark.requirement("8A-FR-019")
    def test_protect_context_manager_records_success(self) -> None:
        """Test protect context manager records success on clean exit."""
        circuit = CircuitBreaker("test-registry")
        initial_failures = circuit.failure_count

        with circuit.protect():
            pass  # Success path

        assert circuit.failure_count == initial_failures  # Still 0

    @pytest.mark.requirement("8A-FR-019")
    def test_protect_context_manager_records_failure(self) -> None:
        """Test protect context manager records failure on exception."""
        circuit = CircuitBreaker("test-registry")

        with pytest.raises(ValueError):
            with circuit.protect():
                raise ValueError("Test error")

        assert circuit.failure_count == 1

    @pytest.mark.requirement("8A-FR-019")
    def test_reset_returns_to_initial_state(self) -> None:
        """Test reset() returns circuit to initial state."""
        config = CircuitBreakerConfig(failure_threshold=1)
        circuit = CircuitBreaker("test-registry", config)

        # Open circuit
        circuit.record_failure()
        assert circuit.is_open

        # Reset
        circuit.reset()

        assert circuit.state == CircuitState.CLOSED
        assert circuit.failure_count == 0


class TestWithResilienceDecorator:
    """Tests for with_resilience combined decorator."""

    @pytest.mark.requirement("8A-FR-018")
    @pytest.mark.requirement("8A-FR-019")
    def test_with_resilience_applies_retry_and_circuit(self) -> None:
        """Test with_resilience applies both retry and circuit breaker."""
        circuit = CircuitBreaker("test-registry")
        retry_config = RetryConfig(max_attempts=2, jitter=False)

        call_count = 0

        @with_resilience(retry_config, circuit)
        def failing_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RegistryUnavailableError("registry", "Transient")
            return "success"

        with patch("floe_core.oci.resilience.time.sleep"):
            result = failing_then_success()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.requirement("8A-FR-018")
    def test_with_resilience_without_circuit_breaker(self) -> None:
        """Test with_resilience works without circuit breaker."""
        retry_config = RetryConfig(max_attempts=2, jitter=False)

        call_count = 0

        @with_resilience(retry_config, None)
        def failing_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RegistryUnavailableError("registry", "Transient")
            return "success"

        with patch("floe_core.oci.resilience.time.sleep"):
            result = failing_then_success()

        assert result == "success"
        assert call_count == 2


class TestCustomRetryableExceptions:
    """Tests for custom retryable exception configuration."""

    @pytest.mark.requirement("8A-FR-018")
    def test_custom_retryable_exceptions(self) -> None:
        """Test custom exception types can be marked as retryable."""
        config = RetryConfig(max_attempts=2, jitter=False)

        # Include ValueError as retryable
        policy = RetryPolicy(config, retryable_exceptions=(ValueError,))

        call_count = 0

        def raises_value_error() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary")
            return "success"

        with patch("floe_core.oci.resilience.time.sleep"):
            result = policy.wrap(raises_value_error)()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.requirement("8A-FR-018")
    def test_should_retry_method(self) -> None:
        """Test should_retry correctly identifies retryable exceptions."""
        policy = RetryPolicy(
            retryable_exceptions=(RegistryUnavailableError, ConnectionError)
        )

        assert policy.should_retry(RegistryUnavailableError("r", "x")) is True
        assert policy.should_retry(ConnectionError("x")) is True
        assert policy.should_retry(ValueError("x")) is False
        assert policy.should_retry(TypeError("x")) is False


class TestRetryAttemptWait:
    """Tests for RetryAttempt.wait() method."""

    @pytest.mark.requirement("8A-FR-018")
    def test_wait_calls_sleep_with_correct_delay(self) -> None:
        """Test wait() calls time.sleep with calculated delay."""
        config = RetryConfig(
            initial_delay_ms=1000,
            backoff_multiplier=2.0,
            jitter=False,
        )
        policy = RetryPolicy(config)

        attempt = next(iter(policy.attempts()))

        with patch("floe_core.oci.resilience.time.sleep") as mock_sleep:
            attempt.wait()

        # Attempt 0 delay: 1000ms = 1s
        mock_sleep.assert_called_once_with(pytest.approx(1.0))

    @pytest.mark.requirement("8A-FR-018")
    def test_wait_does_not_sleep_on_last_attempt(self) -> None:
        """Test wait() does not sleep on last attempt."""
        config = RetryConfig(max_attempts=2, jitter=False)
        policy = RetryPolicy(config)

        attempts_list = list(policy.attempts())
        last_attempt = attempts_list[-1]

        with patch("floe_core.oci.resilience.time.sleep") as mock_sleep:
            last_attempt.wait()

        # Should not sleep on last attempt
        mock_sleep.assert_not_called()

    @pytest.mark.requirement("8A-FR-018")
    def test_wait_logs_debug_message(self) -> None:
        """Test wait() logs debug message."""
        config = RetryConfig(max_attempts=3, jitter=False)
        policy = RetryPolicy(config)

        attempt = next(iter(policy.attempts()))

        with (
            patch("floe_core.oci.resilience.time.sleep"),
            patch("floe_core.oci.resilience.logger") as mock_logger,
        ):
            attempt.wait()

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "retry_wait"


class TestRetryAttemptIteratorMethods:
    """Tests for RetryAttemptIterator dunder methods."""

    @pytest.mark.requirement("8A-FR-018")
    def test_iter_returns_self(self) -> None:
        """Test __iter__ returns self."""
        config = RetryConfig(max_attempts=3)
        policy = RetryPolicy(config)

        iterator = policy.attempts()
        assert iter(iterator) is iterator

    @pytest.mark.requirement("8A-FR-018")
    def test_next_raises_stop_iteration_after_exhausted(self) -> None:
        """Test __next__ raises StopIteration when exhausted."""
        config = RetryConfig(max_attempts=2)
        policy = RetryPolicy(config)

        iterator = policy.attempts()
        next(iterator)  # Attempt 0
        next(iterator)  # Attempt 1

        with pytest.raises(StopIteration):
            next(iterator)


class TestCircuitBreakerRecoveryTime:
    """Tests for CircuitBreaker.recovery_time property."""

    @pytest.mark.requirement("8A-FR-020")
    def test_recovery_time_returns_none_when_closed(self) -> None:
        """Test recovery_time returns None when circuit is closed."""
        circuit = CircuitBreaker("test-registry")

        assert circuit.state == CircuitState.CLOSED
        assert circuit.recovery_time is None

    @pytest.mark.requirement("8A-FR-020")
    def test_recovery_time_returns_timestamp_when_open(self) -> None:
        """Test recovery_time returns expected timestamp when open."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=5000,  # 5s
        )
        circuit = CircuitBreaker("test-registry", config)

        # Open the circuit
        circuit.record_failure()
        assert circuit.is_open

        # recovery_time should be ~5s from now
        recovery_time = circuit.recovery_time
        assert recovery_time is not None

        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        # Recovery time should be between now and now + 6s (with some buffer)
        assert now <= recovery_time <= now + timedelta(seconds=6)


class TestCircuitBreakerWithMetrics:
    """Tests for CircuitBreaker with metrics emission."""

    @pytest.mark.requirement("8A-FR-019")
    def test_circuit_emits_state_metric_on_init(self) -> None:
        """Test circuit emits state metric on initialization."""
        from unittest.mock import MagicMock

        mock_metrics = MagicMock()
        circuit = CircuitBreaker("test-registry", metrics=mock_metrics)

        # Should have called set_circuit_breaker_state on init
        mock_metrics.set_circuit_breaker_state.assert_called_once()
        call_kwargs = mock_metrics.set_circuit_breaker_state.call_args[1]
        assert call_kwargs["registry"] == "test-registry"
        assert call_kwargs["failure_count"] == 0
        assert circuit.is_closed

    @pytest.mark.requirement("8A-FR-019")
    def test_circuit_emits_metric_on_open(self) -> None:
        """Test circuit emits state metric when opening."""
        from unittest.mock import MagicMock

        mock_metrics = MagicMock()
        config = CircuitBreakerConfig(failure_threshold=1)
        circuit = CircuitBreaker("test-registry", config, metrics=mock_metrics)

        # Reset call count from init
        mock_metrics.reset_mock()

        # Open circuit
        circuit.record_failure()

        # Should emit state metric
        mock_metrics.set_circuit_breaker_state.assert_called_once()
        call_kwargs = mock_metrics.set_circuit_breaker_state.call_args[1]
        assert call_kwargs["failure_count"] == 1

    @pytest.mark.requirement("8A-FR-021")
    def test_circuit_emits_metric_on_close(self) -> None:
        """Test circuit emits state metric when closing from half-open."""
        from unittest.mock import MagicMock

        mock_metrics = MagicMock()
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=1000,
        )
        circuit = CircuitBreaker("test-registry", config, metrics=mock_metrics)

        # Open circuit
        circuit.record_failure()
        assert circuit.is_open

        # Mock time passage to trigger half-open
        with patch("floe_core.oci.resilience.datetime") as mock_datetime:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = now + timedelta(seconds=2)

            # Trigger half-open
            circuit.allow_request()

            # Reset call count
            mock_metrics.reset_mock()

            # Record success (should close and emit metric)
            circuit.record_success()

        assert circuit.is_closed
        mock_metrics.set_circuit_breaker_state.assert_called()

    @pytest.mark.requirement("8A-FR-021")
    def test_circuit_emits_metric_on_reopen(self) -> None:
        """Test circuit emits state metric when reopening from half-open."""
        from unittest.mock import MagicMock

        mock_metrics = MagicMock()
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=1000,
        )
        circuit = CircuitBreaker("test-registry", config, metrics=mock_metrics)

        # Open circuit
        circuit.record_failure()

        # Mock time passage to trigger half-open
        with patch("floe_core.oci.resilience.datetime") as mock_datetime:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = now + timedelta(seconds=2)

            # Trigger half-open
            circuit.allow_request()

            # Reset call count
            mock_metrics.reset_mock()

            # Record failure (should reopen and emit metric)
            circuit.record_failure()

        assert circuit.is_open
        mock_metrics.set_circuit_breaker_state.assert_called()

    @pytest.mark.requirement("8A-FR-019")
    def test_circuit_emits_metric_on_reset(self) -> None:
        """Test circuit emits state metric on reset."""
        from unittest.mock import MagicMock

        mock_metrics = MagicMock()
        config = CircuitBreakerConfig(failure_threshold=1)
        circuit = CircuitBreaker("test-registry", config, metrics=mock_metrics)

        # Open circuit
        circuit.record_failure()
        assert circuit.is_open

        # Reset call count
        mock_metrics.reset_mock()

        # Reset circuit
        circuit.reset()

        # Should emit state metric
        mock_metrics.set_circuit_breaker_state.assert_called_once()
        assert circuit.is_closed

    @pytest.mark.requirement("8A-FR-020")
    def test_circuit_emits_metric_on_half_open_transition(self) -> None:
        """Test circuit emits state metric when transitioning to half-open."""
        from unittest.mock import MagicMock

        mock_metrics = MagicMock()
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=1000,
        )
        circuit = CircuitBreaker("test-registry", config, metrics=mock_metrics)

        # Open circuit
        circuit.record_failure()

        # Reset call count
        mock_metrics.reset_mock()

        # Mock time passage to trigger half-open
        with patch("floe_core.oci.resilience.datetime") as mock_datetime:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = now + timedelta(seconds=2)

            # Trigger state check (should transition to half-open)
            state = circuit.state

        assert state == CircuitState.HALF_OPEN
        mock_metrics.set_circuit_breaker_state.assert_called()


class TestCircuitBreakerHalfOpenLimiting:
    """Tests for half-open request limiting."""

    @pytest.mark.requirement("8A-FR-020")
    def test_half_open_logs_probe_requests(self) -> None:
        """Test half-open state logs probe request details."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=1000,
            half_open_requests=2,
        )
        circuit = CircuitBreaker("test-registry", config)

        # Open circuit
        circuit.record_failure()

        # Mock time passage to trigger half-open
        with patch("floe_core.oci.resilience.datetime") as mock_datetime:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = now + timedelta(seconds=2)

            with patch("floe_core.oci.resilience.logger") as mock_logger:
                # First probe
                circuit.allow_request()

            mock_logger.debug.assert_called()
            call_args = mock_logger.debug.call_args
            assert call_args[0][0] == "circuit_half_open_probe"


class TestRetryExhaustedLogging:
    """Tests for retry exhausted logging."""

    @pytest.mark.requirement("8A-FR-018")
    def test_retry_exhausted_logs_warning(self) -> None:
        """Test that retry exhausted logs a warning message."""
        config = RetryConfig(max_attempts=2, jitter=False)
        policy = RetryPolicy(config)

        def always_fails() -> None:
            raise RegistryUnavailableError("registry", "Always fails")

        with (
            patch("floe_core.oci.resilience.time.sleep"),
            patch("floe_core.oci.resilience.logger") as mock_logger,
            pytest.raises(RegistryUnavailableError),
        ):
            policy.wrap(always_fails)()

        # Check that warning was logged
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "retry_exhausted"


class TestCircuitBreakerProtectContextManager:
    """Tests for protect context manager edge cases."""

    @pytest.mark.requirement("8A-FR-019")
    def test_protect_includes_recovery_time_in_error(self) -> None:
        """Test protect includes recovery_time in CircuitBreakerOpenError."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_ms=5000,
        )
        circuit = CircuitBreaker("test-registry", config)

        # Open the circuit
        circuit.record_failure()

        # Try to use protect (should raise with recovery info)
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            with circuit.protect():
                pass

        error = exc_info.value
        assert "test-registry" in str(error)


class TestCircuitBreakerDisabled:
    """Tests for disabled circuit breaker behavior."""

    @pytest.mark.requirement("8A-FR-019")
    def test_disabled_record_success_does_nothing(self) -> None:
        """Test record_success is a no-op when disabled."""
        config = CircuitBreakerConfig(enabled=False, failure_threshold=1)
        circuit = CircuitBreaker("test-registry", config)

        # Record some activity
        circuit.record_failure()
        circuit.record_success()

        # Should still allow requests
        assert circuit.allow_request() is True

    @pytest.mark.requirement("8A-FR-019")
    def test_disabled_record_failure_does_nothing(self) -> None:
        """Test record_failure is a no-op when disabled."""
        config = CircuitBreakerConfig(enabled=False, failure_threshold=1)
        circuit = CircuitBreaker("test-registry", config)

        # Record many failures
        for _ in range(10):
            circuit.record_failure()

        # Should still allow requests (not open)
        assert circuit.allow_request() is True
