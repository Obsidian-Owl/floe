"""Unit tests for floe helm generate CLI command.

Tests the generate_command CLI implementation including argument parsing,
error handling, and output generation.

Requirements tested:
- 9b-FR-060: Helm values generation from CLI
- 9b-FR-062: Multi-environment generation
- 9b-FR-063: User overrides via --set
- 9b-FR-064: Values file merging
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from floe_core.cli.helm.generate import generate_command
from floe_core.helm.parsing import parse_set_values, parse_value


class TestParseValue:
    """Tests for parse_value helper function."""

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_null(self) -> None:
        """Test parsing 'null' string."""
        assert parse_value("null") is None
        assert parse_value("NULL") is None
        assert parse_value("Null") is None

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_bool_true(self) -> None:
        """Test parsing 'true' string."""
        assert parse_value("true") is True
        assert parse_value("TRUE") is True
        assert parse_value("True") is True

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_bool_false(self) -> None:
        """Test parsing 'false' string."""
        assert parse_value("false") is False
        assert parse_value("FALSE") is False
        assert parse_value("False") is False

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_integer(self) -> None:
        """Test parsing integer values."""
        assert parse_value("42") == 42
        assert parse_value("0") == 0
        assert parse_value("-10") == -10

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_float(self) -> None:
        """Test parsing float values."""
        assert parse_value("3.14") == pytest.approx(3.14)
        assert parse_value("0.5") == pytest.approx(0.5)
        assert parse_value("-1.5") == pytest.approx(-1.5)

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_string(self) -> None:
        """Test parsing string values."""
        assert parse_value("hello") == "hello"
        assert parse_value("test-value") == "test-value"
        assert parse_value("with spaces") == "with spaces"

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_string_with_number_prefix(self) -> None:
        """Test parsing strings that start with numbers."""
        # These should be strings, not numbers
        assert parse_value("123abc") == "123abc"
        assert parse_value("1.2.3") == "1.2.3"


class TestParseSetValues:
    """Tests for parse_set_values helper function."""

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_empty_tuple(self) -> None:
        """Test parsing empty set values."""
        result = parse_set_values(())
        assert result == {}

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_single_value(self) -> None:
        """Test parsing single key=value pair."""
        result = parse_set_values(("key=value",))
        assert result == {"key": "value"}

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_nested_values(self) -> None:
        """Test parsing nested key paths."""
        result = parse_set_values(("dagster.replicas=3",))
        assert result == {"dagster": {"replicas": 3}}

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_deeply_nested(self) -> None:
        """Test parsing deeply nested paths."""
        result = parse_set_values(("a.b.c.d=value",))
        assert result == {"a": {"b": {"c": {"d": "value"}}}}

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_multiple_values(self) -> None:
        """Test parsing multiple key=value pairs."""
        result = parse_set_values(("dagster.replicas=3", "global.env=prod", "enabled=true"))
        assert result == {
            "dagster": {"replicas": 3},
            "global": {"env": "prod"},
            "enabled": True,
        }

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_type_conversion(self) -> None:
        """Test automatic type conversion."""
        result = parse_set_values(
            (
                "int_val=42",
                "float_val=3.14",
                "bool_val=true",
                "null_val=null",
                "str_val=hello",
            )
        )
        assert result["int_val"] == 42
        assert result["float_val"] == pytest.approx(3.14)
        assert result["bool_val"] is True
        assert result["null_val"] is None
        assert result["str_val"] == "hello"

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_invalid_format_skipped(self) -> None:
        """Test that values without '=' are skipped."""
        result = parse_set_values(("key=value", "invalid", "other=test"))
        assert result == {"key": "value", "other": "test"}
        assert "invalid" not in result

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_empty_value(self) -> None:
        """Test parsing empty value after equals."""
        result = parse_set_values(("key=",))
        assert result == {"key": ""}

    @pytest.mark.requirement("9b-FR-063")
    def test_parse_value_with_equals(self) -> None:
        """Test parsing value containing equals sign."""
        result = parse_set_values(("url=http://example.com?foo=bar",))
        assert result == {"url": "http://example.com?foo=bar"}

    @pytest.mark.requirement("9b-FR-063")
    def test_warn_fn_called_for_invalid_entries(self) -> None:
        """Test that warn_fn callback is invoked for entries missing '='."""
        warnings: list[str] = []
        result = parse_set_values(
            ("key=value", "no-equals", "other=test"),
            warn_fn=warnings.append,
        )
        assert result == {"key": "value", "other": "test"}
        assert len(warnings) == 1
        assert "no-equals" in warnings[0]

    @pytest.mark.requirement("9b-FR-063")
    def test_warn_fn_none_silently_skips(self) -> None:
        """Test that warn_fn=None silently skips invalid entries."""
        result = parse_set_values(
            ("key=value", "no-equals"),
            warn_fn=None,
        )
        assert result == {"key": "value"}


class TestGenerateCommand:
    """Tests for generate_command CLI function."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create Click CLI test runner."""
        return CliRunner()

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_default_dev_environment(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test generating with default dev environment."""
        output_dir = tmp_path / "output"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--output-dir", str(output_dir)],
            )

        assert result.exit_code == 0
        assert "Generated" in result.output

    @pytest.mark.requirement("9b-FR-062")
    def test_generate_multiple_environments(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test generating values for multiple environments."""
        output_dir = tmp_path / "output"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                [
                    "--env",
                    "dev",
                    "--env",
                    "staging",
                    "--env",
                    "prod",
                    "--output-dir",
                    str(output_dir),
                ],
            )

        assert result.exit_code == 0
        assert "Generated 3 values files" in result.output
        assert (output_dir / "values-dev.yaml").exists()
        assert (output_dir / "values-staging.yaml").exists()
        assert (output_dir / "values-prod.yaml").exists()

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_single_environment_to_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test generating single environment to specific file."""
        output_file = tmp_path / "custom-values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--env", "staging", "--output", str(output_file)],
            )

        assert result.exit_code == 0
        assert output_file.exists()
        with output_file.open() as f:
            values = yaml.safe_load(f)
        assert values["global"]["environment"] == "staging"

    @pytest.mark.requirement("9b-FR-063")
    def test_generate_with_set_values(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test generating with --set overrides."""
        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                [
                    "--output",
                    str(output_file),
                    "--set",
                    "dagster.replicas=5",
                    "--set",
                    "global.custom=test",
                ],
            )

        assert result.exit_code == 0
        with output_file.open() as f:
            values = yaml.safe_load(f)
        assert values["dagster"]["replicas"] == 5
        assert values["global"]["custom"] == "test"

    @pytest.mark.requirement("9b-FR-064")
    def test_generate_with_values_files(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test generating with additional values files."""
        # Create additional values file
        additional_values = {"custom": {"key": "value"}, "dagster": {"enabled": True}}
        values_file = tmp_path / "additional.yaml"
        with values_file.open("w") as f:
            yaml.safe_dump(additional_values, f)

        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--output", str(output_file), "--values", str(values_file)],
            )

        assert result.exit_code == 0
        with output_file.open() as f:
            values = yaml.safe_load(f)
        assert values["custom"]["key"] == "value"
        assert values["dagster"]["enabled"] is True

    @pytest.mark.requirement("9b-FR-064")
    def test_generate_with_multiple_values_files(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test generating with multiple values files."""
        values1 = {"a": {"b": 1}}
        values2 = {"a": {"c": 2}}

        file1 = tmp_path / "values1.yaml"
        file2 = tmp_path / "values2.yaml"

        with file1.open("w") as f:
            yaml.safe_dump(values1, f)
        with file2.open("w") as f:
            yaml.safe_dump(values2, f)

        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                [
                    "--output",
                    str(output_file),
                    "--values",
                    str(file1),
                    "--values",
                    str(file2),
                ],
            )

        assert result.exit_code == 0
        with output_file.open() as f:
            values = yaml.safe_load(f)
        # Both should be merged
        assert values["a"]["b"] == 1
        assert values["a"]["c"] == 2

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_dry_run_single_env(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test dry-run mode for single environment."""
        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--output", str(output_file), "--dry-run"],
            )

        assert result.exit_code == 0
        assert "Dry-run mode" in result.output
        assert "Would generate:" in result.output
        assert "Dry-run complete" in result.output
        # File should NOT be created
        assert not output_file.exists()

    @pytest.mark.requirement("9b-FR-062")
    def test_generate_dry_run_multi_env(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test dry-run mode for multiple environments."""
        output_dir = tmp_path / "output"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                [
                    "--env",
                    "dev",
                    "--env",
                    "staging",
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ],
            )

        assert result.exit_code == 0
        assert "Dry-run mode" in result.output
        assert "Would generate values for environments" in result.output
        assert "values-dev.yaml" in result.output
        assert "values-staging.yaml" in result.output
        # Files should NOT be created
        assert not output_dir.exists()

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_artifact_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test error when artifact file not found."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--artifact", "/nonexistent/artifact.json"],
            )

        assert result.exit_code != 0
        assert "Artifact file not found" in result.output

    @pytest.mark.requirement("9b-FR-064")
    def test_generate_values_file_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test error when values file not found."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--values", "/nonexistent/values.yaml"],
            )

        # Click validates file existence, so this fails at click level
        assert result.exit_code != 0

    @pytest.mark.requirement("9b-FR-064")
    def test_generate_invalid_values_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test error when values file contains invalid YAML."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("not: valid: yaml: {{{")

        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--output", str(output_file), "--values", str(invalid_file)],
            )

        assert result.exit_code != 0
        assert "Failed to load values file" in result.output

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_oci_artifact_placeholder(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test OCI artifact support shows placeholder message."""
        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                [
                    "--artifact",
                    "oci://registry.example.com/floe:v1.0",
                    "--output",
                    str(output_file),
                ],
            )

        assert result.exit_code == 0
        assert "OCI artifact support planned" in result.output

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_artifact_file_exists(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test loading artifact from file path."""
        artifact_file = tmp_path / "artifact.json"
        artifact_file.write_text('{"version": "1.0"}')

        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--artifact", str(artifact_file), "--output", str(output_file)],
            )

        assert result.exit_code == 0
        assert f"Loading artifact: {artifact_file}" in result.output

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_default_output_directory(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test default output directory is target/helm."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(generate_command, [])

            # Should use default target/helm directory and succeed
            assert result.exit_code == 0
            # Default creates target/helm/values-dev.yaml
            expected_dir = Path("target") / "helm"
            expected_file = expected_dir / "values-dev.yaml"
            assert expected_file.exists()

    @pytest.mark.requirement("9b-FR-062")
    def test_generate_multi_env_output_is_directory(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test multi-env generation uses output as directory."""
        output_dir = tmp_path / "helm"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                [
                    "--env",
                    "dev",
                    "--env",
                    "staging",
                    "--output",
                    str(output_dir),
                ],
            )

        assert result.exit_code == 0
        # Should create files in output directory
        assert (output_dir / "values-dev.yaml").exists()
        assert (output_dir / "values-staging.yaml").exists()

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_single_env_output_without_extension(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test single-env generation with output path without extension."""
        output_dir = tmp_path / "helm"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--env", "staging", "--output", str(output_dir)],
            )

        assert result.exit_code == 0
        # Should append values-{env}.yaml
        assert (output_dir / "values-staging.yaml").exists()

    @pytest.mark.requirement("9b-FR-064")
    def test_generate_values_file_empty(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test values file that is empty is handled gracefully."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--output", str(output_file), "--values", str(empty_file)],
            )

        # Should succeed (empty YAML is None, which is filtered)
        assert result.exit_code == 0

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_exception_during_generation(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test error handling when generation fails."""
        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            with patch("floe_core.cli.helm.generate.HelmValuesGenerator") as mock_gen:
                mock_gen.return_value.generate.side_effect = Exception("Generation error")

                result = runner.invoke(
                    generate_command,
                    ["--output", str(output_file)],
                )

        assert result.exit_code != 0
        assert "Helm values generation failed" in result.output
