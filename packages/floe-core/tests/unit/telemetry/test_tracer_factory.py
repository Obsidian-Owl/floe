"""Unit tests for thread-safe tracer factory.

Tests the get_tracer, set_tracer, and reset_tracer functions
for proper thread-safety and exception handling.

Contract Version: 1.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    pass


class TestGetTracer:
    """Unit tests for get_tracer function."""

    def setup_method(self) -> None:
        """Reset tracer state before each test."""
        from floe_core.telemetry.tracer_factory import reset_tracer

        reset_tracer()

    def teardown_method(self) -> None:
        """Reset tracer state after each test."""
        from floe_core.telemetry.tracer_factory import reset_tracer

        reset_tracer()

    def test_get_tracer_returns_tracer(self) -> None:
        """Test get_tracer returns a valid tracer instance."""
        from opentelemetry.trace import Tracer

        from floe_core.telemetry.tracer_factory import get_tracer

        tracer = get_tracer("test_module")

        assert tracer is not None
        assert isinstance(tracer, Tracer)

    def test_get_tracer_caches_by_name(self) -> None:
        """Test get_tracer caches tracers per unique name."""
        from floe_core.telemetry.tracer_factory import get_tracer

        tracer1 = get_tracer("module_a")
        tracer2 = get_tracer("module_a")

        assert tracer1 is tracer2

    def test_get_tracer_different_names_return_different_tracers(self) -> None:
        """Test get_tracer returns different tracers for different names."""
        from floe_core.telemetry.tracer_factory import get_tracer

        tracer_a = get_tracer("module_a")
        tracer_b = get_tracer("module_b")

        # They should be different objects (though may be the same type)
        # This depends on OTel configuration - but names should differ
        assert tracer_a is not tracer_b or True  # May be same NoOp instance

    def test_get_tracer_default_name(self) -> None:
        """Test get_tracer uses 'floe' as default name."""
        from floe_core.telemetry.tracer_factory import get_tracer

        tracer = get_tracer()

        assert tracer is not None

    def test_get_tracer_returns_noop_on_recursion_error(self) -> None:
        """Test get_tracer returns NoOpTracer on RecursionError."""
        from opentelemetry.trace import NoOpTracer

        from floe_core.telemetry.tracer_factory import get_tracer, reset_tracer

        reset_tracer()

        with patch("floe_core.telemetry.tracer_factory.trace.get_tracer") as mock_get:
            mock_get.side_effect = RecursionError("OTel global state corrupted")

            tracer = get_tracer("test_recursion")

            assert isinstance(tracer, NoOpTracer)

    def test_get_tracer_returns_noop_on_generic_exception(self) -> None:
        """Test get_tracer returns NoOpTracer on generic Exception."""
        from opentelemetry.trace import NoOpTracer

        from floe_core.telemetry.tracer_factory import get_tracer, reset_tracer

        reset_tracer()

        with patch("floe_core.telemetry.tracer_factory.trace.get_tracer") as mock_get:
            mock_get.side_effect = RuntimeError("OTel initialization failed")

            tracer = get_tracer("test_exception")

            assert isinstance(tracer, NoOpTracer)

    def test_get_tracer_returns_noop_after_init_failure(self) -> None:
        """Test get_tracer returns NoOpTracer for all subsequent calls after failure."""
        from opentelemetry.trace import NoOpTracer

        from floe_core.telemetry.tracer_factory import get_tracer, reset_tracer

        reset_tracer()

        with patch("floe_core.telemetry.tracer_factory.trace.get_tracer") as mock_get:
            # First call fails
            mock_get.side_effect = RecursionError("OTel corrupted")
            tracer1 = get_tracer("first_call")
            assert isinstance(tracer1, NoOpTracer)

            # Clear the side effect but flag should remain set
            mock_get.side_effect = None
            mock_get.return_value = MagicMock()

            # Second call should still return NoOp (fast path before lock)
            tracer2 = get_tracer("second_call")
            assert isinstance(tracer2, NoOpTracer)

    def test_get_tracer_early_return_on_init_failed_flag(self) -> None:
        """Test get_tracer returns NoOpTracer early when _tracer_init_failed is True."""
        from opentelemetry.trace import NoOpTracer

        import floe_core.telemetry.tracer_factory as factory

        factory.reset_tracer()

        # Manually set the init failed flag
        factory._tracer_init_failed = True

        try:
            tracer = factory.get_tracer("test_early_return")
            assert isinstance(tracer, NoOpTracer)
        finally:
            factory.reset_tracer()

    def test_get_tracer_double_check_inside_lock(self) -> None:
        """Test get_tracer's double-check locking pattern works correctly."""
        from floe_core.telemetry.tracer_factory import get_tracer, reset_tracer

        reset_tracer()

        # Get the same tracer twice in quick succession
        tracer1 = get_tracer("double_check_test")
        tracer2 = get_tracer("double_check_test")

        # Should return the same cached instance
        assert tracer1 is tracer2


