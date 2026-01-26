"""Unit tests for the network generate command.

Task ID: T069
Phase: 7 - Manifest Generator (US5)
User Story: US5 - Network and Pod Security CLI Commands
Requirements: FR-080

Tests cover:
- Command option parsing (--config, --output, --dry-run, --namespace)
- Configuration validation (missing config, file not found)
- Namespace validation (valid/invalid formats)
- Stub manifest generation (when no plugin available)
- Plugin discovery and instantiation
- Manifest generation with plugin
- Dry-run mode behavior
- Output directory handling
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import pytest

from floe_core.cli.network.generate import generate_command
from floe_core.network.result import NetworkPolicyGenerationResult

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestGenerateCommandOptions:
    """Tests for command option parsing."""

    @pytest.mark.requirement("FR-080")
    def test_accepts_config_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
    ) -> None:
        """Test that generate command accepts --config option.

        Validates that the --config option is recognized and parsed correctly.
        """
        result = cli_runner.invoke(
            generate_command,
            ["--config", str(sample_manifest_yaml_with_network)],
        )

        # Should not error on argument parsing
        assert "Error: No such option: --config" not in (result.output or "")

    @pytest.mark.requirement("FR-080")
    def test_accepts_output_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that generate command accepts --output option.

        Validates that the --output option is recognized for custom output directory.
        """
        output_dir = tmp_path / "custom-output"

        result = cli_runner.invoke(
            generate_command,
            [
                "--config",
                str(sample_manifest_yaml_with_network),
                "--output",
                str(output_dir),
            ],
        )

        assert "Error: No such option: --output" not in (result.output or "")

    @pytest.mark.requirement("FR-080")
    def test_accepts_dry_run_flag(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
    ) -> None:
        """Test that generate command accepts --dry-run flag.

        Validates that the --dry-run flag is recognized.
        """
        result = cli_runner.invoke(
            generate_command,
            ["--config", str(sample_manifest_yaml_with_network), "--dry-run"],
        )

        assert "Error: No such option: --dry-run" not in (result.output or "")

    @pytest.mark.requirement("FR-080")
    def test_accepts_namespace_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
    ) -> None:
        """Test that generate command accepts --namespace option.

        Validates that the --namespace option is recognized.
        """
        result = cli_runner.invoke(
            generate_command,
            [
                "--config",
                str(sample_manifest_yaml_with_network),
                "--namespace",
                "floe-jobs",
            ],
        )

        assert "Error: No such option: --namespace" not in (result.output or "")

    @pytest.mark.requirement("FR-080")
    def test_shows_help(self, cli_runner: CliRunner) -> None:
        """Test that generate command shows help with --help flag.

        Validates that help text is displayed and includes key information.
        """
        result = cli_runner.invoke(generate_command, ["--help"])

        assert result.exit_code == 0
        assert "Generate NetworkPolicy manifests" in (result.output or "")
        assert "--config" in (result.output or "")
        assert "--output" in (result.output or "")
        assert "--dry-run" in (result.output or "")
        assert "--namespace" in (result.output or "")


