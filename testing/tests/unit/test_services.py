"""Unit tests for service health utilities.

Tests for testing.fixtures.services module including check_service_health(),
check_infrastructure(), and ServiceEndpoint.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from testing.fixtures.services import (
    ServiceEndpoint,
    ServiceUnavailableError,
    check_infrastructure,
    check_service_health,
)


class TestServiceEndpoint:
    """Tests for ServiceEndpoint dataclass."""

    @pytest.mark.requirement("9c-FR-005")
    def test_default_namespace(self) -> None:
        """Test ServiceEndpoint uses default namespace."""
        endpoint = ServiceEndpoint("polaris", 8181)
        assert endpoint.namespace == "floe-test"

    @pytest.mark.requirement("9c-FR-005")
    def test_custom_namespace(self) -> None:
        """Test ServiceEndpoint accepts custom namespace."""
        endpoint = ServiceEndpoint("postgres", 5432, "custom-ns")
        assert endpoint.namespace == "custom-ns"

    @pytest.mark.requirement("9c-FR-005")
    def test_host_property(self) -> None:
        """Test ServiceEndpoint generates effective host based on environment.

        When K8s DNS is resolvable, returns K8s DNS name.
        When not resolvable (running on host), returns localhost.
        """
        endpoint = ServiceEndpoint("polaris", 8181, "floe-test")
        # Mock K8s DNS resolution to return True so we get K8s DNS name
        with patch("testing.fixtures.services._can_resolve_host", return_value=True):
            assert endpoint.host == "polaris.floe-test.svc.cluster.local"

    @pytest.mark.requirement("9c-FR-005")
    def test_host_property_falls_back_to_localhost(self) -> None:
        """Test ServiceEndpoint falls back to localhost when K8s DNS not resolvable."""
        endpoint = ServiceEndpoint("polaris", 8181, "floe-test")
        with patch("testing.fixtures.services._can_resolve_host", return_value=False):
            assert endpoint.host == "localhost"

    @pytest.mark.requirement("9c-FR-005")
    def test_k8s_host_property(self) -> None:
        """Test ServiceEndpoint k8s_host always returns K8s DNS name."""
        endpoint = ServiceEndpoint("polaris", 8181, "floe-test")
        assert endpoint.k8s_host == "polaris.floe-test.svc.cluster.local"

    @pytest.mark.requirement("9c-FR-005")
    def test_str_representation(self) -> None:
        """Test ServiceEndpoint string representation."""
        endpoint = ServiceEndpoint("postgres", 5432)
        result = str(endpoint)
        assert "postgres:5432" in result
        assert "floe-test" in result

    @pytest.mark.requirement("9c-FR-005")
    def test_frozen(self) -> None:
        """Test ServiceEndpoint is immutable."""
        endpoint = ServiceEndpoint("polaris", 8181)
        with pytest.raises(FrozenInstanceError):
            endpoint.name = "other"  # type: ignore[misc]


class TestCheckServiceHealth:
    """Tests for check_service_health() function."""

    @pytest.mark.requirement("9c-FR-005")
    def test_returns_true_for_healthy_service(self) -> None:
        """Test check_service_health returns True for healthy service."""
        with patch("testing.fixtures.services._tcp_health_check", return_value=True):
            result = check_service_health("polaris", 8181)
            assert result is True

    @pytest.mark.requirement("9c-FR-005")
    def test_returns_false_for_unhealthy_service(self) -> None:
        """Test check_service_health returns False for unhealthy service."""
        with patch("testing.fixtures.services._tcp_health_check", return_value=False):
            result = check_service_health("polaris", 8181)
            assert result is False

    @pytest.mark.requirement("9c-FR-005")
    def test_uses_custom_namespace(self) -> None:
        """Test check_service_health uses custom namespace."""
        with (
            patch("testing.fixtures.services._can_resolve_host", return_value=True),
            patch("testing.fixtures.services._tcp_health_check") as mock_check,
        ):
            mock_check.return_value = True
            check_service_health("postgres", 5432, namespace="custom-ns")

            # Verify called with correct host (K8s DNS with custom namespace)
            call_args = mock_check.call_args[0]
            assert "custom-ns" in call_args[0]

    @pytest.mark.requirement("9c-FR-005")
    def test_uses_custom_timeout(self) -> None:
        """Test check_service_health passes timeout to TCP check."""
        with patch("testing.fixtures.services._tcp_health_check") as mock_check:
            mock_check.return_value = True
            check_service_health("polaris", 8181, timeout=10.0)

            # Verify timeout passed
            call_args = mock_check.call_args[0]
            assert call_args[2] == pytest.approx(10.0)


class TestCheckInfrastructure:
    """Tests for check_infrastructure() function."""

    @pytest.mark.requirement("9c-FR-005")
    def test_all_services_healthy(self) -> None:
        """Test check_infrastructure returns all True for healthy services."""
        with patch("testing.fixtures.services._tcp_health_check", return_value=True):
            result = check_infrastructure(
                [
                    ("polaris", 8181),
                    ("minio", 9000),
                    ("postgres", 5432),
                ]
            )

            assert result == {
                "polaris": True,
                "minio": True,
                "postgres": True,
            }

    @pytest.mark.requirement("9c-FR-005")
    def test_raises_on_unhealthy_service(self) -> None:
        """Test check_infrastructure raises when service unhealthy."""

        def mock_check(host: str, port: int, timeout: float) -> bool:
            _ = port, timeout  # Unused in mock
            return "polaris" not in host

        with (
            patch("testing.fixtures.services._can_resolve_host", return_value=True),
            patch(
                "testing.fixtures.services._tcp_health_check", side_effect=mock_check
            ),
        ):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                check_infrastructure(
                    [
                        ("polaris", 8181),
                        ("minio", 9000),
                    ]
                )

            assert "polaris" in str(exc_info.value)

    @pytest.mark.requirement("9c-FR-005")
    def test_no_raise_returns_all_statuses(self) -> None:
        """Test check_infrastructure returns all statuses with raise_on_failure=False."""

        def mock_check(host: str, port: int, timeout: float) -> bool:
            _ = port, timeout  # Unused in mock
            return "polaris" not in host

        with (
            patch("testing.fixtures.services._can_resolve_host", return_value=True),
            patch(
                "testing.fixtures.services._tcp_health_check", side_effect=mock_check
            ),
        ):
            result = check_infrastructure(
                [("polaris", 8181), ("minio", 9000)],
                raise_on_failure=False,
            )

            assert result["polaris"] is False
            assert result["minio"] is True


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError exception."""

    @pytest.mark.requirement("9c-FR-005")
    def test_error_message_contains_service_info(self) -> None:
        """Test error message contains service details."""
        endpoint = ServiceEndpoint("polaris", 8181)
        error = ServiceUnavailableError(endpoint, "connection refused")

        assert "polaris:8181" in str(error)
        assert "connection refused" in str(error)

    @pytest.mark.requirement("9c-FR-005")
    def test_error_suggests_make_kind_up(self) -> None:
        """Test error message suggests running make kind-up."""
        endpoint = ServiceEndpoint("polaris", 8181)
        error = ServiceUnavailableError(endpoint, "connection refused")

        assert "make kind-up" in str(error)

    @pytest.mark.requirement("9c-FR-005")
    def test_error_attributes(self) -> None:
        """Test error stores service and reason."""
        endpoint = ServiceEndpoint("postgres", 5432)
        error = ServiceUnavailableError(endpoint, "timeout")

        assert error.service == endpoint
        assert error.reason == "timeout"


class TestTcpHealthCheck:
    """Tests for _tcp_health_check internal function."""

    @pytest.mark.requirement("9c-FR-005")
    def test_successful_connection(self) -> None:
        """Test _tcp_health_check returns True for successful connection."""
        from unittest.mock import MagicMock

        from testing.fixtures.services import _tcp_health_check

        mock_socket = MagicMock()
        with patch("socket.create_connection", return_value=mock_socket):
            result = _tcp_health_check("localhost", 8080, 5.0)
            assert result is True

    @pytest.mark.requirement("9c-FR-005")
    def test_failed_connection(self) -> None:
        """Test _tcp_health_check returns False for failed connection."""
        from testing.fixtures.services import _tcp_health_check

        with patch(
            "socket.create_connection", side_effect=OSError("Connection refused")
        ):
            result = _tcp_health_check("localhost", 8080, 5.0)
            assert result is False

    @pytest.mark.requirement("9c-FR-005")
    def test_timeout_returns_false(self) -> None:
        """Test _tcp_health_check returns False on timeout."""

        from testing.fixtures.services import _tcp_health_check

        with patch("socket.create_connection", side_effect=TimeoutError("timed out")):
            result = _tcp_health_check("localhost", 8080, 5.0)
            assert result is False
