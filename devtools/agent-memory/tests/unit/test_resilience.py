"""Unit tests for resilience module.

Tests for:
- Exponential backoff with jitter calculation
- Circuit breaker state transitions
- Retry configuration

Requirements Covered:
- FR-008: SDK error handling
- SC-002: 80%+ unit test coverage
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from agent_memory.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryConfig,
    calculate_backoff,
    parse_retry_after,
)

if TYPE_CHECKING:
    pass


class TestCalculateBackoff:
    """Tests for exponential backoff calculation."""

    @pytest.mark.requirement("FR-008")
    def test_backoff_increases_exponentially(self) -> None:
        """Test that backoff increases with each attempt."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)

        delay_0 = calculate_backoff(0, config)
        delay_1 = calculate_backoff(1, config)
        delay_2 = calculate_backoff(2, config)

        assert delay_0 == pytest.approx(1.0)  # 1 * 2^0 = 1
        assert delay_1 == pytest.approx(2.0)  # 1 * 2^1 = 2
        assert delay_2 == pytest.approx(4.0)  # 1 * 2^2 = 4

    @pytest.mark.requirement("FR-008")
    def test_backoff_respects_max_delay(self) -> None:
        """Test that backoff is capped at max_delay."""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, jitter=False)

        # Attempt 10 would give 1024s without cap
        delay = calculate_backoff(10, config)

        assert delay == pytest.approx(5.0)

    @pytest.mark.requirement("FR-008")
    def test_backoff_with_jitter_varies(self) -> None:
        """Test that jitter produces varying delays."""
        config = RetryConfig(base_delay=10.0, jitter=True)

        # Get multiple delays and check they vary
        delays = [calculate_backoff(0, config) for _ in range(10)]

        # With jitter, delays should be between 0 and base_delay
        assert all(0 <= d <= 10.0 for d in delays)
        # And they shouldn't all be the same
        assert len(set(delays)) > 1

    @pytest.mark.requirement("FR-008")
    def test_backoff_default_config(self) -> None:
        """Test backoff works with default config."""
        delay = calculate_backoff(0)

        # Should use default: base_delay=2.0 with jitter
        assert 0 <= delay <= 2.0


class TestCircuitBreaker:
    """Tests for circuit breaker state machine."""

    @pytest.mark.requirement("FR-008")
    def test_initial_state_is_closed(self) -> None:
        """Test circuit breaker starts in closed state."""
        breaker = CircuitBreaker()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True

    @pytest.mark.requirement("FR-008")
    def test_opens_after_failure_threshold(self) -> None:
        """Test circuit opens after consecutive failures."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        # Record failures
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True

        # Third failure should open
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_execute() is False

    @pytest.mark.requirement("FR-008")
    def test_success_resets_failure_count(self) -> None:
        """Test that success resets failure counter."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2

        breaker.record_success()
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.requirement("FR-008")
    def test_half_open_after_recovery_timeout(self) -> None:
        """Test circuit transitions to half-open after timeout."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=30.0)
        breaker = CircuitBreaker(config)

        # Mock time.monotonic to control time flow
        mock_time = 1000.0

        def mock_monotonic() -> float:
            return mock_time

        with patch(
            "agent_memory.resilience.time.monotonic", side_effect=mock_monotonic
        ):
            # Open the circuit
            breaker.record_failure()
            assert breaker.state == CircuitState.OPEN
            assert breaker.can_execute() is False

        # Advance time past recovery timeout
        mock_time = 1031.0  # 31 seconds later (> 30s recovery_timeout)

        with patch("agent_memory.resilience.time.monotonic", return_value=mock_time):
            # Should now be half-open
            assert breaker.can_execute() is True
            assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.requirement("FR-008")
    def test_half_open_closes_on_success(self) -> None:
        """Test circuit closes after successes in half-open."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=30.0,
            success_threshold=2,
        )
        breaker = CircuitBreaker(config)

        # Mock time.monotonic for controlled time flow
        mock_time = 1000.0

        with patch("agent_memory.resilience.time.monotonic", return_value=mock_time):
            # Open the circuit
            breaker.record_failure()

        # Advance time past recovery timeout
        mock_time = 1031.0

        with patch("agent_memory.resilience.time.monotonic", return_value=mock_time):
            breaker.can_execute()  # Triggers half-open
            assert breaker.state == CircuitState.HALF_OPEN

            breaker.record_success()
            assert breaker.state == CircuitState.HALF_OPEN  # Need 2 successes

            breaker.record_success()
            assert breaker.state == CircuitState.CLOSED

    @pytest.mark.requirement("FR-008")
    def test_half_open_reopens_on_failure(self) -> None:
        """Test circuit reopens if failure during half-open."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=30.0)
        breaker = CircuitBreaker(config)

        # Mock time.monotonic for controlled time flow
        mock_time = 1000.0

        with patch("agent_memory.resilience.time.monotonic", return_value=mock_time):
            # Open the circuit
            breaker.record_failure()

        # Advance time past recovery timeout
        mock_time = 1031.0

        with patch("agent_memory.resilience.time.monotonic", return_value=mock_time):
            breaker.can_execute()  # Triggers half-open
            assert breaker.state == CircuitState.HALF_OPEN

            # Failure in half-open should reopen
            breaker.record_failure()
            assert breaker.state == CircuitState.OPEN

    @pytest.mark.requirement("FR-008")
    def test_reset_returns_to_initial_state(self) -> None:
        """Test reset clears all state."""
        breaker = CircuitBreaker()

        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()  # Opens circuit

        assert breaker.state == CircuitState.OPEN

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.can_execute() is True


class TestParseRetryAfter:
    """Tests for Retry-After header parsing."""

    @pytest.mark.requirement("FR-008")
    def test_parse_seconds(self) -> None:
        """Test parsing delay in seconds."""
        result = parse_retry_after("30")
        assert result == pytest.approx(30.0)

    @pytest.mark.requirement("FR-008")
    def test_parse_float_seconds(self) -> None:
        """Test parsing float seconds."""
        result = parse_retry_after("1.5")
        assert result == pytest.approx(1.5)

    @pytest.mark.requirement("FR-008")
    def test_parse_none(self) -> None:
        """Test None input returns None."""
        result = parse_retry_after(None)
        assert result is None

    @pytest.mark.requirement("FR-008")
    def test_parse_invalid_returns_none(self) -> None:
        """Test invalid input returns None."""
        result = parse_retry_after("invalid")
        assert result is None


class TestRetryConfig:
    """Tests for retry configuration."""

    @pytest.mark.requirement("FR-008")
    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 5
        assert config.base_delay == pytest.approx(2.0)
        assert config.max_delay == pytest.approx(60.0)
        assert config.exponential_base == pytest.approx(2.0)
        assert config.jitter is True

    @pytest.mark.requirement("FR-008")
    def test_custom_values(self) -> None:
        """Test custom configuration."""
        config = RetryConfig(
            max_retries=10,
            base_delay=0.5,
            max_delay=30.0,
            jitter=False,
        )

        assert config.max_retries == 10
        assert config.base_delay == pytest.approx(0.5)
        assert config.max_delay == pytest.approx(30.0)
        assert config.jitter is False

    @pytest.mark.requirement("FR-008")
    def test_config_is_frozen(self) -> None:
        """Test config is immutable."""
        config = RetryConfig()

        with pytest.raises(AttributeError):
            config.max_retries = 100  # type: ignore[misc]
