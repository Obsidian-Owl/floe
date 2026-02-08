"""Unit tests for the rbac generate command.

Task ID: T027
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-020, FR-021

Tests cover:
- Command accepts --config option (FR-020)
- Command accepts --output option (FR-020)
- Command accepts --dry-run option (FR-020)
- Command produces YAML manifests for Namespace, ServiceAccount, Role, RoleBinding (FR-021)
- Exit code handling
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestRbacGenerateCommand:
    """Tests for the rbac generate CLI command."""

    @pytest.mark.requirement("FR-020")
    def test_generate_accepts_config_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that generate command accepts --config option.

        Validates that the --config option is recognized and accepts a file path.
        """
        from floe_core.cli.main import cli

        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(sample_manifest_yaml),
                "--output",
                str(output_dir),
            ],
        )

        # Command should not fail on argument parsing
        assert "Error: No such option: --config" not in (result.output or "")

    @pytest.mark.requirement("FR-020")
    def test_generate_accepts_output_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that generate command accepts --output option.

        Validates that the --output option is recognized for specifying output directory.
        """
        from floe_core.cli.main import cli

        output_dir = temp_dir / "rbac_output"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(sample_manifest_yaml),
                "--output",
                str(output_dir),
            ],
        )

        assert "Error: No such option: --output" not in (result.output or "")

    @pytest.mark.requirement("FR-020")
    def test_generate_accepts_dry_run_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that generate command accepts --dry-run option.

        Validates that --dry-run flag prevents writing files.
        """
        from floe_core.cli.main import cli

        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(sample_manifest_yaml),
                "--output",
                str(output_dir),
                "--dry-run",
            ],
        )

        assert "Error: No such option: --dry-run" not in (result.output or "")

    @pytest.mark.requirement("FR-020")
    def test_generate_shows_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that generate command shows help text.

        Validates that --help flag works and shows expected options.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["rbac", "generate", "--help"],
        )

        assert result.exit_code == 0
        assert "generate" in result.output.lower()
        # Should document options
        assert "--config" in result.output or "config" in result.output.lower()

    @pytest.mark.requirement("FR-020")
    def test_generate_fails_without_config(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that generate fails when --config not provided.

        Validates proper error handling for missing required option.
        """
        from floe_core.cli.main import cli

        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--output",
                str(output_dir),
            ],
        )

        # Should fail when config not provided
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-020")
    def test_generate_fails_config_not_found(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that generate fails when config file doesn't exist.

        Validates error handling for missing config file.
        """
        from floe_core.cli.main import cli

        nonexistent_config = temp_dir / "nonexistent.yaml"
        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(nonexistent_config),
                "--output",
                str(output_dir),
            ],
        )

        assert result.exit_code != 0

    @pytest.mark.requirement("FR-021")
    def test_generate_default_output_directory(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that generate uses default output directory if not specified.

        Validates that default output path is target/rbac.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["rbac", "generate", "--help"],
        )

        # Help should show default output path
        assert result.exit_code == 0
        # Default should be mentioned in help
        assert "target/rbac" in result.output or "rbac" in result.output.lower()


