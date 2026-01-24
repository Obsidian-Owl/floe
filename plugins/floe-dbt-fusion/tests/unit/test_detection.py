"""Unit tests for Fusion binary detection.

Tests for detection.py module that handles:
- Fusion CLI binary detection (FR-020)
- Fusion version parsing
- Rust adapter availability checking (FR-021)

These tests use mocked subprocess and shutil.which calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Binary Detection Tests
# ---------------------------------------------------------------------------


class TestDetectFusionBinary:
    """Tests for detect_fusion_binary() function."""

    @pytest.mark.requirement("FR-020")
    def test_detect_fusion_binary_found_in_path(
        self, mock_fusion_binary_exists: MagicMock
    ) -> None:
        """detect_fusion_binary() returns path when binary is in PATH."""
        from floe_dbt_fusion.detection import detect_fusion_binary

        result = detect_fusion_binary()

        assert result is not None
        assert result == Path("/usr/local/bin/dbt-sa-cli")
        mock_fusion_binary_exists.assert_called_once_with("dbt-sa-cli")

    @pytest.mark.requirement("FR-020")
    def test_detect_fusion_binary_not_found(
        self, mock_fusion_binary_not_found: MagicMock
    ) -> None:
        """detect_fusion_binary() returns None when binary not in PATH."""
        from floe_dbt_fusion.detection import detect_fusion_binary

        result = detect_fusion_binary()

        assert result is None
        mock_fusion_binary_not_found.assert_called_once_with("dbt-sa-cli")

    @pytest.mark.requirement("FR-020")
    def test_detect_fusion_binary_custom_binary_name(self) -> None:
        """detect_fusion_binary() uses custom binary name when provided."""
        from floe_dbt_fusion.detection import detect_fusion_binary

        with patch("shutil.which", return_value="/custom/path/fusion") as mock_which:
            result = detect_fusion_binary(binary_name="fusion")

            assert result == Path("/custom/path/fusion")
            mock_which.assert_called_once_with("fusion")

    @pytest.mark.requirement("FR-020")
    def test_detect_fusion_binary_checks_standard_paths(self) -> None:
        """detect_fusion_binary() checks standard installation paths."""
        from floe_dbt_fusion.detection import STANDARD_FUSION_PATHS, detect_fusion_binary

        # Mock shutil.which to return None (not in PATH)
        # Mock Path.exists to return True for a standard path
        with (
            patch("shutil.which", return_value=None),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "is_file", return_value=True),
        ):
            result = detect_fusion_binary()

            # Should return a path from standard paths
            assert result is not None


class TestGetFusionVersion:
    """Tests for get_fusion_version() function."""

    @pytest.mark.requirement("FR-020")
    def test_get_fusion_version_success(self) -> None:
        """get_fusion_version() parses version from CLI output."""
        from floe_dbt_fusion.detection import get_fusion_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "dbt-sa-cli 0.1.0"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            version = get_fusion_version(Path("/usr/local/bin/dbt-sa-cli"))

            assert version == "0.1.0"

    @pytest.mark.requirement("FR-020")
    def test_get_fusion_version_with_extra_output(self) -> None:
        """get_fusion_version() handles extra text in version output."""
        from floe_dbt_fusion.detection import get_fusion_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "dbt-sa-cli version 0.2.1-beta\nCopyright 2026"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            version = get_fusion_version(Path("/usr/local/bin/dbt-sa-cli"))

            assert version == "0.2.1-beta"

    @pytest.mark.requirement("FR-020")
    def test_get_fusion_version_failure(self) -> None:
        """get_fusion_version() returns None on CLI failure."""
        from floe_dbt_fusion.detection import get_fusion_version

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: command not found"

        with patch("subprocess.run", return_value=mock_result):
            version = get_fusion_version(Path("/usr/local/bin/dbt-sa-cli"))

            assert version is None

    @pytest.mark.requirement("FR-020")
    def test_get_fusion_version_binary_not_found(self) -> None:
        """get_fusion_version() returns None when binary not found."""
        from floe_dbt_fusion.detection import get_fusion_version

        with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            version = get_fusion_version(Path("/nonexistent/dbt-sa-cli"))

            assert version is None

    @pytest.mark.requirement("FR-020")
    def test_get_fusion_version_called_with_version_flag(self) -> None:
        """get_fusion_version() calls CLI with --version flag."""
        from floe_dbt_fusion.detection import get_fusion_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "dbt-sa-cli 0.1.0"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            binary_path = Path("/usr/local/bin/dbt-sa-cli")
            get_fusion_version(binary_path)

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            # First positional arg should be the command list
            assert call_args[0][0] == [str(binary_path), "--version"]


# ---------------------------------------------------------------------------
# Adapter Availability Tests
# ---------------------------------------------------------------------------


class TestCheckAdapterAvailable:
    """Tests for check_adapter_available() function."""

    @pytest.mark.requirement("FR-021")
    def test_check_adapter_available_duckdb(self) -> None:
        """check_adapter_available() returns True for DuckDB."""
        from floe_dbt_fusion.detection import check_adapter_available

        result = check_adapter_available("duckdb")

        assert result is True

    @pytest.mark.requirement("FR-021")
    def test_check_adapter_available_snowflake(self) -> None:
        """check_adapter_available() returns True for Snowflake."""
        from floe_dbt_fusion.detection import check_adapter_available

        result = check_adapter_available("snowflake")

        assert result is True

    @pytest.mark.requirement("FR-021")
    def test_check_adapter_unavailable_bigquery(self) -> None:
        """check_adapter_available() returns False for BigQuery."""
        from floe_dbt_fusion.detection import check_adapter_available

        result = check_adapter_available("bigquery")

        assert result is False

    @pytest.mark.requirement("FR-021")
    def test_check_adapter_unavailable_postgres(self) -> None:
        """check_adapter_available() returns False for PostgreSQL."""
        from floe_dbt_fusion.detection import check_adapter_available

        result = check_adapter_available("postgres")

        assert result is False

    @pytest.mark.requirement("FR-021")
    def test_check_adapter_unavailable_redshift(self) -> None:
        """check_adapter_available() returns False for Redshift."""
        from floe_dbt_fusion.detection import check_adapter_available

        result = check_adapter_available("redshift")

        assert result is False

    @pytest.mark.requirement("FR-021")
    def test_check_adapter_unavailable_databricks(self) -> None:
        """check_adapter_available() returns False for Databricks."""
        from floe_dbt_fusion.detection import check_adapter_available

        result = check_adapter_available("databricks")

        assert result is False

    @pytest.mark.requirement("FR-021")
    def test_check_adapter_case_insensitive(self) -> None:
        """check_adapter_available() is case-insensitive."""
        from floe_dbt_fusion.detection import check_adapter_available

        assert check_adapter_available("DuckDB") is True
        assert check_adapter_available("DUCKDB") is True
        assert check_adapter_available("Snowflake") is True
        assert check_adapter_available("SNOWFLAKE") is True

    @pytest.mark.requirement("FR-021")
    def test_check_adapter_unknown_returns_false(self) -> None:
        """check_adapter_available() returns False for unknown adapters."""
        from floe_dbt_fusion.detection import check_adapter_available

        result = check_adapter_available("unknown_adapter")

        assert result is False


class TestGetAvailableAdapters:
    """Tests for get_available_adapters() function."""

    @pytest.mark.requirement("FR-021")
    def test_get_available_adapters_returns_list(self) -> None:
        """get_available_adapters() returns list of supported adapters."""
        from floe_dbt_fusion.detection import get_available_adapters

        adapters = get_available_adapters()

        assert isinstance(adapters, list)
        assert "duckdb" in adapters
        assert "snowflake" in adapters

    @pytest.mark.requirement("FR-021")
    def test_get_available_adapters_does_not_include_unsupported(self) -> None:
        """get_available_adapters() does not include unsupported adapters."""
        from floe_dbt_fusion.detection import get_available_adapters

        adapters = get_available_adapters()

        assert "bigquery" not in adapters
        assert "postgres" not in adapters
        assert "redshift" not in adapters
        assert "databricks" not in adapters


# ---------------------------------------------------------------------------
# Detection Info Tests
# ---------------------------------------------------------------------------


class TestFusionDetectionInfo:
    """Tests for FusionDetectionInfo dataclass."""

    @pytest.mark.requirement("FR-020")
    def test_fusion_detection_info_available(self) -> None:
        """FusionDetectionInfo represents available Fusion installation."""
        from floe_dbt_fusion.detection import FusionDetectionInfo

        info = FusionDetectionInfo(
            available=True,
            binary_path=Path("/usr/local/bin/dbt-sa-cli"),
            version="0.1.0",
            adapters_available=["duckdb", "snowflake"],
        )

        assert info.available is True
        assert info.binary_path == Path("/usr/local/bin/dbt-sa-cli")
        assert info.version == "0.1.0"
        assert "duckdb" in info.adapters_available

    @pytest.mark.requirement("FR-020")
    def test_fusion_detection_info_not_available(self) -> None:
        """FusionDetectionInfo represents unavailable Fusion."""
        from floe_dbt_fusion.detection import FusionDetectionInfo

        info = FusionDetectionInfo(
            available=False,
            binary_path=None,
            version=None,
            adapters_available=[],
        )

        assert info.available is False
        assert info.binary_path is None
        assert info.version is None
        assert info.adapters_available == []


class TestDetectFusion:
    """Tests for detect_fusion() function that returns full detection info."""

    @pytest.mark.requirement("FR-020")
    def test_detect_fusion_success(self) -> None:
        """detect_fusion() returns complete info when Fusion available."""
        from floe_dbt_fusion.detection import detect_fusion

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "dbt-sa-cli 0.1.0"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/local/bin/dbt-sa-cli"),
            patch("subprocess.run", return_value=mock_result),
        ):
            info = detect_fusion()

            assert info.available is True
            assert info.binary_path == Path("/usr/local/bin/dbt-sa-cli")
            assert info.version == "0.1.0"
            assert "duckdb" in info.adapters_available
            assert "snowflake" in info.adapters_available

    @pytest.mark.requirement("FR-020")
    def test_detect_fusion_not_found(self) -> None:
        """detect_fusion() returns unavailable info when Fusion not found."""
        from floe_dbt_fusion.detection import detect_fusion

        with patch("shutil.which", return_value=None):
            info = detect_fusion()

            assert info.available is False
            assert info.binary_path is None
            assert info.version is None

    @pytest.mark.requirement("FR-020")
    def test_detect_fusion_version_check_fails(self) -> None:
        """detect_fusion() handles version check failure gracefully."""
        from floe_dbt_fusion.detection import detect_fusion

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error"

        with (
            patch("shutil.which", return_value="/usr/local/bin/dbt-sa-cli"),
            patch("subprocess.run", return_value=mock_result),
        ):
            info = detect_fusion()

            # Binary found but version check failed
            assert info.available is True
            assert info.binary_path == Path("/usr/local/bin/dbt-sa-cli")
            assert info.version is None  # Version unknown but binary exists
