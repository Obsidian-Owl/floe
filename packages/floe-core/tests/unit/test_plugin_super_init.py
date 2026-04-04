"""Tests that all 11 plugin subclasses call super().__init__().

Verifies AC-3: every plugin with a custom __init__ calls
super().__init__() so the ABC's _config attribute is properly
initialized. Tests MUST FAIL until plugins are fixed to call super().

This test suite covers:
- ABC lifecycle contract: _config attribute exists after construction
- is_configured property works on every plugin
- Direct instantiation with config yields is_configured == True
- Registry path: configure() overwrites __init__ config (last-write-wins)
- Alert plugins (no config param): _config exists from super().__init__()

Done when all fail before implementation (super() calls added).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, SecretStr

# ---------------------------------------------------------------------------
# Config construction helpers
# ---------------------------------------------------------------------------


def _make_polaris_config() -> Any:
    """Create a minimal PolarisCatalogConfig mock."""
    from floe_catalog_polaris.config import PolarisCatalogConfig

    # PolarisCatalogConfig requires specific fields; use MagicMock with spec
    mock = MagicMock(spec=PolarisCatalogConfig)
    mock.uri = "http://polaris:8181/api/catalog"
    mock.warehouse = "test-warehouse"
    return mock


def _make_s3_config() -> Any:
    """Create a minimal S3StorageConfig mock."""
    from floe_storage_s3.config import S3StorageConfig

    mock = MagicMock(spec=S3StorageConfig)
    mock.endpoint = "http://minio:9000"
    mock.bucket = "test-bucket"
    return mock


def _make_infisical_config() -> Any:
    """Create a minimal InfisicalSecretsConfig mock."""
    from floe_secrets_infisical.config import InfisicalSecretsConfig

    mock = MagicMock(spec=InfisicalSecretsConfig)
    mock.client_id = "test-client"
    mock.client_secret = SecretStr("test-secret")
    mock.project_id = "proj_test"
    return mock


def _make_k8s_config() -> Any:
    """Create a minimal K8sSecretsConfig."""
    from floe_secrets_k8s.config import K8sSecretsConfig

    # K8sSecretsConfig has simple defaults; real instance is fine
    return K8sSecretsConfig()


def _make_keycloak_config() -> Any:
    """Create a minimal KeycloakIdentityConfig mock."""
    from floe_identity_keycloak.config import KeycloakIdentityConfig

    mock = MagicMock(spec=KeycloakIdentityConfig)
    mock.server_url = "http://keycloak:8080"
    mock.realm = "test-realm"
    mock.client_id = "test-client"
    mock.client_secret = SecretStr("test-secret")
    return mock


def _make_cube_config() -> Any:
    """Create a minimal CubeSemanticConfig mock."""
    from floe_semantic_cube.config import CubeSemanticConfig

    mock = MagicMock(spec=CubeSemanticConfig)
    mock.api_url = "http://cube:4000"
    mock.api_secret = SecretStr("test-secret")
    return mock


# ---------------------------------------------------------------------------
# Group 1: Alert plugins (no config param in __init__)
# These are the clearest failures — without super().__init__(), _config
# attribute does not exist at all.
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-001")
def test_slack_plugin_has_config_attr() -> None:
    """SlackAlertPlugin must have _config attribute from ABC.__init__.

    Without super().__init__(), SlackAlertPlugin never sets _config,
    so hasattr will be False.
    """
    from floe_alert_slack.plugin import SlackAlertPlugin

    plugin = SlackAlertPlugin(webhook_url="https://hooks.slack.com/test")
    assert hasattr(plugin, "_config"), (
        "SlackAlertPlugin missing _config — super().__init__() not called"
    )


@pytest.mark.requirement("ARC-001")
def test_alertmanager_plugin_has_config_attr() -> None:
    """AlertmanagerPlugin must have _config attribute from ABC.__init__."""
    from floe_alert_alertmanager.plugin import AlertmanagerPlugin

    plugin = AlertmanagerPlugin(api_url="http://alertmanager:9093")
    assert hasattr(plugin, "_config"), (
        "AlertmanagerPlugin missing _config — super().__init__() not called"
    )


@pytest.mark.requirement("ARC-001")
def test_email_plugin_has_config_attr() -> None:
    """EmailAlertPlugin must have _config attribute from ABC.__init__."""
    from floe_alert_email.plugin import EmailAlertPlugin

    plugin = EmailAlertPlugin(smtp_host="mail.test.com")
    assert hasattr(plugin, "_config"), (
        "EmailAlertPlugin missing _config — super().__init__() not called"
    )


@pytest.mark.requirement("ARC-001")
def test_webhook_plugin_has_config_attr() -> None:
    """WebhookAlertPlugin must have _config attribute from ABC.__init__."""
    from floe_alert_webhook.plugin import WebhookAlertPlugin

    plugin = WebhookAlertPlugin(webhook_url="http://webhook.test/endpoint")
    assert hasattr(plugin, "_config"), (
        "WebhookAlertPlugin missing _config — super().__init__() not called"
    )


@pytest.mark.requirement("ARC-001")
def test_dlt_plugin_has_config_attr() -> None:
    """DltIngestionPlugin must have _config attribute from ABC.__init__.

    DltIngestionPlugin.__init__ takes no config param, so _config
    only appears if super().__init__() is called.
    """
    from floe_ingestion_dlt.plugin import DltIngestionPlugin

    plugin = DltIngestionPlugin()
    assert hasattr(plugin, "_config"), (
        "DltIngestionPlugin missing _config — super().__init__() not called"
    )


# ---------------------------------------------------------------------------
# Group 2: Alert plugins — is_configured must work (requires _config to exist)
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-001")
def test_slack_is_configured_returns_false() -> None:
    """SlackAlertPlugin.is_configured must return False when no config set.

    This will raise AttributeError without super().__init__() because
    the is_configured property reads self._config which won't exist.
    """
    from floe_alert_slack.plugin import SlackAlertPlugin

    plugin = SlackAlertPlugin()
    # Must not raise AttributeError — property must work
    result = plugin.is_configured
    assert result is False


@pytest.mark.requirement("ARC-001")
def test_alertmanager_is_configured_returns_false() -> None:
    """AlertmanagerPlugin.is_configured must return False when no config set."""
    from floe_alert_alertmanager.plugin import AlertmanagerPlugin

    plugin = AlertmanagerPlugin()
    result = plugin.is_configured
    assert result is False


@pytest.mark.requirement("ARC-001")
def test_email_is_configured_returns_false() -> None:
    """EmailAlertPlugin.is_configured must return False when no config set."""
    from floe_alert_email.plugin import EmailAlertPlugin

    plugin = EmailAlertPlugin()
    result = plugin.is_configured
    assert result is False


@pytest.mark.requirement("ARC-001")
def test_webhook_is_configured_returns_false() -> None:
    """WebhookAlertPlugin.is_configured must return False when no config set."""
    from floe_alert_webhook.plugin import WebhookAlertPlugin

    plugin = WebhookAlertPlugin()
    result = plugin.is_configured
    assert result is False


@pytest.mark.requirement("ARC-001")
def test_dlt_is_configured_returns_false() -> None:
    """DltIngestionPlugin.is_configured must return False (no config in __init__)."""
    from floe_ingestion_dlt.plugin import DltIngestionPlugin

    plugin = DltIngestionPlugin()
    result = plugin.is_configured
    assert result is False


# ---------------------------------------------------------------------------
# Group 3: Plugins that set _config in __init__ — is_configured must be True
# after direct instantiation with a config value.
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-001")
def test_polaris_direct_instantiation_is_configured() -> None:
    """PolarisCatalogPlugin(config=cfg) must yield is_configured == True.

    AC-3: Direct instantiation with config results in is_configured == True.
    Without super().__init__(), the property still reads self._config
    (which the plugin sets), but the ABC's __init__ is not called.
    We verify both is_configured and that _config is the provided value.
    """
    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    config = _make_polaris_config()
    plugin = PolarisCatalogPlugin(config=config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_s3_direct_instantiation_is_configured() -> None:
    """S3StoragePlugin(config=cfg) must yield is_configured == True."""
    from floe_storage_s3.plugin import S3StoragePlugin

    config = _make_s3_config()
    plugin = S3StoragePlugin(config=config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_infisical_direct_instantiation_is_configured() -> None:
    """InfisicalSecretsPlugin(config=cfg) must yield is_configured == True."""
    from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

    config = _make_infisical_config()
    plugin = InfisicalSecretsPlugin(config=config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_keycloak_direct_instantiation_is_configured() -> None:
    """KeycloakIdentityPlugin(config=cfg) must yield is_configured == True."""
    from floe_identity_keycloak.plugin import KeycloakIdentityPlugin

    config = _make_keycloak_config()
    plugin = KeycloakIdentityPlugin(config=config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_cube_direct_instantiation_is_configured() -> None:
    """CubeSemanticPlugin(config=cfg) must yield is_configured == True."""
    from floe_semantic_cube.plugin import CubeSemanticPlugin

    config = _make_cube_config()
    plugin = CubeSemanticPlugin(config=config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_k8s_direct_instantiation_is_configured() -> None:
    """K8sSecretsPlugin(config=cfg) must yield is_configured == True.

    K8sSecretsPlugin uses self.config (public), not self._config (private).
    The ABC lifecycle uses self._config. After fix, super().__init__()
    sets self._config = None, then plugin sets self.config = real_config.
    is_configured reads self._config, so it would be False unless the
    plugin also sets self._config = config AFTER super().__init__().
    """
    from floe_secrets_k8s.plugin import K8sSecretsPlugin

    config = _make_k8s_config()
    plugin = K8sSecretsPlugin(config=config)
    # _config must exist (from super().__init__) and be set to the config
    assert hasattr(plugin, "_config"), (
        "K8sSecretsPlugin missing _config — super().__init__() not called"
    )
    assert plugin.is_configured is True


# ---------------------------------------------------------------------------
# Group 4: Registry path — configure() overwrites __init__ config
# AC-4: loader creates with config=None, then registry.configure() pushes
# real config. After both, _config is the registry-provided config.
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-001")
def test_polaris_registry_path_configure_wins() -> None:
    """Registry path: configure() must overwrite __init__ config.

    Simulates: loader creates plugin(config=init_cfg), then
    registry calls plugin.configure(registry_cfg). Final _config
    must be registry_cfg, not init_cfg.
    """
    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    init_config = _make_polaris_config()
    registry_config = _make_polaris_config()
    registry_config.warehouse = "registry-warehouse"

    plugin = PolarisCatalogPlugin(config=init_config)
    assert plugin._config is init_config

    plugin.configure(registry_config)
    assert plugin._config is registry_config, (
        "configure() must override __init__ config (last-write-wins)"
    )
    assert plugin.is_configured is True


@pytest.mark.requirement("ARC-001")
def test_s3_registry_path_configure_wins() -> None:
    """Registry path: S3 configure() overwrites __init__ config."""
    from floe_storage_s3.plugin import S3StoragePlugin

    init_config = _make_s3_config()
    registry_config = _make_s3_config()

    plugin = S3StoragePlugin(config=init_config)
    plugin.configure(registry_config)
    assert plugin._config is registry_config


@pytest.mark.requirement("ARC-001")
def test_infisical_registry_path_configure_wins() -> None:
    """Registry path: Infisical configure() overwrites __init__ config."""
    from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

    init_config = _make_infisical_config()
    registry_config = _make_infisical_config()

    plugin = InfisicalSecretsPlugin(config=init_config)
    plugin.configure(registry_config)
    assert plugin._config is registry_config


@pytest.mark.requirement("ARC-001")
def test_keycloak_registry_path_configure_wins() -> None:
    """Registry path: Keycloak configure() overwrites __init__ config."""
    from floe_identity_keycloak.plugin import KeycloakIdentityPlugin

    init_config = _make_keycloak_config()
    registry_config = _make_keycloak_config()

    plugin = KeycloakIdentityPlugin(config=init_config)
    plugin.configure(registry_config)
    assert plugin._config is registry_config


@pytest.mark.requirement("ARC-001")
def test_cube_registry_path_configure_wins() -> None:
    """Registry path: Cube configure() overwrites __init__ config."""
    from floe_semantic_cube.plugin import CubeSemanticPlugin

    init_config = _make_cube_config()
    registry_config = _make_cube_config()

    plugin = CubeSemanticPlugin(config=init_config)
    plugin.configure(registry_config)
    assert plugin._config is registry_config


@pytest.mark.requirement("ARC-001")
def test_k8s_registry_path_configure_wins() -> None:
    """Registry path: K8s configure() overwrites __init__ config."""
    from floe_secrets_k8s.plugin import K8sSecretsPlugin

    init_config = _make_k8s_config()
    registry_config = _make_k8s_config()

    plugin = K8sSecretsPlugin(config=init_config)
    plugin.configure(registry_config)
    assert plugin._config is registry_config


# ---------------------------------------------------------------------------
# Group 5: Alert plugin configure() path (no config in __init__)
# Simulate registry calling configure() on a plugin created without config.
# ---------------------------------------------------------------------------


class _AlertConfig(BaseModel):
    """Minimal config for alert plugin configure() tests."""

    channel: str = "test"


@pytest.mark.requirement("ARC-001")
def test_slack_configure_sets_is_configured() -> None:
    """SlackAlertPlugin.configure() must set is_configured True."""
    from floe_alert_slack.plugin import SlackAlertPlugin

    plugin = SlackAlertPlugin()
    assert plugin.is_configured is False

    config = _AlertConfig()
    plugin.configure(config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_alertmanager_configure_sets_is_configured() -> None:
    """AlertmanagerPlugin.configure() must set is_configured True."""
    from floe_alert_alertmanager.plugin import AlertmanagerPlugin

    plugin = AlertmanagerPlugin()
    assert plugin.is_configured is False

    config = _AlertConfig()
    plugin.configure(config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_email_configure_sets_is_configured() -> None:
    """EmailAlertPlugin.configure() must set is_configured True."""
    from floe_alert_email.plugin import EmailAlertPlugin

    plugin = EmailAlertPlugin()
    assert plugin.is_configured is False

    config = _AlertConfig()
    plugin.configure(config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_webhook_configure_sets_is_configured() -> None:
    """WebhookAlertPlugin.configure() must set is_configured True."""
    from floe_alert_webhook.plugin import WebhookAlertPlugin

    plugin = WebhookAlertPlugin()
    assert plugin.is_configured is False

    config = _AlertConfig()
    plugin.configure(config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_dlt_configure_sets_is_configured() -> None:
    """DltIngestionPlugin.configure() must set is_configured True."""
    from floe_ingestion_dlt.plugin import DltIngestionPlugin

    plugin = DltIngestionPlugin()
    assert plugin.is_configured is False

    config = _AlertConfig()
    plugin.configure(config)
    assert plugin.is_configured is True
    assert plugin._config is config


# ---------------------------------------------------------------------------
# Group 6: S3 and K8s with config=None (optional config param)
# Even with None, _config must exist from super().__init__().
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-001")
def test_s3_none_config_has_config_attr() -> None:
    """S3StoragePlugin(config=None) must still have _config from ABC."""
    from floe_storage_s3.plugin import S3StoragePlugin

    plugin = S3StoragePlugin(config=None)
    assert hasattr(plugin, "_config")
    # _config should be None (ABC sets None, then plugin sets None)
    assert plugin.is_configured is False


@pytest.mark.requirement("ARC-001")
def test_k8s_none_config_has_config_attr() -> None:
    """K8sSecretsPlugin(config=None) must have _config from ABC.

    K8s defaults config to K8sSecretsConfig() when None. But _config
    (the ABC attribute) must still exist from super().__init__().
    """
    from floe_secrets_k8s.plugin import K8sSecretsPlugin

    plugin = K8sSecretsPlugin(config=None)
    assert hasattr(plugin, "_config"), (
        "K8sSecretsPlugin missing _config — super().__init__() not called"
    )


# ---------------------------------------------------------------------------
# Group 7: Verify _config initialization ORDER
# super().__init__() sets _config = None FIRST, then subclass __init__
# body sets _config = config. This ensures the attribute always exists
# even if subclass __init__ raises partway through.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Group 7a: Verify super().__init__() is actually CALLED for plugins that
# set _config themselves. Without this, a plugin could skip super() entirely
# and tests in Groups 3/4 would still pass because _config exists.
# We monkeypatch PluginMetadata.__init__ to track calls.
# ---------------------------------------------------------------------------

_SUPER_INIT_CALLED: list[bool] = []


@pytest.fixture(autouse=False)
def _track_super_init(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Monkeypatch PluginMetadata.__init__ to track whether it's called."""
    from floe_core.plugin_metadata import PluginMetadata

    original_init = PluginMetadata.__init__

    def tracked_init(self: PluginMetadata) -> None:
        _SUPER_INIT_CALLED.append(True)
        original_init(self)

    monkeypatch.setattr(PluginMetadata, "__init__", tracked_init)
    _SUPER_INIT_CALLED.clear()
    return _SUPER_INIT_CALLED


