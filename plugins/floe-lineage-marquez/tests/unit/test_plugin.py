"""Tests for Marquez lineage backend plugin.

Tests verify that MarquezLineageBackendPlugin correctly implements
the LineageBackendPlugin interface and provides valid configuration
for Marquez deployments.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from floe_core.plugins.lineage import LineageBackendPlugin

from floe_lineage_marquez import MarquezLineageBackendPlugin


@pytest.mark.requirement("REQ-527")
def test_marquez_plugin_implements_interface() -> None:
    """Test that MarquezLineageBackendPlugin implements LineageBackendPlugin.

    Verifies that the plugin correctly inherits from the abstract base class
    and can be instantiated.
    """
    plugin = MarquezLineageBackendPlugin()
    assert isinstance(plugin, LineageBackendPlugin)


@pytest.mark.requirement("REQ-527")
def test_marquez_plugin_properties() -> None:
    """Test that MarquezLineageBackendPlugin has correct metadata properties.

    Verifies name, version, and floe_api_version properties return
    expected values.
    """
    plugin = MarquezLineageBackendPlugin()

    assert plugin.name == "marquez"
    assert plugin.version == "0.20.0"
    assert plugin.floe_api_version == "1.0"


@pytest.mark.requirement("REQ-527")
def test_transport_config_structure() -> None:
    """Test that get_transport_config returns correct HTTP transport config.

    Verifies the transport configuration has the correct structure
    for OpenLineage HTTP transport to Marquez.
    """
    plugin = MarquezLineageBackendPlugin(
        url="http://marquez:5000",
        api_key="test-key",  # pragma: allowlist secret
    )
    config = plugin.get_transport_config()

    assert config["type"] == "http"
    assert config["url"] == "http://marquez:5000/api/v1/lineage"
    assert config["timeout"] == 5.0
    assert config["api_key"] == "test-key"  # pragma: allowlist secret


@pytest.mark.requirement("REQ-527")
def test_transport_config_url_normalization() -> None:
    """Test that URLs with trailing slashes are normalized correctly.

    Verifies that trailing slashes in the base URL are removed
    to prevent double slashes in the final endpoint URL.
    """
    plugin = MarquezLineageBackendPlugin(url="http://marquez:5000/")
    config = plugin.get_transport_config()

    assert config["url"] == "http://marquez:5000/api/v1/lineage"


@pytest.mark.requirement("REQ-527")
def test_transport_config_without_api_key() -> None:
    """Test that transport config works without API key.

    Verifies that the plugin can be configured without authentication
    for development environments.
    """
    plugin = MarquezLineageBackendPlugin(url="http://localhost:5000")
    config = plugin.get_transport_config()

    assert config["api_key"] is None


@pytest.mark.requirement("REQ-527")
def test_namespace_strategy() -> None:
    """Test that get_namespace_strategy returns environment-based strategy.

    Verifies the namespace strategy configuration for organizing
    lineage data by environment.
    """
    plugin = MarquezLineageBackendPlugin()
    strategy = plugin.get_namespace_strategy()

    assert strategy["strategy"] == "centralized"
    assert strategy["environment"] == "prod"
    assert strategy["platform"] == "floe"


@pytest.mark.requirement("REQ-527")
def test_helm_values_structure() -> None:
    """Test that get_helm_values returns valid Helm chart configuration.

    Verifies the Helm values include both Marquez and PostgreSQL
    configuration sections with required fields.
    """
    plugin = MarquezLineageBackendPlugin()
    values = plugin.get_helm_values()

    # Verify Marquez section
    assert "marquez" in values
    assert values["marquez"]["enabled"] is True
    assert "image" in values["marquez"]
    assert values["marquez"]["image"]["repository"] == "marquezproject/marquez"
    assert values["marquez"]["service"]["port"] == 5000

    # Verify PostgreSQL section
    assert "postgresql" in values
    assert values["postgresql"]["enabled"] is True
    assert "auth" in values["postgresql"]
    assert values["postgresql"]["auth"]["database"] == "marquez"


@pytest.mark.requirement("REQ-527")
def test_helm_values_resource_limits() -> None:
    """Test that Helm values include resource limits.

    Verifies that both Marquez and PostgreSQL have resource
    limits and requests defined for Kubernetes deployment.
    """
    plugin = MarquezLineageBackendPlugin()
    values = plugin.get_helm_values()

    # Marquez resources
    marquez_resources = values["marquez"]["resources"]
    assert "limits" in marquez_resources
    assert "requests" in marquez_resources
    assert marquez_resources["limits"]["cpu"] == "500m"
    assert marquez_resources["limits"]["memory"] == "512Mi"

    # PostgreSQL resources
    pg_resources = values["postgresql"]["primary"]["resources"]
    assert "limits" in pg_resources
    assert "requests" in pg_resources


@pytest.mark.requirement("REQ-527")
def test_validate_connection_success() -> None:
    """Test that validate_connection returns True when server responds.

    Mocks urllib to simulate a successful connection to Marquez API.
    """
    plugin = MarquezLineageBackendPlugin(url="http://localhost:5000")

    # Mock successful HTTP response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = plugin.validate_connection()

    assert result is True


@pytest.mark.requirement("REQ-527")
def test_validate_connection_failure_no_server() -> None:
    """Test that validate_connection returns False when server is unreachable.

    Mocks urllib to simulate connection failure (no server running).
    """
    plugin = MarquezLineageBackendPlugin(url="http://localhost:5000")

    # Mock connection error
    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        result = plugin.validate_connection()

    assert result is False


@pytest.mark.requirement("REQ-527")
def test_validate_connection_failure_timeout() -> None:
    """Test that validate_connection returns False on timeout.

    Mocks urllib to simulate request timeout.
    """
    plugin = MarquezLineageBackendPlugin(url="http://localhost:5000")

    # Mock timeout error
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timeout")):
        result = plugin.validate_connection()

    assert result is False


@pytest.mark.requirement("REQ-527")
def test_validate_connection_with_api_key() -> None:
    """Test that validate_connection includes API key in request headers.

    Verifies that the Authorization header is set when API key is provided.
    """
    plugin = MarquezLineageBackendPlugin(
        url="http://localhost:5000",
        api_key="test-key",  # pragma: allowlist secret
    )

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        result = plugin.validate_connection()

        # Verify Authorization header was set
        request = mock_urlopen.call_args[0][0]
        assert request.get_header("Authorization") == "Bearer test-key"

    assert result is True


@pytest.mark.requirement("REQ-527")
def test_validate_connection_endpoint() -> None:
    """Test that validate_connection uses correct API endpoint.

    Verifies that the validation request is sent to the namespaces endpoint.
    """
    plugin = MarquezLineageBackendPlugin(url="http://localhost:5000")

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        plugin.validate_connection()

        # Verify correct endpoint was called
        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "http://localhost:5000/api/v1/namespaces"