class TestConfigValidation:
    """Tests for configuration validation."""

    @pytest.mark.requirement("FR-080")
    def test_missing_config_fails(self, cli_runner: CliRunner) -> None:
        """Test that command fails when --config is not provided.

        Validates that missing config option results in usage error.
        """
        result = cli_runner.invoke(generate_command, [])

        assert result.exit_code != 0
        assert "Missing --config option" in (result.output or "")

    @pytest.mark.requirement("FR-080")
    def test_config_file_not_found(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that command fails when config file does not exist.

        Validates that non-existent config file is caught by Click validation.
        """
        nonexistent_config = tmp_path / "nonexistent.yaml"

        result = cli_runner.invoke(
            generate_command,
            ["--config", str(nonexistent_config)],
        )

        # Click's Path(exists=True) validation catches this before command runs
        assert result.exit_code != 0
        assert "does not exist" in (result.output or "").lower()


class TestNamespaceValidation:
    """Tests for namespace validation."""

    @pytest.mark.requirement("FR-080")
    def test_valid_namespace_accepted(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
    ) -> None:
        """Test that valid namespace format is accepted.

        Validates that RFC 1123 compliant namespace names are accepted.
        """
        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_discover.return_value = {}
            mock_load.return_value = MagicMock()

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--namespace",
                    "floe-jobs",
                    "--dry-run",
                ],
            )

            # Should not error on namespace validation
            assert "Invalid namespace" not in (result.output or "")

    @pytest.mark.requirement("FR-080")
    def test_invalid_namespace_rejected(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
    ) -> None:
        """Test that invalid namespace format is rejected.

        Validates that non-RFC 1123 compliant names are rejected.
        """
        result = cli_runner.invoke(
            generate_command,
            [
                "--config",
                str(sample_manifest_yaml_with_network),
                "--namespace",
                "Invalid_Namespace!",
            ],
        )

        assert result.exit_code != 0
        assert "namespace" in (result.output or "").lower()


class TestGenerateStubManifests:
    """Tests for stub manifest generation when no plugin available."""

    @pytest.mark.requirement("FR-080")
    def test_creates_output_directory(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that output directory is created when generating stubs.

        Validates that the output directory is created if it doesn't exist.
        """
        output_dir = tmp_path / "network-output"

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_discover.return_value = {}
            mock_load.return_value = MagicMock()

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            assert output_dir.exists()
            assert output_dir.is_dir()

    @pytest.mark.requirement("FR-080")
    def test_creates_stub_yaml_files(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that stub YAML files are created when no plugin available.

        Validates that default-deny stub files are created for each namespace.
        """
        output_dir = tmp_path / "network-output"

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_discover.return_value = {}
            mock_load.return_value = MagicMock()

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            # Check stub files exist
            assert (output_dir / "default-default-deny.yaml").exists()
            assert (output_dir / "floe-jobs-default-deny.yaml").exists()
            assert (output_dir / "floe-services-default-deny.yaml").exists()

            # Verify content
            content = (output_dir / "default-default-deny.yaml").read_text()
            assert "Generated by floe network generate" in content

    @pytest.mark.requirement("FR-080")
    def test_creates_summary_markdown(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that summary markdown file is created with stubs.

        Validates that NETWORK-POLICY-SUMMARY.md is created with statistics.
        """
        output_dir = tmp_path / "network-output"

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_discover.return_value = {}
            mock_load.return_value = MagicMock()

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            summary_file = output_dir / "NETWORK-POLICY-SUMMARY.md"
            assert summary_file.exists()

            content = summary_file.read_text()
            assert "Network Policy Summary" in content
            assert "Statistics" in content
            assert "Total Policies" in content

    @pytest.mark.requirement("FR-080")
    def test_dry_run_no_file_writes(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that dry-run mode does not write files for stubs.

        Validates that --dry-run prevents file creation.
        """
        output_dir = tmp_path / "network-output"

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_discover.return_value = {}
            mock_load.return_value = MagicMock()

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                    "--dry-run",
                ],
            )

            # Output directory should not be created
            assert not output_dir.exists()

            # Should show what would be created
            assert "Would create:" in (result.output or "")
            assert "default-default-deny.yaml" in (result.output or "")


class TestPluginDiscovery:
    """Tests for plugin discovery mechanism."""

    @pytest.mark.requirement("FR-080")
    def test_no_plugins_uses_stubs(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that stub implementation is used when no plugins found.

        Validates that the command falls back to stub generation.
        """
        output_dir = tmp_path / "network-output"

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_discover.return_value = {}
            mock_load.return_value = MagicMock()

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            assert "No network security plugins available" in (result.output or "")
            assert "stub implementation" in (result.output or "")

    @pytest.mark.requirement("FR-080")
    def test_plugin_found_and_instantiated(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that discovered plugin is instantiated and used.

        Validates that plugin discovery and instantiation works correctly.
        """
        output_dir = tmp_path / "network-output"

        # Create mock plugin
        mock_plugin_class = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_class.return_value = mock_plugin_instance

        # Mock generator and result
        mock_generator = MagicMock()
        mock_result = NetworkPolicyGenerationResult(
            generated_policies=[],
            policies_count=0,
        )
        mock_generator.generate.return_value = mock_result

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.network.NetworkPolicyManifestGenerator") as mock_gen_class,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_load.return_value = MagicMock()
            mock_discover.return_value = {"test-plugin": mock_plugin_class}
            mock_gen_class.return_value = mock_generator

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            # Verify plugin was instantiated
            mock_plugin_class.assert_called_once()

            # Verify generator was created with plugin
            mock_gen_class.assert_called_once_with(plugin=mock_plugin_instance)

            # Verify message about plugin usage
            assert "Using network security plugin: test-plugin" in (result.output or "")


class TestGenerateWithPlugin:
    """Tests for manifest generation with plugin."""

    @pytest.mark.requirement("FR-080")
    def test_calls_plugin_generate(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that plugin's generate method is called with namespaces.

        Validates that the generator.generate() is invoked correctly.
        """
        output_dir = tmp_path / "network-output"

        mock_plugin_class = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_class.return_value = mock_plugin_instance

        mock_generator = MagicMock()
        mock_result = NetworkPolicyGenerationResult(
            generated_policies=[],
            policies_count=0,
        )
        mock_generator.generate.return_value = mock_result

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.network.NetworkPolicyManifestGenerator") as mock_gen_class,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_load.return_value = MagicMock()
            mock_discover.return_value = {"test-plugin": mock_plugin_class}
            mock_gen_class.return_value = mock_generator

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            # Verify generate was called with default namespaces
            mock_generator.generate.assert_called_once()
            call_args = mock_generator.generate.call_args
            assert "namespaces" in call_args.kwargs
            assert "default" in call_args.kwargs["namespaces"]
            assert "floe-jobs" in call_args.kwargs["namespaces"]
            assert "floe-services" in call_args.kwargs["namespaces"]

    @pytest.mark.requirement("FR-080")
    def test_writes_manifests(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that generated manifests are written to output directory.

        Validates that write_manifests is called when not in dry-run mode.
        """
        output_dir = tmp_path / "network-output"

        mock_plugin_class = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_class.return_value = mock_plugin_instance

        mock_generator = MagicMock()
        mock_result = NetworkPolicyGenerationResult(
            generated_policies=[
                {
                    "metadata": {"namespace": "default", "name": "default-deny"},
                }
            ],
            policies_count=1,
        )
        mock_generator.generate.return_value = mock_result

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.network.NetworkPolicyManifestGenerator") as mock_gen_class,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_load.return_value = MagicMock()
            mock_discover.return_value = {"test-plugin": mock_plugin_class}
            mock_gen_class.return_value = mock_generator

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            # Verify write_manifests was called
            mock_generator.write_manifests.assert_called_once_with(mock_result, output_dir)

    @pytest.mark.requirement("FR-080")
    def test_reports_statistics(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that generation statistics are reported to user.

        Validates that policy counts and statistics are displayed.
        """
        output_dir = tmp_path / "network-output"

        mock_plugin_class = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_class.return_value = mock_plugin_instance

        mock_generator = MagicMock()
        mock_result = NetworkPolicyGenerationResult(
            generated_policies=[
                {"metadata": {"namespace": "default", "name": "policy1"}},
                {"metadata": {"namespace": "default", "name": "policy2"}},
            ],
            policies_count=2,
            default_deny_count=1,
            egress_rules_count=3,
            ingress_rules_count=2,
        )
        mock_generator.generate.return_value = mock_result

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.network.NetworkPolicyManifestGenerator") as mock_gen_class,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_load.return_value = MagicMock()
            mock_discover.return_value = {"test-plugin": mock_plugin_class}
            mock_gen_class.return_value = mock_generator

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            output = result.output or ""
            assert "Generated 2 NetworkPolicy manifests" in output
            assert "Generated 1 default-deny policies" in output
            assert "Generated 3 egress rules" in output
            assert "Generated 2 ingress rules" in output

    @pytest.mark.requirement("FR-080")
    def test_handles_empty_result(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that empty generation result is handled gracefully.

        Validates that no policies generated is reported correctly.
        """
        output_dir = tmp_path / "network-output"

        mock_plugin_class = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_class.return_value = mock_plugin_instance

        mock_generator = MagicMock()
        mock_result = NetworkPolicyGenerationResult(
            generated_policies=[],
            policies_count=0,
        )
        mock_generator.generate.return_value = mock_result

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.network.NetworkPolicyManifestGenerator") as mock_gen_class,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_load.return_value = MagicMock()
            mock_discover.return_value = {"test-plugin": mock_plugin_class}
            mock_gen_class.return_value = mock_generator

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            assert "No policies generated" in (result.output or "")
            # write_manifests should not be called for empty result
            mock_generator.write_manifests.assert_not_called()

    @pytest.mark.requirement("FR-080")
    def test_handles_warnings(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that generation warnings are displayed to user.

        Validates that warnings from generation are shown.
        """
        output_dir = tmp_path / "network-output"

        mock_plugin_class = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_class.return_value = mock_plugin_instance

        mock_generator = MagicMock()
        mock_result = NetworkPolicyGenerationResult(
            generated_policies=[
                {"metadata": {"namespace": "default", "name": "policy1"}},
            ],
            policies_count=1,
            warnings=["Deprecated egress format", "Missing ingress rules"],
        )
        mock_generator.generate.return_value = mock_result

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.network.NetworkPolicyManifestGenerator") as mock_gen_class,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_load.return_value = MagicMock()
            mock_discover.return_value = {"test-plugin": mock_plugin_class}
            mock_gen_class.return_value = mock_generator

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                ],
            )

            output = result.output or ""
            assert "Warning: Deprecated egress format" in output
            assert "Warning: Missing ingress rules" in output


class TestDryRunMode:
    """Tests for dry-run mode behavior."""

    @pytest.mark.requirement("FR-080")
    def test_shows_what_would_be_generated(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that dry-run shows what files would be generated.

        Validates that dry-run displays file paths without writing.
        """
        output_dir = tmp_path / "network-output"

        mock_plugin_class = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_class.return_value = mock_plugin_instance

        mock_generator = MagicMock()
        mock_result = NetworkPolicyGenerationResult(
            generated_policies=[
                {
                    "metadata": {"namespace": "floe-jobs", "name": "default-deny"},
                }
            ],
            policies_count=1,
        )
        mock_generator.generate.return_value = mock_result

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.network.NetworkPolicyManifestGenerator") as mock_gen_class,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_load.return_value = MagicMock()
            mock_discover.return_value = {"test-plugin": mock_plugin_class}
            mock_gen_class.return_value = mock_generator

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                    "--dry-run",
                ],
            )

            output = result.output or ""
            assert "Dry-run: would write to:" in output
            assert "floe-jobs-default-deny.yaml" in output
            assert "NETWORK-POLICY-SUMMARY.md" in output

    @pytest.mark.requirement("FR-080")
    def test_no_files_written(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that dry-run does not write any files.

        Validates that write_manifests is not called in dry-run mode.
        """
        output_dir = tmp_path / "network-output"

        mock_plugin_class = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_class.return_value = mock_plugin_instance

        mock_generator = MagicMock()
        mock_result = NetworkPolicyGenerationResult(
            generated_policies=[
                {"metadata": {"namespace": "default", "name": "policy1"}},
            ],
            policies_count=1,
        )
        mock_generator.generate.return_value = mock_result

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.network.NetworkPolicyManifestGenerator") as mock_gen_class,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_load.return_value = MagicMock()
            mock_discover.return_value = {"test-plugin": mock_plugin_class}
            mock_gen_class.return_value = mock_generator

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(output_dir),
                    "--dry-run",
                ],
            )

            # Verify write_manifests was NOT called
            mock_generator.write_manifests.assert_not_called()

            # Verify output directory was not created
            assert not output_dir.exists()


class TestOutputDirectory:
    """Tests for output directory handling."""

    @pytest.mark.requirement("FR-080")
    def test_default_output_directory(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
    ) -> None:
        """Test that default output directory is target/network.

        Validates that when --output is not specified, target/network is used.
        """
        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_discover.return_value = {}
            mock_load.return_value = MagicMock()

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--dry-run",
                ],
            )

            output = result.output or ""
            assert "Output directory: target/network" in output

    @pytest.mark.requirement("FR-080")
    def test_custom_output_directory(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that custom output directory is used when specified.

        Validates that --output option overrides default directory.
        """
        custom_dir = tmp_path / "custom" / "network"

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_discover.return_value = {}
            mock_load.return_value = MagicMock()

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(custom_dir),
                ],
            )

            # Verify custom directory was created
            assert custom_dir.exists()

    @pytest.mark.requirement("FR-080")
    def test_creates_nested_directories(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml_with_network: Path,
        tmp_path: Path,
    ) -> None:
        """Test that nested output directories are created.

        Validates that parent directories are created if they don't exist.
        """
        nested_dir = tmp_path / "level1" / "level2" / "level3" / "network"

        with (
            patch("floe_core.network.generator.discover_network_security_plugins") as mock_discover,
            patch("floe_core.compilation.loader.load_manifest") as mock_load,
        ):
            mock_discover.return_value = {}
            mock_load.return_value = MagicMock()

            result = cli_runner.invoke(
                generate_command,
                [
                    "--config",
                    str(sample_manifest_yaml_with_network),
                    "--output",
                    str(nested_dir),
                ],
            )

            # Verify all nested directories were created
            assert nested_dir.exists()
            assert nested_dir.is_dir()


__all__: list[str] = [
    "TestGenerateCommandOptions",
    "TestConfigValidation",
    "TestNamespaceValidation",
    "TestGenerateStubManifests",
    "TestPluginDiscovery",
    "TestGenerateWithPlugin",
    "TestDryRunMode",
    "TestOutputDirectory",
]