@pytest.mark.requirement("ARC-001")
def test_polaris_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """PolarisCatalogPlugin.__init__ must call super().__init__()."""
    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    _track_super_init.clear()
    PolarisCatalogPlugin(config=_make_polaris_config())
    assert len(_track_super_init) == 1, "PolarisCatalogPlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_s3_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """S3StoragePlugin.__init__ must call super().__init__()."""
    from floe_storage_s3.plugin import S3StoragePlugin

    _track_super_init.clear()
    S3StoragePlugin(config=_make_s3_config())
    assert len(_track_super_init) == 1, "S3StoragePlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_infisical_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """InfisicalSecretsPlugin.__init__ must call super().__init__()."""
    from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

    _track_super_init.clear()
    InfisicalSecretsPlugin(config=_make_infisical_config())
    assert len(_track_super_init) == 1, "InfisicalSecretsPlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_keycloak_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """KeycloakIdentityPlugin.__init__ must call super().__init__()."""
    from floe_identity_keycloak.plugin import KeycloakIdentityPlugin

    _track_super_init.clear()
    KeycloakIdentityPlugin(config=_make_keycloak_config())
    assert len(_track_super_init) == 1, "KeycloakIdentityPlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_cube_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """CubeSemanticPlugin.__init__ must call super().__init__()."""
    from floe_semantic_cube.plugin import CubeSemanticPlugin

    _track_super_init.clear()
    CubeSemanticPlugin(config=_make_cube_config())
    assert len(_track_super_init) == 1, "CubeSemanticPlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_k8s_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """K8sSecretsPlugin.__init__ must call super().__init__()."""
    from floe_secrets_k8s.plugin import K8sSecretsPlugin

    _track_super_init.clear()
    K8sSecretsPlugin(config=_make_k8s_config())
    assert len(_track_super_init) == 1, "K8sSecretsPlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_dlt_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """DltIngestionPlugin.__init__ must call super().__init__()."""
    from floe_ingestion_dlt.plugin import DltIngestionPlugin

    _track_super_init.clear()
    DltIngestionPlugin()
    assert len(_track_super_init) == 1, "DltIngestionPlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_slack_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """SlackAlertPlugin.__init__ must call super().__init__()."""
    from floe_alert_slack.plugin import SlackAlertPlugin

    _track_super_init.clear()
    SlackAlertPlugin()
    assert len(_track_super_init) == 1, "SlackAlertPlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_alertmanager_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """AlertmanagerPlugin.__init__ must call super().__init__()."""
    from floe_alert_alertmanager.plugin import AlertmanagerPlugin

    _track_super_init.clear()
    AlertmanagerPlugin()
    assert len(_track_super_init) == 1, "AlertmanagerPlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_email_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """EmailAlertPlugin.__init__ must call super().__init__()."""
    from floe_alert_email.plugin import EmailAlertPlugin

    _track_super_init.clear()
    EmailAlertPlugin()
    assert len(_track_super_init) == 1, "EmailAlertPlugin did not call super().__init__()"


@pytest.mark.requirement("ARC-001")
def test_webhook_calls_super_init(
    _track_super_init: list[bool],
) -> None:
    """WebhookAlertPlugin.__init__ must call super().__init__()."""
    from floe_alert_webhook.plugin import WebhookAlertPlugin

    _track_super_init.clear()
    WebhookAlertPlugin()
    assert len(_track_super_init) == 1, "WebhookAlertPlugin did not call super().__init__()"


# ---------------------------------------------------------------------------
# Group 7b: Verify _config initialization ORDER
# super().__init__() sets _config = None FIRST, then subclass __init__
# body sets _config = config. This ensures the attribute always exists
# even if subclass __init__ raises partway through.
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-001")
def test_polaris_config_set_after_super_init() -> None:
    """Verify Polaris sets _config AFTER super().__init__() (not before).

    The ABC sets _config = None. Then the subclass overwrites with
    the real config. If they called super() AFTER setting _config,
    super() would clobber it back to None.
    """
    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    config = _make_polaris_config()
    plugin = PolarisCatalogPlugin(config=config)

    # After construction, _config must be the provided config, NOT None.
    # This proves super().__init__() was called FIRST (set None),
    # then subclass set the real config.
    assert plugin._config is config, (
        "_config is None — super().__init__() likely called AFTER "
        "self._config = config, clobbering the value"
    )
    assert plugin.is_configured is True


@pytest.mark.requirement("ARC-001")
def test_keycloak_config_set_after_super_init() -> None:
    """Verify Keycloak sets _config AFTER super().__init__()."""
    from floe_identity_keycloak.plugin import KeycloakIdentityPlugin

    config = _make_keycloak_config()
    plugin = KeycloakIdentityPlugin(config=config)
    assert plugin._config is config
    assert plugin.is_configured is True


@pytest.mark.requirement("ARC-001")
def test_cube_config_set_after_super_init() -> None:
    """Verify Cube sets _config AFTER super().__init__()."""
    from floe_semantic_cube.plugin import CubeSemanticPlugin

    config = _make_cube_config()
    plugin = CubeSemanticPlugin(config=config)
    assert plugin._config is config
    assert plugin.is_configured is True


@pytest.mark.requirement("ARC-001")
def test_infisical_config_set_after_super_init() -> None:
    """Verify Infisical sets _config AFTER super().__init__()."""
    from floe_secrets_infisical.plugin import InfisicalSecretsPlugin

    config = _make_infisical_config()
    plugin = InfisicalSecretsPlugin(config=config)
    assert plugin._config is config
    assert plugin.is_configured is True
