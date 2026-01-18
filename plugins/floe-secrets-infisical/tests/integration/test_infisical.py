"""Integration tests for Infisical Secrets operations.

Tests InfisicalSecretsPlugin operations against a real Infisical instance.
These tests are OPTIONAL and require:
- Infisical instance available (cloud or self-hosted)
- Valid Universal Auth credentials in environment variables

Task: T044
Requirements: 7A-FR-020 (InfisicalSecretsPlugin integration)

Prerequisites:
    Set these environment variables:
    - INFISICAL_CLIENT_ID: Universal Auth client ID
    - INFISICAL_CLIENT_SECRET: Universal Auth client secret
    - INFISICAL_PROJECT_ID: Project ID for testing
    - INFISICAL_SITE_URL: (optional) Self-hosted URL, defaults to cloud
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr
from testing.base_classes.integration_test_base import IntegrationTestBase

if TYPE_CHECKING:
    from collections.abc import Generator


def _infisical_credentials_available() -> bool:
    """Check if Infisical credentials are available in environment."""
    return bool(
        os.environ.get("INFISICAL_CLIENT_ID")
        and os.environ.get("INFISICAL_CLIENT_SECRET")
        and os.environ.get("INFISICAL_PROJECT_ID")
    )


class TestInfisicalSecretsOperations(IntegrationTestBase):
    """Integration tests for Infisical Secrets operations.

    Requires a real Infisical instance and valid Universal Auth credentials.
    Tests run in an isolated path and clean up after themselves.
    """

    # No local services required - Infisical is external
    required_services: list[tuple[str, int]] = []

    @pytest.fixture
    def infisical_config(self) -> InfisicalSecretsConfig:
        """Create config from environment variables.

        Raises:
            pytest.fail: If credentials are not available.
        """
        if not _infisical_credentials_available():
            pytest.fail(
                "Infisical credentials not available. "
                "Set INFISICAL_CLIENT_ID, INFISICAL_CLIENT_SECRET, INFISICAL_PROJECT_ID"
            )

        from floe_secrets_infisical.config import InfisicalSecretsConfig

        return InfisicalSecretsConfig(
            client_id=os.environ["INFISICAL_CLIENT_ID"],
            client_secret=SecretStr(os.environ["INFISICAL_CLIENT_SECRET"]),
            project_id=os.environ["INFISICAL_PROJECT_ID"],
            site_url=os.environ.get("INFISICAL_SITE_URL", "https://app.infisical.com"),
            environment="dev",
            secret_path=f"/floe-test-{uuid.uuid4().hex[:8]}",
        )

    @pytest.fixture
    def plugin(
        self, infisical_config: InfisicalSecretsConfig
    ) -> Generator[InfisicalSecretsPlugin, None, None]:
        """Create and initialize plugin for tests."""
        from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

        plugin = InfisicalSecretsPlugin(config=infisical_config)
        plugin.startup()
        yield plugin
        # Cleanup: delete any secrets created during test
        try:
            secrets = plugin.list_secrets()
            for secret_key in secrets:
                try:
                    plugin.delete_secret(secret_key)
                except Exception:
                    pass  # Best effort cleanup
        except Exception:
            pass
        plugin.shutdown()

    @pytest.mark.requirement("7A-FR-020")
    def test_authenticate_with_universal_auth(
        self, infisical_config: InfisicalSecretsConfig
    ) -> None:
        """Test successful authentication with Universal Auth credentials."""
        from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

        plugin = InfisicalSecretsPlugin(config=infisical_config)

        # startup() should authenticate without errors
        plugin.startup()

        try:
            # Verify authenticated by making API call
            status = plugin.health_check()
            assert status.healthy is True
        finally:
            plugin.shutdown()

    @pytest.mark.requirement("7A-FR-020")
    def test_get_secret_returns_value(self, plugin: InfisicalSecretsPlugin) -> None:
        """Test get_secret retrieves an existing secret value."""
        secret_key = f"test-secret-{uuid.uuid4().hex[:8]}"
        secret_value = f"value-{uuid.uuid4().hex}"

        # Create secret first
        plugin.set_secret(secret_key, secret_value)

        # Retrieve it
        result = plugin.get_secret(secret_key)

        assert result == secret_value

    @pytest.mark.requirement("7A-FR-020")
    def test_get_secret_returns_none_for_nonexistent(self, plugin: InfisicalSecretsPlugin) -> None:
        """Test get_secret returns None for non-existent secret."""
        result = plugin.get_secret(f"nonexistent-{uuid.uuid4().hex}")

        assert result is None

    @pytest.mark.requirement("7A-FR-020")
    def test_set_secret_creates_new(self, plugin: InfisicalSecretsPlugin) -> None:
        """Test set_secret creates a new secret."""
        secret_key = f"new-secret-{uuid.uuid4().hex[:8]}"
        secret_value = f"new-value-{uuid.uuid4().hex}"

        # Create secret
        plugin.set_secret(secret_key, secret_value)

        # Verify it exists
        result = plugin.get_secret(secret_key)
        assert result == secret_value

    @pytest.mark.requirement("7A-FR-020")
    def test_set_secret_updates_existing(self, plugin: InfisicalSecretsPlugin) -> None:
        """Test set_secret updates an existing secret."""
        secret_key = f"update-secret-{uuid.uuid4().hex[:8]}"
        original_value = "original-value"
        updated_value = "updated-value"

        # Create original
        plugin.set_secret(secret_key, original_value)

        # Update
        plugin.set_secret(secret_key, updated_value)

        # Verify updated value
        result = plugin.get_secret(secret_key)
        assert result == updated_value

    @pytest.mark.requirement("7A-FR-020")
    def test_list_secrets_returns_all(self, plugin: InfisicalSecretsPlugin) -> None:
        """Test list_secrets returns all secrets at path."""
        # Create multiple secrets
        secret_keys = [
            f"list-test-a-{uuid.uuid4().hex[:8]}",
            f"list-test-b-{uuid.uuid4().hex[:8]}",
            f"list-test-c-{uuid.uuid4().hex[:8]}",
        ]

        for key in secret_keys:
            plugin.set_secret(key, f"value-for-{key}")

        # List secrets
        result = plugin.list_secrets()

        # All created secrets should be in the list
        for key in secret_keys:
            assert key in result

    @pytest.mark.requirement("7A-FR-020")
    def test_list_secrets_filters_by_prefix(self, plugin: InfisicalSecretsPlugin) -> None:
        """Test list_secrets filters by prefix."""
        # Create secrets with different prefixes
        db_keys = [f"db-{uuid.uuid4().hex[:8]}" for _ in range(2)]
        api_keys = [f"api-{uuid.uuid4().hex[:8]}" for _ in range(2)]

        for key in db_keys + api_keys:
            plugin.set_secret(key, f"value-for-{key}")

        # Filter by db- prefix
        result = plugin.list_secrets(prefix="db-")

        # Should only contain db- prefixed keys
        assert all(k.startswith("db-") for k in result)
        assert not any(k.startswith("api-") for k in result)

    @pytest.mark.requirement("7A-FR-020")
    def test_health_check_returns_healthy(self, plugin: InfisicalSecretsPlugin) -> None:
        """Test health_check returns healthy when connected."""
        status = plugin.health_check()

        assert status.healthy is True
        assert status.message is not None

    @pytest.mark.requirement("7A-FR-021")
    def test_invalid_credentials_fail_auth(self) -> None:
        """Test authentication fails with invalid credentials."""
        from floe_secrets_infisical.config import InfisicalSecretsConfig
        from floe_secrets_infisical.errors import InfisicalAuthError
        from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

        config = InfisicalSecretsConfig(
            client_id="invalid-client-id",
            client_secret=SecretStr("invalid-client-secret"),
            project_id=os.environ["INFISICAL_PROJECT_ID"],
        )

        plugin = InfisicalSecretsPlugin(config=config)

        with pytest.raises((InfisicalAuthError, PermissionError, Exception)):
            plugin.startup()


class TestInfisicalSecretsPathOrganization(IntegrationTestBase):
    """Integration tests for path-based secret organization (FR-024)."""

    required_services: list[tuple[str, int]] = []

    @pytest.fixture
    def base_path(self) -> str:
        """Generate unique base path for isolation."""
        return f"/floe-test-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def plugin_with_path(self, base_path: str) -> Generator[InfisicalSecretsPlugin, None, None]:
        """Create plugin with specific secret_path.

        Raises:
            pytest.fail: If credentials are not available.
        """
        if not _infisical_credentials_available():
            pytest.fail(
                "Infisical credentials not available. "
                "Set INFISICAL_CLIENT_ID, INFISICAL_CLIENT_SECRET, INFISICAL_PROJECT_ID"
            )

        from floe_secrets_infisical.config import InfisicalSecretsConfig
        from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

        config = InfisicalSecretsConfig(
            client_id=os.environ["INFISICAL_CLIENT_ID"],
            client_secret=SecretStr(os.environ["INFISICAL_CLIENT_SECRET"]),
            project_id=os.environ["INFISICAL_PROJECT_ID"],
            site_url=os.environ.get("INFISICAL_SITE_URL", "https://app.infisical.com"),
            environment="dev",
            secret_path=base_path,
        )

        plugin = InfisicalSecretsPlugin(config=config)
        plugin.startup()
        yield plugin
        plugin.shutdown()

    @pytest.mark.requirement("7A-FR-024")
    def test_secrets_isolated_by_path(
        self, plugin_with_path: InfisicalSecretsPlugin, base_path: str
    ) -> None:
        """Test secrets at different paths are isolated."""
        from floe_secrets_infisical.config import InfisicalSecretsConfig
        from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

        # Create secret in first path
        secret_key = f"isolated-{uuid.uuid4().hex[:8]}"
        plugin_with_path.set_secret(secret_key, "value-in-base")

        # Create plugin with different path
        other_path = f"{base_path}/subpath"
        other_config = InfisicalSecretsConfig(
            client_id=os.environ["INFISICAL_CLIENT_ID"],
            client_secret=SecretStr(os.environ["INFISICAL_CLIENT_SECRET"]),
            project_id=os.environ["INFISICAL_PROJECT_ID"],
            site_url=os.environ.get("INFISICAL_SITE_URL", "https://app.infisical.com"),
            environment="dev",
            secret_path=other_path,
        )
        other_plugin = InfisicalSecretsPlugin(config=other_config)
        other_plugin.startup()

        try:
            # Secret should not be visible from other path
            result = other_plugin.get_secret(secret_key)
            assert result is None
        finally:
            other_plugin.shutdown()


class TestInfisicalSecretsEnvironmentIsolation(IntegrationTestBase):
    """Integration tests for environment-based isolation."""

    required_services: list[tuple[str, int]] = []

    @pytest.mark.requirement("7A-FR-020")
    def test_different_environments_isolated(self) -> None:
        """Test secrets in different environments are isolated."""
        if not _infisical_credentials_available():
            pytest.fail(
                "Infisical credentials not available. "
                "Set INFISICAL_CLIENT_ID, INFISICAL_CLIENT_SECRET, INFISICAL_PROJECT_ID"
            )

        from floe_secrets_infisical.config import InfisicalSecretsConfig
        from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

        base_path = f"/floe-test-{uuid.uuid4().hex[:8]}"
        secret_key = f"env-test-{uuid.uuid4().hex[:8]}"

        # Create in dev environment
        dev_config = InfisicalSecretsConfig(
            client_id=os.environ["INFISICAL_CLIENT_ID"],
            client_secret=SecretStr(os.environ["INFISICAL_CLIENT_SECRET"]),
            project_id=os.environ["INFISICAL_PROJECT_ID"],
            site_url=os.environ.get("INFISICAL_SITE_URL", "https://app.infisical.com"),
            environment="dev",
            secret_path=base_path,
        )
        dev_plugin = InfisicalSecretsPlugin(config=dev_config)
        dev_plugin.startup()

        try:
            dev_plugin.set_secret(secret_key, "dev-value")

            # Try to access from staging environment (should not find it)
            staging_config = InfisicalSecretsConfig(
                client_id=os.environ["INFISICAL_CLIENT_ID"],
                client_secret=SecretStr(os.environ["INFISICAL_CLIENT_SECRET"]),
                project_id=os.environ["INFISICAL_PROJECT_ID"],
                site_url=os.environ.get("INFISICAL_SITE_URL", "https://app.infisical.com"),
                environment="staging",
                secret_path=base_path,
            )
            staging_plugin = InfisicalSecretsPlugin(config=staging_config)
            staging_plugin.startup()

            try:
                result = staging_plugin.get_secret(secret_key)
                # Should not find dev secret in staging
                assert result is None
            finally:
                staging_plugin.shutdown()

        finally:
            dev_plugin.shutdown()


# Type hints for fixtures
if TYPE_CHECKING:
    from floe_secrets_infisical.config import InfisicalSecretsConfig
    from floe_secrets_infisical.plugin import InfisicalSecretsPlugin
