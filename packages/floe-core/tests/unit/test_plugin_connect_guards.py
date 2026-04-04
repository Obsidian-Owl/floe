"""Tests for connect() guards against unconfigured state (AC-4).

Verifies that Polaris connect() and S3 get_pyiceberg_fileio() raise
PluginConfigurationError when self._config is None.
"""

from __future__ import annotations

import pytest

from floe_core.plugin_errors import PluginConfigurationError


@pytest.mark.requirement("ARC-001")
def test_polaris_connect_raises_when_unconfigured() -> None:
    """Polaris connect() must raise PluginConfigurationError when _config is None.

    AC-4 condition 1: connect() raises PluginConfigurationError when not configured.
    """
    from unittest.mock import MagicMock

    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    config = MagicMock()
    plugin = PolarisCatalogPlugin(config=config)
    # Reset config to simulate unconfigured state
    plugin.configure(None)
    assert plugin.is_configured is False

    with pytest.raises(PluginConfigurationError, match="not configured"):
        plugin.connect({})


@pytest.mark.requirement("ARC-001")
def test_polaris_connect_error_includes_plugin_name() -> None:
    """Polaris connect() error message must include plugin name.

    AC-4 condition 3: Error message includes plugin name and 'not configured'.
    """
    from unittest.mock import MagicMock

    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    config = MagicMock()
    plugin = PolarisCatalogPlugin(config=config)
    plugin.configure(None)

    with pytest.raises(PluginConfigurationError) as exc_info:
        plugin.connect({})

    assert "polaris" in str(exc_info.value).lower()


@pytest.mark.requirement("ARC-001")
def test_s3_get_pyiceberg_fileio_raises_when_unconfigured() -> None:
    """S3 get_pyiceberg_fileio() must raise PluginConfigurationError when unconfigured.

    AC-4 condition 2: get_pyiceberg_fileio() raises PluginConfigurationError.
    """
    from floe_storage_s3.plugin import S3StoragePlugin

    plugin = S3StoragePlugin(config=None)
    assert plugin.is_configured is False

    with pytest.raises(PluginConfigurationError, match="not configured"):
        plugin.get_pyiceberg_fileio()


@pytest.mark.requirement("ARC-001")
def test_s3_error_includes_plugin_name() -> None:
    """S3 error message must include plugin name.

    AC-4 condition 3: Error message includes plugin name and 'not configured'.
    """
    from floe_storage_s3.plugin import S3StoragePlugin

    plugin = S3StoragePlugin(config=None)

    with pytest.raises(PluginConfigurationError) as exc_info:
        plugin.get_pyiceberg_fileio()

    assert "s3" in str(exc_info.value).lower()


@pytest.mark.requirement("ARC-001")
def test_polaris_connect_after_configure_none_raises() -> None:
    """Calling connect() after configure(None) on a previously-configured plugin raises.

    AC-6 condition 6: config reset edge case.
    """
    from unittest.mock import MagicMock

    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    config = MagicMock()
    plugin = PolarisCatalogPlugin(config=config)
    assert plugin.is_configured is True

    # Reset config
    plugin.configure(None)
    assert plugin.is_configured is False

    with pytest.raises(PluginConfigurationError, match="not configured"):
        plugin.connect({})


@pytest.mark.requirement("ARC-001")
def test_s3_fileio_after_configure_none_raises() -> None:
    """Calling get_pyiceberg_fileio() after configure(None) raises.

    AC-6 condition 6: config reset edge case.
    """
    from unittest.mock import MagicMock

    from floe_storage_s3.config import S3StorageConfig
    from floe_storage_s3.plugin import S3StoragePlugin

    config = MagicMock(spec=S3StorageConfig)
    plugin = S3StoragePlugin(config=config)
    assert plugin.is_configured is True

    # Reset config
    plugin.configure(None)
    assert plugin.is_configured is False

    with pytest.raises(PluginConfigurationError, match="not configured"):
        plugin.get_pyiceberg_fileio()