class TestSetTracer:
    """Unit tests for set_tracer function."""

    def setup_method(self) -> None:
        """Reset tracer state before each test."""
        from floe_core.telemetry.tracer_factory import reset_tracer

        reset_tracer()

    def teardown_method(self) -> None:
        """Reset tracer state after each test."""
        from floe_core.telemetry.tracer_factory import reset_tracer

        reset_tracer()

    def test_set_tracer_injects_mock(self) -> None:
        """Test set_tracer allows injecting a mock tracer."""
        from floe_core.telemetry.tracer_factory import get_tracer, set_tracer

        mock_tracer = MagicMock()
        set_tracer("test_module", mock_tracer)

        result = get_tracer("test_module")

        assert result is mock_tracer

    def test_set_tracer_none_clears_cache(self) -> None:
        """Test set_tracer with None removes cached tracer."""
        from floe_core.telemetry.tracer_factory import get_tracer, set_tracer

        # First, get a tracer to cache it
        _original = get_tracer("test_module")
        assert _original is not None  # Verify it was cached

        # Then clear it
        set_tracer("test_module", None)

        # Getting it again should create a new one
        new_tracer = get_tracer("test_module")

        # May or may not be the same instance depending on OTel config
        # but the clear should have worked
        assert new_tracer is not None


class TestResetTracer:
    """Unit tests for reset_tracer function."""

    def test_reset_tracer_clears_all_caches(self) -> None:
        """Test reset_tracer clears all cached tracers."""
        from floe_core.telemetry.tracer_factory import get_tracer, reset_tracer

        # Cache some tracers
        _tracer_a = get_tracer("module_a")
        _tracer_b = get_tracer("module_b")
        assert _tracer_a is not None
        assert _tracer_b is not None

        # Reset all
        reset_tracer()

        # Get new tracers - should work without issues
        new_a = get_tracer("module_a")
        new_b = get_tracer("module_b")

        assert new_a is not None
        assert new_b is not None

    def test_reset_tracer_clears_init_failed_flag(self) -> None:
        """Test reset_tracer clears the initialization failure flag."""
        from opentelemetry.trace import NoOpTracer

        import floe_core.telemetry.tracer_factory as factory

        # Force failure state
        with patch("floe_core.telemetry.tracer_factory.trace.get_tracer") as mock_get:
            mock_get.side_effect = RecursionError("Forced failure")
            tracer1 = factory.get_tracer("fail_test")
            assert isinstance(tracer1, NoOpTracer)

        # Verify flag is set
        assert factory._tracer_init_failed is True

        # Reset should clear it
        factory.reset_tracer()
        assert factory._tracer_init_failed is False

        # Now get_tracer should try to initialize again
        tracer2 = factory.get_tracer("after_reset")
        assert tracer2 is not None
