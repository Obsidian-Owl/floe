"""Health/status sanitization tests for Infisical secrets plugin."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from floe_core.plugin_metadata import HealthState
from pydantic import SecretStr

from floe_secrets_infisical.config import InfisicalSecretsConfig
from floe_secrets_infisical.plugin import InfisicalSecretsPlugin


@pytest.mark.requirement("SEC-OBS-005")
def test_health_check_sanitizes_provider_error_message() -> None:
    """Health status must not expose provider exception text."""
    plugin = InfisicalSecretsPlugin(
        InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("placeholder"),
            site_url="https://app.infisical.com",
            environment="dev",
            project_id="proj_12345",
            secret_path="/floe",
        )
    )
    plugin._authenticated = True
    plugin._client = Mock()
    toxic_error = RuntimeError(
        "503 https://infisical.example/api?token=raw-token "
        "password=raw-password secret_value=raw-secret person@example.com"
    )

    with patch.object(plugin, "_list_secrets_internal", side_effect=toxic_error):
        status = plugin.health_check()

    assert status.state == HealthState.UNHEALTHY
    assert status.message == "Infisical health check failed: unavailable"
    assert "raw-token" not in status.message
    assert "raw-password" not in status.message
    assert "raw-secret" not in status.message
    assert "infisical.example" not in status.message
    assert "person@example.com" not in status.message