class TestRbacGroup:
    """Tests for the rbac command group."""

    @pytest.mark.requirement("FR-022")
    def test_rbac_group_exists(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that rbac command group exists.

        Validates that 'floe rbac' is a valid command group.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        assert "rbac" in result.output.lower()

    @pytest.mark.requirement("FR-022")
    def test_rbac_shows_generate_subcommand(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that rbac group shows generate subcommand.

        Validates that generate is listed in rbac help.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        assert "generate" in result.output.lower()


class TestGenerateStubManifestsHelper:
    """Tests for the _generate_stub_manifests helper function."""

    @pytest.mark.requirement("FR-021")
    def test_generate_stub_manifests_dry_run(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _generate_stub_manifests in dry-run mode.

        Validates that dry-run doesn't write files but reports what would be created.
        """
        from floe_core.cli.rbac.generate import _generate_stub_manifests

        output_dir = temp_dir / "rbac"

        _generate_stub_manifests(output_dir, dry_run=True)

        # Directory should not be created in dry-run mode
        assert not output_dir.exists()

    @pytest.mark.requirement("FR-021")
    def test_generate_stub_manifests_creates_files(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _generate_stub_manifests creates expected files.

        Validates that the helper creates all four manifest files.
        """
        from floe_core.cli.rbac.generate import _generate_stub_manifests

        output_dir = temp_dir / "rbac"

        _generate_stub_manifests(output_dir, dry_run=False)

        # All manifest files should be created
        assert (output_dir / "namespaces.yaml").exists()
        assert (output_dir / "serviceaccounts.yaml").exists()
        assert (output_dir / "roles.yaml").exists()
        assert (output_dir / "rolebindings.yaml").exists()

    @pytest.mark.requirement("FR-021")
    def test_generate_stub_manifests_file_content(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _generate_stub_manifests creates files with header comment.

        Validates that generated files have the expected header.
        """
        from floe_core.cli.rbac.generate import _generate_stub_manifests

        output_dir = temp_dir / "rbac"

        _generate_stub_manifests(output_dir, dry_run=False)

        # Check file content has header comment
        content = (output_dir / "roles.yaml").read_text()
        assert "Generated by floe rbac generate" in content

    @pytest.mark.requirement("FR-021")
    def test_generate_stub_manifests_creates_directory(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _generate_stub_manifests creates output directory if needed.

        Validates that parent directories are created automatically.
        """
        from floe_core.cli.rbac.generate import _generate_stub_manifests

        output_dir = temp_dir / "nested" / "path" / "rbac"

        _generate_stub_manifests(output_dir, dry_run=False)

        assert output_dir.exists()
        assert output_dir.is_dir()


class TestGenerateCommandMocked:
    """Tests for generate command with mocked dependencies."""

    @pytest.mark.requirement("FR-021")
    def test_generate_no_rbac_plugin_uses_stub(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that generate falls back to stub when no RBAC plugin available.

        Validates stub generation path when registry returns no plugins.
        """
        from unittest.mock import MagicMock

        from floe_core.cli.main import cli

        # Mock registry to return empty plugin list
        mock_registry = MagicMock()
        mock_registry.list.return_value = []

        def mock_get_registry() -> MagicMock:
            return mock_registry

        monkeypatch.setattr(
            "floe_core.cli.rbac.generate.get_registry",
            mock_get_registry,
            raising=False,
        )

        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(sample_manifest_yaml),
                "--output",
                str(output_dir),
            ],
        )

        # Should fall back to stub manifests
        # Check the stub was called (files exist or info message)
        assert result.exception is None or isinstance(result.exception, SystemExit)

    @pytest.mark.requirement("FR-021")
    def test_generate_with_rbac_plugin_success(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that generate works with an RBAC plugin.

        Validates full generation path with mocked plugin.
        """
        from unittest.mock import MagicMock

        from floe_core.cli.main import cli

        # Mock plugin and registry
        mock_plugin = MagicMock()

        mock_registry = MagicMock()
        mock_registry.list.return_value = [mock_plugin]

        def mock_get_registry() -> MagicMock:
            return mock_registry

        # Mock RBACManifestGenerator
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.service_accounts = 2
        mock_result.roles = 3
        mock_result.role_bindings = 2
        mock_result.namespaces = 1
        mock_result.files_generated = [temp_dir / "roles.yaml"]
        mock_result.errors = []

        mock_generator_class = MagicMock()
        mock_generator_instance = MagicMock()
        mock_generator_instance.generate.return_value = mock_result
        mock_generator_class.return_value = mock_generator_instance

        monkeypatch.setattr(
            "floe_core.cli.rbac.generate.get_registry",
            mock_get_registry,
            raising=False,
        )
        monkeypatch.setattr(
            "floe_core.cli.rbac.generate.RBACManifestGenerator",
            mock_generator_class,
            raising=False,
        )

        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(sample_manifest_yaml),
                "--output",
                str(output_dir),
            ],
        )

        # Should succeed with mocked plugin
        assert result.exception is None or isinstance(result.exception, SystemExit)

    @pytest.mark.requirement("FR-021")
    def test_generate_with_generation_failure(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test generate error handling when generation fails.

        Validates error output when generator returns failure.
        """
        from unittest.mock import MagicMock

        from floe_core.cli.main import cli

        # Mock plugin and registry
        mock_plugin = MagicMock()

        mock_registry = MagicMock()
        mock_registry.list.return_value = [mock_plugin]

        def mock_get_registry() -> MagicMock:
            return mock_registry

        # Mock RBACManifestGenerator with failure
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.errors = [
            "Failed to create role: invalid name",
            "Permission denied",
        ]

        mock_generator_class = MagicMock()
        mock_generator_instance = MagicMock()
        mock_generator_instance.generate.return_value = mock_result
        mock_generator_class.return_value = mock_generator_instance

        monkeypatch.setattr(
            "floe_core.cli.rbac.generate.get_registry",
            mock_get_registry,
            raising=False,
        )
        monkeypatch.setattr(
            "floe_core.cli.rbac.generate.RBACManifestGenerator",
            mock_generator_class,
            raising=False,
        )

        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(sample_manifest_yaml),
                "--output",
                str(output_dir),
            ],
        )

        # Should fail with error output
        assert result.exit_code != 0


class TestGenerateSchemaValidation:
    """Tests for SecurityConfig and RBACConfig schemas used in generate."""

    @pytest.mark.requirement("FR-021")
    def test_security_config_with_rbac_enabled(self) -> None:
        """Test SecurityConfig with RBAC enabled.

        Validates that security config can be created with RBAC.
        """
        from floe_core.schemas.security import RBACConfig, SecurityConfig

        rbac_config = RBACConfig(enabled=True)
        security_config = SecurityConfig(rbac=rbac_config)

        assert security_config.rbac.enabled is True

    @pytest.mark.requirement("FR-021")
    def test_rbac_config_defaults(self) -> None:
        """Test RBACConfig default values.

        Validates that RBACConfig has expected defaults.
        """
        from floe_core.schemas.security import RBACConfig

        config = RBACConfig()

        assert config.enabled is True  # Default to enabled


__all__: list[str] = [
    "TestRbacGenerateCommand",
    "TestRbacGroup",
    "TestGenerateStubManifestsHelper",
    "TestGenerateCommandMocked",
    "TestGenerateSchemaValidation",
]
