"""Unit tests for floe platform deploy command.

Tests the deploy command CLI interface and value generation logic.

Requirements tested:
- FR-018: floe platform deploy command
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from floe_core.cli.platform.deploy import deploy_command


class TestDeployCommand:
    """Tests for deploy command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def chart_dir(self, tmp_path: Path) -> Path:
        """Create a minimal chart directory for testing."""
        chart = tmp_path / "test-chart"
        chart.mkdir()
        # Create minimal Chart.yaml
        (chart / "Chart.yaml").write_text("apiVersion: v2\nname: test\nversion: 0.1.0\n")
        # Create values.yaml
        (chart / "values.yaml").write_text(yaml.dump({"global": {"environment": "dev"}}))
        # Create values-test.yaml
        (chart / "values-test.yaml").write_text(yaml.dump({"global": {"environment": "test"}}))
        return chart

    @pytest.mark.requirement("FR-018")
    def test_dry_run_prints_command(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test --dry-run prints helm command without executing."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "helm upgrade --install" in result.output
        assert "floe-platform" in result.output

    @pytest.mark.requirement("FR-018")
    def test_dry_run_with_custom_release_name(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test --dry-run with custom release name."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "dev",
                "--chart",
                str(chart_dir),
                "--release-name",
                "my-release",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "my-release" in result.output

    @pytest.mark.requirement("FR-018")
    def test_dry_run_default_namespace(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test default namespace is derived from environment."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "staging",
                "--chart",
                str(chart_dir),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "floe-staging" in result.output

    @pytest.mark.requirement("FR-018")
    def test_dry_run_custom_namespace(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test custom namespace override."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--namespace",
                "custom-ns",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "custom-ns" in result.output

    @pytest.mark.requirement("FR-018")
    def test_dry_run_with_set_values(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test --set values appear in generated output."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--set",
                "dagster.replicas=3",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "replicas: 3" in result.output

    @pytest.mark.requirement("FR-018")
    def test_invalid_chart_path(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test error on non-existent chart path."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(tmp_path / "nonexistent"),
            ],
        )
        assert result.exit_code != 0
        assert "not exist" in result.output.lower() or "invalid" in result.output.lower()

    @pytest.mark.requirement("FR-018")
    def test_skip_schema_validation_default(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test --skip-schema-validation is on by default."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "--skip-schema-validation" in result.output

    @pytest.mark.requirement("FR-018")
    @patch("floe_core.cli.platform.deploy.subprocess")
    def test_execute_calls_helm(
        self, mock_subprocess: MagicMock, runner: CliRunner, chart_dir: Path
    ) -> None:
        """Test that deploy executes helm command."""
        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="deployed", stderr="")
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
            ],
        )
        # Should exit successfully
        assert result.exit_code == 0

        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "helm"
        assert "upgrade" in cmd
        assert "--install" in cmd

    @pytest.mark.requirement("FR-018")
    @patch("floe_core.cli.platform.deploy.subprocess")
    def test_execute_failure_shows_error(
        self, mock_subprocess: MagicMock, runner: CliRunner, chart_dir: Path
    ) -> None:
        """Test that helm failure shows error message."""
        mock_subprocess.run.side_effect = subprocess.CalledProcessError(
            1, "helm", stderr="chart not found"
        )
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
            ],
        )
        assert result.exit_code != 0
        assert "Helm deployment failed" in result.output

    @pytest.mark.requirement("FR-018")
    def test_additional_values_file(
        self, runner: CliRunner, chart_dir: Path, tmp_path: Path
    ) -> None:
        """Test merging additional values files into generated output."""
        extra_values = tmp_path / "extra.yaml"
        extra_values.write_text(yaml.dump({"custom": {"key": "value"}}))

        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--values",
                str(extra_values),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "custom:" in result.output
        assert "key: value" in result.output

    @pytest.mark.requirement("FR-018")
    def test_env_specific_values_loaded(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test that environment-specific values file is auto-loaded."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Loading environment values: values-test.yaml" in result.output

    @pytest.mark.requirement("FR-018")
    def test_set_multiple_values(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test multiple --set values are parsed correctly."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--set",
                "dagster.replicas=3",
                "--set",
                "global.debug=true",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        # Values should be in output
        assert "dagster:" in result.output or "replicas:" in result.output

    @pytest.mark.requirement("FR-018")
    def test_timeout_option(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test custom timeout is passed to helm."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--timeout",
                "15m",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "15m" in result.output

    @pytest.mark.requirement("FR-018")
    def test_default_chart_path_missing(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test error when default chart path does not exist."""
        # Change to temp directory where chart doesn't exist
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @pytest.mark.requirement("FR-018")
    def test_multiple_values_files(
        self, runner: CliRunner, chart_dir: Path, tmp_path: Path
    ) -> None:
        """Test merging multiple additional values files into output."""
        extra1 = tmp_path / "extra1.yaml"
        extra1.write_text(yaml.dump({"key1": "value1"}))

        extra2 = tmp_path / "extra2.yaml"
        extra2.write_text(yaml.dump({"key2": "value2"}))

        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--values",
                str(extra1),
                "--values",
                str(extra2),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "key1: value1" in result.output
        assert "key2: value2" in result.output

    @pytest.mark.requirement("FR-018")
    def test_set_value_type_parsing(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test that --set values are parsed to correct types in output."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--set",
                "int_val=42",
                "--set",
                "bool_val=true",
                "--set",
                "string_val=hello",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "int_val: 42" in result.output
        assert "bool_val: true" in result.output
        assert "string_val: hello" in result.output

    @pytest.mark.requirement("FR-018")
    def test_invalid_values_file(self, runner: CliRunner, chart_dir: Path, tmp_path: Path) -> None:
        """Test error on invalid YAML in values file."""
        bad_values = tmp_path / "bad.yaml"
        bad_values.write_text("invalid: yaml: content: [")

        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--values",
                str(bad_values),
            ],
        )
        assert result.exit_code != 0
        assert "Failed to load values file" in result.output

    @pytest.mark.requirement("FR-018")
    def test_dry_run_shows_values_content(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test dry-run displays generated values."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Generated values content:" in result.output
        assert "fullnameOverride:" in result.output
        assert "global:" in result.output

    @pytest.mark.requirement("FR-018")
    def test_invalid_set_value_shows_warning(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test that invalid --set entries (missing '=') produce warnings."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--set",
                "valid=ok",
                "--set",
                "no-equals-sign",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Ignoring invalid --set value" in result.output
        assert "no-equals-sign" in result.output

    @pytest.mark.requirement("FR-018")
    def test_invalid_release_name_rejected(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test that invalid release names are rejected."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--release-name",
                "INVALID_CAPS",
                "--dry-run",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid release name" in result.output

    @pytest.mark.requirement("FR-018")
    def test_invalid_namespace_rejected(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test that invalid namespace is rejected."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--namespace",
                "bad namespace!",
                "--dry-run",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid namespace" in result.output

    @pytest.mark.requirement("FR-018")
    def test_invalid_timeout_rejected(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test that invalid timeout format is rejected."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--timeout",
                "not-a-timeout",
                "--dry-run",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid timeout" in result.output

    @pytest.mark.requirement("FR-018")
    def test_empty_set_key_rejected(self, runner: CliRunner, chart_dir: Path) -> None:
        """Test that empty --set keys are warned and skipped."""
        result = runner.invoke(
            deploy_command,
            [
                "--env",
                "test",
                "--chart",
                str(chart_dir),
                "--set",
                "=value",
                "--set",
                "a..b=value",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Ignoring invalid --set key" in result.output
