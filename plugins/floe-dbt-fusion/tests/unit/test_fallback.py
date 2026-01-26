"""Unit tests for automatic fallback to dbt-core.

Tests for the fallback mechanism when:
- Fusion CLI binary is not found (FR-020)
- Rust adapter is unavailable (FR-021)

These tests use mocked imports and subprocess calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# check_fallback_available Tests
# ---------------------------------------------------------------------------


class TestCheckFallbackAvailable:
    """Tests for check_fallback_available() function."""

    @pytest.mark.requirement("FR-021")
    def test_check_fallback_available_returns_true(
        self, mock_fallback_available: MagicMock
    ) -> None:
        """check_fallback_available() returns True when floe-dbt-core installed."""
        from floe_dbt_fusion.errors import check_fallback_available

        result = check_fallback_available()

        assert result is True
        mock_fallback_available.assert_called_once_with("floe_dbt_core")

    @pytest.mark.requirement("FR-021")
    def test_check_fallback_not_available_returns_false(
        self, mock_fallback_not_available: MagicMock
    ) -> None:
        """check_fallback_available() returns False when floe-dbt-core not installed."""
        from floe_dbt_fusion.errors import check_fallback_available

        result = check_fallback_available()

        assert result is False
        mock_fallback_not_available.assert_called_once_with("floe_dbt_core")

    @pytest.mark.requirement("FR-021")
    def test_check_fallback_handles_import_error(self) -> None:
        """check_fallback_available() handles ImportError gracefully."""
        from floe_dbt_fusion.errors import check_fallback_available

        with patch("importlib.util.find_spec", side_effect=ImportError("test error")):
            result = check_fallback_available()

            assert result is False


# ---------------------------------------------------------------------------
# FallbackPlugin Tests
# ---------------------------------------------------------------------------


class TestFallbackPluginCreation:
    """Tests for creating a FallbackPlugin when adapter unavailable."""

    @pytest.mark.requirement("FR-021")
    def test_create_fallback_plugin_when_adapter_unavailable(self) -> None:
        """FallbackPlugin created when Rust adapter not available."""
        from floe_dbt_fusion.fallback import create_fallback_plugin

        # Mock the check to return unavailable adapter
        # Note: patch where the function is USED (fallback), not where it's DEFINED (detection)
        with (
            patch(
                "floe_dbt_fusion.fallback.check_adapter_available",
                return_value=False,
            ),
            patch(
                "floe_dbt_fusion.fallback.check_fallback_available",
                return_value=True,
            ),
        ):
            fallback = create_fallback_plugin("bigquery")

            assert fallback is not None
            assert fallback.name == "core"

    @pytest.mark.requirement("FR-021")
    def test_create_fallback_plugin_raises_when_not_installed(self) -> None:
        """FallbackPlugin raises when floe-dbt-core not installed."""
        from floe_dbt_fusion.errors import DBTAdapterUnavailableError
        from floe_dbt_fusion.fallback import create_fallback_plugin

        with (
            patch(
                "floe_dbt_fusion.fallback.check_adapter_available",
                return_value=False,
            ),
            patch(
                "floe_dbt_fusion.fallback.check_fallback_available",
                return_value=False,
            ),
        ):
            with pytest.raises(DBTAdapterUnavailableError) as exc_info:
                create_fallback_plugin("bigquery")

            assert "bigquery" in str(exc_info.value)

    @pytest.mark.requirement("FR-021")
    def test_create_fallback_plugin_returns_none_for_supported_adapter(self) -> None:
        """create_fallback_plugin returns None for supported Rust adapters.

        Note: snowflake is supported by the official Fusion CLI, not duckdb.
        """
        from floe_dbt_fusion.fallback import create_fallback_plugin

        # Snowflake IS a supported adapter in SUPPORTED_RUST_ADAPTERS
        with patch(
            "floe_dbt_fusion.fallback.check_adapter_available",
            return_value=True,
        ):
            result = create_fallback_plugin("snowflake")

            # No fallback needed for supported adapters
            assert result is None


class TestFallbackPluginBehavior:
    """Tests for FallbackPlugin behavior delegating to dbt-core."""

    @pytest.mark.requirement("FR-021")
    def test_fallback_plugin_compile_delegates_to_core(self, temp_dbt_project: Path) -> None:
        """FallbackPlugin.compile_project() delegates to DBTCorePlugin."""
        from floe_dbt_fusion.fallback import FallbackPlugin

        mock_core_plugin = MagicMock()
        mock_core_plugin.compile_project.return_value = (
            temp_dbt_project / "target" / "manifest.json"
        )

        fallback = FallbackPlugin(core_plugin=mock_core_plugin)
        result = fallback.compile_project(
            project_dir=temp_dbt_project,
            profiles_dir=temp_dbt_project,
            target="dev",
        )

        mock_core_plugin.compile_project.assert_called_once_with(
            temp_dbt_project,
            temp_dbt_project,
            "dev",
        )
        assert result == temp_dbt_project / "target" / "manifest.json"

    @pytest.mark.requirement("FR-021")
    def test_fallback_plugin_run_delegates_to_core(self, temp_dbt_project: Path) -> None:
        """FallbackPlugin.run_models() delegates to DBTCorePlugin."""
        from floe_dbt_fusion.fallback import FallbackPlugin

        mock_run_result = MagicMock()
        mock_run_result.success = True
        mock_core_plugin = MagicMock()
        mock_core_plugin.run_models.return_value = mock_run_result

        fallback = FallbackPlugin(core_plugin=mock_core_plugin)
        result = fallback.run_models(
            project_dir=temp_dbt_project,
            profiles_dir=temp_dbt_project,
            target="dev",
            select="model_a",
            exclude="model_b",
            full_refresh=True,
        )

        mock_core_plugin.run_models.assert_called_once_with(
            temp_dbt_project,
            temp_dbt_project,
            "dev",
            select="model_a",
            exclude="model_b",
            full_refresh=True,
        )
        assert result.success is True

    @pytest.mark.requirement("FR-021")
    def test_fallback_plugin_test_delegates_to_core(self, temp_dbt_project: Path) -> None:
        """FallbackPlugin.test_models() delegates to DBTCorePlugin."""
        from floe_dbt_fusion.fallback import FallbackPlugin

        mock_test_result = MagicMock()
        mock_test_result.success = True
        mock_core_plugin = MagicMock()
        mock_core_plugin.test_models.return_value = mock_test_result

        fallback = FallbackPlugin(core_plugin=mock_core_plugin)
        result = fallback.test_models(
            project_dir=temp_dbt_project,
            profiles_dir=temp_dbt_project,
            target="dev",
            select="test_a",
        )

        mock_core_plugin.test_models.assert_called_once_with(
            temp_dbt_project,
            temp_dbt_project,
            "dev",
            select="test_a",
        )
        assert result.success is True

    @pytest.mark.requirement("FR-021")
    def test_fallback_plugin_supports_parallel_returns_false(self) -> None:
        """FallbackPlugin.supports_parallel_execution() returns False.

        dbt-core is NOT thread-safe.
        """
        from floe_dbt_fusion.fallback import FallbackPlugin

        mock_core_plugin = MagicMock()
        fallback = FallbackPlugin(core_plugin=mock_core_plugin)

        assert fallback.supports_parallel_execution() is False


class TestFallbackPluginMetadata:
    """Tests for FallbackPlugin metadata properties."""

    @pytest.mark.requirement("FR-021")
    def test_fallback_plugin_name_is_core(self) -> None:
        """FallbackPlugin.name returns 'core' (delegates to dbt-core)."""
        from floe_dbt_fusion.fallback import FallbackPlugin

        mock_core_plugin = MagicMock()
        mock_core_plugin.name = "core"
        fallback = FallbackPlugin(core_plugin=mock_core_plugin)

        assert fallback.name == "core"

    @pytest.mark.requirement("FR-021")
    def test_fallback_plugin_version_from_core(self) -> None:
        """FallbackPlugin.version comes from wrapped core plugin."""
        from floe_dbt_fusion.fallback import FallbackPlugin

        mock_core_plugin = MagicMock()
        mock_core_plugin.version = "0.1.0"
        fallback = FallbackPlugin(core_plugin=mock_core_plugin)

        assert fallback.version == "0.1.0"

    @pytest.mark.requirement("FR-021")
    def test_fallback_plugin_get_runtime_metadata(self) -> None:
        """FallbackPlugin.get_runtime_metadata() includes fallback info."""
        from floe_dbt_fusion.fallback import FallbackPlugin

        mock_core_plugin = MagicMock()
        mock_core_plugin.get_runtime_metadata.return_value = {
            "runtime": "core",
            "thread_safe": False,
        }
        fallback = FallbackPlugin(core_plugin=mock_core_plugin)

        metadata = fallback.get_runtime_metadata()

        assert metadata["runtime"] == "core"
        assert metadata["fallback"] is True
        assert metadata["thread_safe"] is False


# ---------------------------------------------------------------------------
# Automatic Fallback Selection Tests
# ---------------------------------------------------------------------------


class TestAutomaticFallbackSelection:
    """Tests for automatic fallback when Fusion unavailable."""

    @pytest.mark.requirement("FR-020")
    @pytest.mark.requirement("FR-021")
    def test_get_best_plugin_returns_fusion_when_available(self) -> None:
        """get_best_plugin() returns DBTFusionPlugin when binary and adapter available.

        Note: Use snowflake as test adapter since it IS supported by Fusion CLI.
        """
        from floe_dbt_fusion.fallback import get_best_plugin

        with (
            patch.object(Path, "exists", return_value=False),
            patch("shutil.which", return_value="/usr/local/bin/dbt-sa-cli"),
            patch(
                "floe_dbt_fusion.fallback.check_adapter_available",
                return_value=True,
            ),
            patch(
                "floe_dbt_fusion.fallback.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
        ):
            plugin = get_best_plugin(adapter="snowflake")

            assert plugin.name == "fusion"

    @pytest.mark.requirement("FR-020")
    @pytest.mark.requirement("FR-021")
    def test_get_best_plugin_falls_back_when_binary_missing(self) -> None:
        """get_best_plugin() falls back to core when Fusion binary not found."""
        from floe_dbt_fusion.fallback import get_best_plugin

        with (
            patch("shutil.which", return_value=None),
            patch.object(Path, "exists", return_value=False),
            patch(
                "floe_dbt_fusion.errors.check_fallback_available",
                return_value=True,
            ),
        ):
            plugin = get_best_plugin(adapter="duckdb")

            assert plugin.name == "core"

    @pytest.mark.requirement("FR-020")
    @pytest.mark.requirement("FR-021")
    def test_get_best_plugin_falls_back_when_adapter_unavailable(self) -> None:
        """get_best_plugin() falls back to core when adapter not supported.

        Note: Use an unsupported adapter like 'mysql' to trigger fallback.
        """
        from floe_dbt_fusion.fallback import get_best_plugin

        with (
            patch.object(Path, "exists", return_value=False),
            patch("shutil.which", return_value="/usr/local/bin/dbt-sa-cli"),
            patch(
                "floe_dbt_fusion.fallback.check_adapter_available",
                return_value=False,
            ),
            patch(
                "floe_dbt_fusion.fallback.check_fallback_available",
                return_value=True,
            ),
        ):
            plugin = get_best_plugin(adapter="mysql")

            assert plugin.name == "core"

    @pytest.mark.requirement("FR-020")
    @pytest.mark.requirement("FR-021")
    def test_get_best_plugin_raises_when_no_option_available(self) -> None:
        """get_best_plugin() raises when neither Fusion nor core available."""
        from floe_dbt_fusion.errors import DBTAdapterUnavailableError
        from floe_dbt_fusion.fallback import get_best_plugin

        with (
            patch(
                "floe_dbt_fusion.fallback.detect_fusion_binary",
                return_value=None,
            ),
            patch(
                "floe_dbt_fusion.fallback.check_fallback_available",
                return_value=False,
            ),
        ):
            with pytest.raises(DBTAdapterUnavailableError) as exc_info:
                get_best_plugin(adapter="bigquery")

            # Error message includes reason, not adapter name
            assert "not installed" in str(exc_info.value)


# ---------------------------------------------------------------------------
# DBTAdapterUnavailableError Tests
# ---------------------------------------------------------------------------


class TestDBTAdapterUnavailableError:
    """Tests for DBTAdapterUnavailableError exception."""

    @pytest.mark.requirement("FR-021")
    def test_error_message_includes_adapter(self) -> None:
        """DBTAdapterUnavailableError message includes the adapter name."""
        from floe_dbt_fusion.errors import DBTAdapterUnavailableError

        error = DBTAdapterUnavailableError(adapter="bigquery")

        assert "bigquery" in str(error)

    @pytest.mark.requirement("FR-021")
    def test_error_message_includes_available_adapters(self) -> None:
        """DBTAdapterUnavailableError message lists available adapters."""
        from floe_dbt_fusion.errors import DBTAdapterUnavailableError

        error = DBTAdapterUnavailableError(
            adapter="bigquery",
            available_adapters=["duckdb", "snowflake"],
        )

        assert "duckdb" in str(error)
        assert "snowflake" in str(error)

    @pytest.mark.requirement("FR-021")
    def test_error_message_shows_fallback_status_available(self) -> None:
        """DBTAdapterUnavailableError shows fallback available."""
        from floe_dbt_fusion.errors import DBTAdapterUnavailableError

        error = DBTAdapterUnavailableError(
            adapter="bigquery",
            fallback_available=True,
        )

        assert "available" in str(error)

    @pytest.mark.requirement("FR-021")
    def test_error_message_shows_fallback_status_not_installed(self) -> None:
        """DBTAdapterUnavailableError shows fallback not installed."""
        from floe_dbt_fusion.errors import DBTAdapterUnavailableError

        error = DBTAdapterUnavailableError(
            adapter="bigquery",
            fallback_available=False,
        )

        assert "not installed" in str(error)

    @pytest.mark.requirement("FR-021")
    def test_error_attributes(self) -> None:
        """DBTAdapterUnavailableError has correct attributes."""
        from floe_dbt_fusion.errors import DBTAdapterUnavailableError

        error = DBTAdapterUnavailableError(
            adapter="postgres",
            available_adapters=["duckdb"],
            fallback_available=True,
        )

        assert error.adapter == "postgres"
        assert error.available_adapters == ["duckdb"]
        assert error.fallback_available is True


# ---------------------------------------------------------------------------
# Edge Cases Tests
# ---------------------------------------------------------------------------


class TestFallbackEdgeCases:
    """Tests for edge cases in fallback behavior."""

    @pytest.mark.requirement("FR-021")
    def test_fallback_plugin_lint_project_delegates(self, temp_dbt_project: Path) -> None:
        """FallbackPlugin.lint_project() delegates to core."""
        from floe_dbt_fusion.fallback import FallbackPlugin

        mock_lint_result = MagicMock()
        mock_lint_result.success = True
        mock_lint_result.issues = []
        mock_core_plugin = MagicMock()
        mock_core_plugin.lint_project.return_value = mock_lint_result

        fallback = FallbackPlugin(core_plugin=mock_core_plugin)
        result = fallback.lint_project(
            project_dir=temp_dbt_project,
            profiles_dir=temp_dbt_project,
            target="dev",
            fix=False,
        )

        mock_core_plugin.lint_project.assert_called_once()
        assert result.success is True

    @pytest.mark.requirement("FR-021")
    def test_fallback_preserves_error_from_core(self, temp_dbt_project: Path) -> None:
        """FallbackPlugin preserves errors from wrapped core plugin."""
        from floe_dbt_fusion.fallback import FallbackPlugin

        mock_core_plugin = MagicMock()
        mock_core_plugin.compile_project.side_effect = RuntimeError("Compilation failed")

        fallback = FallbackPlugin(core_plugin=mock_core_plugin)

        with pytest.raises(RuntimeError, match="Compilation failed"):
            fallback.compile_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
            )

    @pytest.mark.requirement("FR-021")
    def test_multiple_adapters_checked_for_availability(self) -> None:
        """Multiple adapters can be checked for availability.

        The official Fusion CLI supports: snowflake, postgres, bigquery,
        redshift, trino, datafusion, spark, databricks, salesforce.
        DuckDB is NOT supported by the official CLI.
        """
        from floe_dbt_fusion.detection import check_adapter_available

        # Supported adapters (in SUPPORTED_RUST_ADAPTERS)
        assert check_adapter_available("snowflake") is True
        assert check_adapter_available("postgres") is True
        assert check_adapter_available("bigquery") is True
        assert check_adapter_available("databricks") is True

        # Unsupported adapters (NOT in SUPPORTED_RUST_ADAPTERS)
        assert check_adapter_available("duckdb") is False
        assert check_adapter_available("mysql") is False
        assert check_adapter_available("sqlite") is False
        assert check_adapter_available("oracle") is False
