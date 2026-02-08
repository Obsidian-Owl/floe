"""Tests for Marquez lineage backend plugin.

Tests verify that MarquezLineageBackendPlugin correctly implements
the LineageBackendPlugin interface and provides valid configuration
for Marquez deployments.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from floe_core.plugins.lineage import LineageBackendPlugin
from pydantic import ValidationError

from floe_lineage_marquez import MarquezConfig, MarquezLineageBackendPlugin


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
    # Use HTTPS for non-localhost URLs (security requirement)
    plugin = MarquezLineageBackendPlugin(
        url="https://marquez:5000",
        api_key="test-key",  # pragma: allowlist secret
    )
    config = plugin.get_transport_config()

    assert config["type"] == "http"
    assert config["url"] == "https://marquez:5000/api/v1/lineage"
    assert config["timeout"] == 5.0
    assert config["api_key"] == "test-key"  # pragma: allowlist secret


@pytest.mark.requirement("REQ-527")
def test_transport_config_url_normalization() -> None:
    """Test that URLs with trailing slashes are normalized correctly.

    Verifies that trailing slashes in the base URL are removed
    to prevent double slashes in the final endpoint URL.
    """
    # Use localhost (allowed for HTTP)
    plugin = MarquezLineageBackendPlugin(url="http://localhost:5000/")
    config = plugin.get_transport_config()

    assert config["url"] == "http://localhost:5000/api/v1/lineage"


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


@pytest.mark.requirement("REQ-527")
def test_namespace_strategy_custom_environment() -> None:
    """Test that namespace strategy uses configurable environment."""
    plugin = MarquezLineageBackendPlugin(environment="staging")
    strategy = plugin.get_namespace_strategy()

    assert strategy["strategy"] == "centralized"
    assert strategy["environment"] == "staging"
    assert strategy["platform"] == "floe"


@pytest.mark.requirement("REQ-527")
def test_config_schema_validation() -> None:
    """Test that MarquezConfig schema validates configuration."""
    # Use HTTPS for non-localhost URLs (security requirement)
    config = MarquezConfig(
        url="https://custom-marquez:9000",
        api_key="my-key",  # pragma: allowlist secret
        environment="dev",
        verify_ssl=False,
    )

    assert config.url == "https://custom-marquez:9000"
    assert config.api_key == "my-key"  # pragma: allowlist secret
    assert config.environment == "dev"
    assert config.verify_ssl is False


@pytest.mark.requirement("REQ-527")
def test_config_schema_defaults() -> None:
    """Test that MarquezConfig has correct defaults."""
    config = MarquezConfig()

    assert config.url == "https://marquez:5000"
    assert config.api_key is None
    assert config.environment == "prod"
    assert config.verify_ssl is True


@pytest.mark.requirement("REQ-527")
def test_get_config_schema_returns_model() -> None:
    """Test that get_config_schema returns the MarquezConfig class."""
    plugin = MarquezLineageBackendPlugin()
    schema = plugin.get_config_schema()

    assert schema is MarquezConfig


@pytest.mark.requirement("REQ-527")
def test_helm_values_uses_existing_secret() -> None:
    """Test that PostgreSQL uses existingSecret pattern (no inline password).

    SECURITY: Inline passwords violate floe's SecretReference architecture.
    The Bitnami existingSecret pattern references a Kubernetes Secret.
    """
    plugin = MarquezLineageBackendPlugin()
    values = plugin.get_helm_values()

    auth = values["postgresql"]["auth"]
    # Verify existingSecret pattern is used
    assert "existingSecret" in auth
    assert auth["existingSecret"] == "marquez-postgresql-credentials"  # pragma: allowlist secret
    # Verify secretKeys are specified (pragma: allowlist secret)
    assert "secretKeys" in auth
    # These are key NAMES, not actual secrets
    assert (
        auth["secretKeys"]["adminPasswordKey"]  # pragma: allowlist secret
        == "postgres-password"  # pragma: allowlist secret
    )
    assert (
        auth["secretKeys"]["userPasswordKey"]  # pragma: allowlist secret
        == "password"  # pragma: allowlist secret
    )
    # Verify NO inline password value
    assert "password" not in auth


# =============================================================================
# URL Security Validation Tests
# =============================================================================


class TestURLSecurityValidation:
    """Tests for URL security validation in MarquezConfig.

    SECURITY: These tests verify that HTTP is blocked for non-localhost URLs
    unless explicitly overridden via FLOE_ALLOW_INSECURE_HTTP environment variable.
    """

    @pytest.mark.requirement("REQ-527")
    def test_https_url_accepted(self) -> None:
        """Test that HTTPS URLs are always accepted."""
        config = MarquezConfig(url="https://marquez.example.com:5000")
        assert config.url == "https://marquez.example.com:5000"

    @pytest.mark.requirement("REQ-527")
    def test_http_localhost_accepted(self) -> None:
        """Test that HTTP is allowed for localhost."""
        config = MarquezConfig(url="http://localhost:5000")
        assert config.url == "http://localhost:5000"

    @pytest.mark.requirement("REQ-527")
    def test_http_127_0_0_1_accepted(self) -> None:
        """Test that HTTP is allowed for 127.0.0.1."""
        config = MarquezConfig(url="http://127.0.0.1:5000")
        assert config.url == "http://127.0.0.1:5000"

    @pytest.mark.requirement("REQ-527")
    def test_http_ipv6_loopback_accepted(self) -> None:
        """Test that HTTP is allowed for IPv6 loopback (::1)."""
        config = MarquezConfig(url="http://[::1]:5000")
        assert config.url == "http://[::1]:5000"

    @pytest.mark.requirement("REQ-527")
    def test_http_non_localhost_rejected(self) -> None:
        """Test that HTTP is rejected for non-localhost URLs by default."""
        with pytest.raises(ValidationError) as exc_info:
            MarquezConfig(url="http://marquez.example.com:5000")

        error = exc_info.value.errors()[0]
        assert "HTTP not allowed" in error["msg"]
        assert "marquez.example.com" in error["msg"]

    @pytest.mark.requirement("REQ-527")
    def test_http_non_localhost_rejected_for_internal_hostnames(self) -> None:
        """Test that HTTP is rejected for internal/cluster hostnames."""
        with pytest.raises(ValidationError) as exc_info:
            MarquezConfig(url="http://marquez:5000")

        error = exc_info.value.errors()[0]
        assert "HTTP not allowed" in error["msg"]

    @pytest.mark.requirement("REQ-527")
    def test_http_allowed_with_env_override(self) -> None:
        """Test that HTTP is allowed when FLOE_ALLOW_INSECURE_HTTP=true."""
        original = os.environ.get("FLOE_ALLOW_INSECURE_HTTP")
        try:
            os.environ["FLOE_ALLOW_INSECURE_HTTP"] = "true"
            config = MarquezConfig(url="http://marquez.example.com:5000")
            assert config.url == "http://marquez.example.com:5000"
        finally:
            if original is not None:
                os.environ["FLOE_ALLOW_INSECURE_HTTP"] = original
            else:
                os.environ.pop("FLOE_ALLOW_INSECURE_HTTP", None)

    @pytest.mark.requirement("REQ-527")
    def test_http_rejected_when_env_override_false(self) -> None:
        """Test that HTTP is rejected when FLOE_ALLOW_INSECURE_HTTP=false."""
        original = os.environ.get("FLOE_ALLOW_INSECURE_HTTP")
        try:
            os.environ["FLOE_ALLOW_INSECURE_HTTP"] = "false"
            with pytest.raises(ValidationError):
                MarquezConfig(url="http://marquez.example.com:5000")
        finally:
            if original is not None:
                os.environ["FLOE_ALLOW_INSECURE_HTTP"] = original
            else:
                os.environ.pop("FLOE_ALLOW_INSECURE_HTTP", None)

    @pytest.mark.requirement("REQ-527")
    def test_invalid_protocol_rejected(self) -> None:
        """Test that non-HTTP(S) protocols are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MarquezConfig(url="ftp://marquez:5000")

        error = exc_info.value.errors()[0]
        assert "must start with https://" in error["msg"]

    @pytest.mark.requirement("REQ-527")
    def test_trailing_slash_normalized(self) -> None:
        """Test that trailing slashes are stripped from URLs."""
        config = MarquezConfig(url="https://marquez:5000/")
        assert config.url == "https://marquez:5000"

    @pytest.mark.requirement("REQ-527")
    def test_plugin_validates_url_on_init(self) -> None:
        """Test that plugin constructor validates URL via MarquezConfig."""
        with pytest.raises(ValidationError) as exc_info:
            MarquezLineageBackendPlugin(url="http://marquez.example.com:5000")

        error = exc_info.value.errors()[0]
        assert "HTTP not allowed" in error["msg"]

    @pytest.mark.requirement("REQ-527")
    def test_localhost_bypass_not_vulnerable_to_prefix_attack(self) -> None:
        """Test that localhost.attacker.com is NOT treated as localhost.

        SECURITY: Prevents bypass via hostnames that start with 'localhost'.
        """
        with pytest.raises(ValidationError) as exc_info:
            MarquezConfig(url="http://localhost.attacker.com:5000")

        error = exc_info.value.errors()[0]
        assert "HTTP not allowed" in error["msg"]
