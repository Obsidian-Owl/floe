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

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from floe_core.cli.helm.generate import generate_command
from floe_core.helm.parsing import parse_set_values, parse_value
from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    DagsterStorageBinding,
    DbtStorageBinding,
    DeploymentConfig,
    KubernetesSecretRef,
    ObservabilityConfig,
    PluginRef,
    ProductIdentity,
    ResolvedModel,
    ResolvedPlugins,
    ResolvedTransforms,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageServiceEndpoint,
)
from floe_core.schemas.telemetry import ResourceAttributes, TelemetryConfig
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION


def _write_minio_artifact(path: Path) -> None:
    """Write a minimal compiled artifact with a MinIO storage binding."""
    credential_secret_name = "floe-platform-minio-credentials"  # pragma: allowlist secret
    access_key_secret_key = "root-user"  # pragma: allowlist secret
    secret_key_secret_key = "root-password"  # pragma: allowlist secret
    artifacts = CompiledArtifacts(
        version=COMPILED_ARTIFACTS_VERSION,
        metadata=CompilationMetadata(
            compiled_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            floe_version="0.5.0",
            source_hash="sha256:test",
            product_name="demo",
            product_version="0.1.0",
        ),
        identity=ProductIdentity(
            product_id="default.demo",
            domain="default",
            repository="repo",
        ),
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="demo",
                    service_version="0.1.0",
                    deployment_environment="dev",
                    floe_namespace="default",
                    floe_product_name="demo",
                    floe_product_version="0.1.0",
                    floe_mode="dev",
                ),
            ),
            lineage_namespace="demo",
        ),
        inheritance_chain=[],
        plugins=ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0"),
            orchestrator=PluginRef(type="dagster", version="0.1.0"),
            storage=PluginRef(
                type="minio",
                version="0.1.0",
                config={
                    "endpoint": "http://floe-platform-minio:9000",
                    "bucket": "floe-iceberg",
                    "artifact_bucket": "floe-artifacts",
                    "region": "us-east-1",
                    "path_style_access": True,
                    "credential_secret_name": credential_secret_name,
                    "access_key_secret_key": access_key_secret_key,
                    "secret_key_secret_key": secret_key_secret_key,
                },
            ),
        ),
        deployment=DeploymentConfig(
            storage=StorageDeploymentBinding(
                provider="minio",
                endpoint=StorageServiceEndpoint(
                    internal_url="http://floe-platform-minio:9000",
                    external_url="http://localhost:9000",
                    region="us-east-1",
                    warehouse_path="s3://floe-iceberg",
                ),
                credentials=StorageCredentialBinding(
                    mode="kubernetes-secret",
                    secret_ref=KubernetesSecretRef(
                        name=credential_secret_name,
                        namespace="floe-system",
                        keys={
                            "accessKeyId": access_key_secret_key,
                            "secretAccessKey": secret_key_secret_key,
                        },
                    ),
                ),
                dbt=DbtStorageBinding(
                    profile_name="floe",
                    target_name="dev",
                    schema_name="analytics",
                ),
                dagster=DagsterStorageBinding(
                    resource_key="minio_storage",
                    asset_io_manager_key="iceberg_io_manager",
                ),
            )
        ),
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name="model_demo", compute="duckdb")],
            default_compute="duckdb",
        ),
    )
    artifacts.to_json_file(path)


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

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_single_environment_to_uppercase_yaml_file(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test single-env generation treats uppercase YAML suffixes as files."""
        output_file = tmp_path / "custom-values.YAML"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--env", "staging", "--output", str(output_file)],
            )

        assert result.exit_code == 0
        assert output_file.exists()
        assert not (output_file / "values-staging.yaml").exists()

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
        _write_minio_artifact(artifact_file)

        output_file = tmp_path / "values.yaml"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--artifact", str(artifact_file), "--output", str(output_file)],
            )

        assert result.exit_code == 0
        assert f"Loading artifact: {artifact_file}" in result.output

    @pytest.mark.requirement("9b-FR-060")
    def test_helm_generate_uses_storage_binding_from_artifact(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Artifact storage binding must contribute Helm values."""
        artifact_file = tmp_path / "compiled_artifacts.json"
        output_file = tmp_path / "values.yaml"
        _write_minio_artifact(artifact_file)

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                ["--artifact", str(artifact_file), "--output", str(output_file)],
            )

        assert result.exit_code == 0
        values = yaml.safe_load(output_file.read_text())
        expected_credential_secret = "floe-platform-minio-credentials"  # pragma: allowlist secret
        assert values["minio"]["enabled"] is True
        assert values["minio"]["auth"] == {"existingSecret": expected_credential_secret}
        assert values["minio"]["defaultBuckets"] == "floe-iceberg,floe-artifacts"
        assert values["polaris"]["storage"]["s3"]["endpoint"] == ("http://floe-platform-minio:9000")
        assert values["polaris"]["storage"]["s3"]["credentialSecretName"] == (
            expected_credential_secret
        )
        assert "accessKey" not in values["polaris"]["storage"]["s3"]
        assert "secretKey" not in values["polaris"]["storage"]["s3"]

    @pytest.mark.requirement("9b-FR-063")
    def test_helm_generate_user_overrides_storage_binding_values(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """User --set values must override artifact-derived storage values."""
        artifact_file = tmp_path / "compiled_artifacts.json"
        output_file = tmp_path / "values.yaml"
        _write_minio_artifact(artifact_file)

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                generate_command,
                [
                    "--artifact",
                    str(artifact_file),
                    "--output",
                    str(output_file),
                    "--set",
                    "minio.enabled=false",
                ],
            )

        assert result.exit_code == 0
        values = yaml.safe_load(output_file.read_text())
        assert values["minio"]["enabled"] is False

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
