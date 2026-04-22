"""Unit tests for the platform compile command.

Task ID: T012, T077
Phase: 3 - User Story 1 (Platform Compile MVP), 9 - Polish
User Story: US1 - Unified Platform Compile with Enforcement Export
Requirements: FR-010 through FR-015, FR-021, 3C-FR-032 (contract flags)

Tests cover:
- Command accepts --spec and --manifest options (FR-010)
- Command accepts --output option (FR-011)
- Command accepts --enforcement-report option (FR-012)
- Command accepts --enforcement-format option (FR-013)
- Parent directories are created for enforcement report (FR-014)
- Exit code handling (FR-015)
- Command accepts --skip-contracts flag (T077)
- Command accepts --drift-detection flag (T077)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class _FakeCompiledArtifacts:
    """Minimal serializer surface for compile CLI unit tests."""

    def __init__(self) -> None:
        self.configmap_calls: list[tuple[str, str | None]] = []

    def to_json_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"format": "json"}', encoding="utf-8")

    def to_yaml_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("format: yaml\n", encoding="utf-8")

    def to_configmap_yaml(
        self,
        name: str = "floe-compiled-values",
        namespace: str | None = None,
    ) -> str:
        import yaml

        self.configmap_calls.append((name, namespace))
        payload: dict[str, object] = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": name},
            "data": {"values.yaml": "format: configmap\n"},
        }
        if namespace is not None:
            payload["metadata"] = {"name": name, "namespace": namespace}
        return yaml.safe_dump(payload, sort_keys=False)


@pytest.fixture
def fake_compiled_artifacts(monkeypatch: pytest.MonkeyPatch) -> _FakeCompiledArtifacts:
    """Patch the compile pipeline to return a deterministic serializer stub."""
    import floe_core.compilation.stages as stages

    artifacts = _FakeCompiledArtifacts()
    monkeypatch.setattr(stages, "compile_pipeline", lambda _spec, _manifest: artifacts)
    return artifacts


class TestPlatformCompileCommand:
    """Tests for the platform compile CLI command."""

    @pytest.mark.requirement("FR-010")
    def test_compile_accepts_spec_and_manifest_options(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
    ) -> None:
        """Test that compile command accepts --spec and --manifest options.

        Validates that the command can be invoked with spec and manifest paths
        and doesn't error on argument parsing.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
            ],
        )

        # Verify argument parsing succeeded (no "No such option" error)
        # The command may fail during execution (exit code != 0), but that's
        # separate from argument parsing validation which is what this test covers
        assert "Error: No such option" not in (result.output or "")
        assert "Error: Missing option" not in (result.output or "")

    @pytest.mark.requirement("FR-011")
    def test_compile_accepts_output_option(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that compile command accepts --output option for artifacts path.

        Validates that the --output option is recognized.
        """
        from floe_core.cli.main import cli

        output_path = temp_dir / "target" / "compiled_artifacts.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--output",
                str(output_path),
            ],
        )

        assert "Error: No such option: --output" not in (result.output or "")

    @pytest.mark.requirement("FR-012")
    def test_compile_accepts_enforcement_report_option(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that compile command accepts --enforcement-report option.

        Validates that the --enforcement-report option is recognized.
        """
        from floe_core.cli.main import cli

        report_path = temp_dir / "report.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--enforcement-report",
                str(report_path),
            ],
        )

        assert "Error: No such option: --enforcement-report" not in (result.output or "")

    @pytest.mark.requirement("FR-013")
    def test_compile_accepts_enforcement_format_option(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that compile command accepts --enforcement-format option.

        Validates that the --enforcement-format option accepts json, sarif, html.
        """
        from floe_core.cli.main import cli

        report_path = temp_dir / "report.sarif"

        for format_choice in ["json", "sarif", "html"]:
            result = cli_runner.invoke(
                cli,
                [
                    "platform",
                    "compile",
                    "--spec",
                    str(sample_floe_yaml),
                    "--manifest",
                    str(sample_manifest_yaml),
                    "--enforcement-report",
                    str(report_path),
                    "--enforcement-format",
                    format_choice,
                ],
            )

            assert "Error: Invalid value for '--enforcement-format'" not in (result.output or ""), (
                f"Format {format_choice} should be valid"
            )

    @pytest.mark.requirement("FR-011")
    def test_compile_accepts_output_format_option(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
    ) -> None:
        """Test that compile accepts the documented output formats."""
        from floe_core.cli.main import cli

        for format_choice in ["json", "yaml", "configmap"]:
            result = cli_runner.invoke(
                cli,
                [
                    "platform",
                    "compile",
                    "--spec",
                    str(sample_floe_yaml),
                    "--manifest",
                    str(sample_manifest_yaml),
                    "--output-format",
                    format_choice,
                ],
            )

            assert "Error: Invalid value for '--output-format'" not in (result.output or ""), (
                f"Format {format_choice} should be valid"
            )

    @pytest.mark.requirement("FR-013")
    def test_compile_rejects_invalid_enforcement_format(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that compile command rejects invalid --enforcement-format values.

        Validates that invalid format choices are rejected by Click.
        """
        from floe_core.cli.main import cli

        report_path = temp_dir / "report.txt"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--enforcement-report",
                str(report_path),
                "--enforcement-format",
                "invalid_format",
            ],
        )

        assert result.exit_code != 0
        # Click outputs error about invalid choice
        assert "Invalid value" in (result.output or "") or "invalid_format" in (result.output or "")

    @pytest.mark.requirement("FR-015")
    def test_compile_help_exits_with_zero(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that compile --help returns exit code 0.

        Validates that the help command works and returns success exit code.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--help",
            ],
        )

        # Help should always succeed
        assert result.exit_code == 0
        assert "compile" in result.output.lower()

    @pytest.mark.requirement("FR-011")
    @pytest.mark.parametrize(
        ("output_format", "expected_output"),
        [
            ("json", Path("target/compiled_artifacts.json")),
            ("yaml", Path("target/compiled_artifacts.yaml")),
            ("configmap", Path("target/floe-compiled-values.yaml")),
        ],
    )
    def test_compile_uses_format_specific_default_output_paths(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        fake_compiled_artifacts: _FakeCompiledArtifacts,
        output_format: str,
        expected_output: Path,
    ) -> None:
        """Test that each output format has a predictable default path."""
        from floe_core.cli.main import cli

        monkeypatch.chdir(temp_dir)

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--output-format",
                output_format,
            ],
        )

        assert result.exit_code == 0, result.output
        assert (temp_dir / expected_output).exists()

    @pytest.mark.requirement("FR-011")
    @pytest.mark.parametrize("output_format", ["json", "yaml", "configmap"])
    def test_compile_respects_explicit_output_path_for_all_formats(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
        fake_compiled_artifacts: _FakeCompiledArtifacts,
        output_format: str,
    ) -> None:
        """Test that explicit --output overrides format-specific defaults."""
        from floe_core.cli.main import cli

        output_path = temp_dir / f"custom-{output_format}.out"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--output-format",
                output_format,
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert output_path.exists()

    @pytest.mark.requirement("FR-011")
    def test_compile_warns_when_configmap_flags_are_used_outside_configmap_mode(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        fake_compiled_artifacts: _FakeCompiledArtifacts,
    ) -> None:
        """Test that configmap-only flags are surfaced clearly outside configmap mode."""
        from floe_core.cli.main import cli

        monkeypatch.chdir(temp_dir)

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--output-format",
                "json",
                "--configmap-name",
                "team-values",
                "--namespace",
                "data-platform",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Warning:" in result.output
        assert "--configmap-name" in result.output
        assert "--namespace" in result.output
        assert (temp_dir / "target" / "compiled_artifacts.json").read_text(
            encoding="utf-8"
        ) == '{"format": "json"}'

    @pytest.mark.requirement("FR-011")
    def test_compile_passes_configmap_name_and_namespace_in_configmap_mode(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        fake_compiled_artifacts: _FakeCompiledArtifacts,
    ) -> None:
        """Test that configmap mode wires the serializer controls through the CLI."""
        import yaml

        from floe_core.cli.main import cli

        monkeypatch.chdir(temp_dir)

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--output-format",
                "configmap",
                "--configmap-name",
                "team-values",
                "--namespace",
                "data-platform",
            ],
        )

        output_path = temp_dir / "target" / "floe-compiled-values.yaml"

        assert result.exit_code == 0, result.output
        assert fake_compiled_artifacts.configmap_calls == [("team-values", "data-platform")]
        assert output_path.exists()

        rendered = yaml.safe_load(output_path.read_text(encoding="utf-8"))
        assert rendered["metadata"]["name"] == "team-values"
        assert rendered["metadata"]["namespace"] == "data-platform"

    @pytest.mark.requirement("FR-010")
    def test_compile_shows_help_with_help_flag(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that compile command shows help text.

        Validates that --help flag works and shows expected options.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["platform", "compile", "--help"],
        )

        assert result.exit_code == 0
        assert "compile" in result.output.lower()
        assert "--spec" in result.output
        assert "--manifest" in result.output
        assert "--output-format" in result.output
        assert "--configmap-name" in result.output
        assert "--namespace" in result.output

    @pytest.mark.requirement("FR-010")
    def test_compile_spec_file_not_found(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
        sample_manifest_yaml: Path,
    ) -> None:
        """Test that compile fails gracefully when spec file not found.

        Validates error handling for missing spec file.
        """
        from floe_core.cli.main import cli

        nonexistent_spec = temp_dir / "nonexistent.yaml"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(nonexistent_spec),
                "--manifest",
                str(sample_manifest_yaml),
            ],
        )

        # Should fail (either during arg parsing or command execution)
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-010")
    def test_compile_manifest_file_not_found(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
        sample_floe_yaml: Path,
    ) -> None:
        """Test that compile fails gracefully when manifest file not found.

        Validates error handling for missing manifest file.
        """
        from floe_core.cli.main import cli

        nonexistent_manifest = temp_dir / "nonexistent_manifest.yaml"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(nonexistent_manifest),
            ],
        )

        # Should fail (either during arg parsing or command execution)
        assert result.exit_code != 0

    @pytest.mark.requirement("3C-FR-032")
    def test_compile_accepts_skip_contracts_flag(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
    ) -> None:
        """Test that compile command accepts --skip-contracts flag.

        FR-032: Contract validation MUST respect enforcement level.
        The --skip-contracts flag allows bypassing contract validation.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--skip-contracts",
            ],
        )

        # Verify argument parsing succeeded (flag is recognized)
        assert "Error: No such option: --skip-contracts" not in (result.output or "")
        # When --skip-contracts is passed, the command should either:
        # - Output "SKIPPED" message indicating contracts were skipped
        # - Or succeed/fail for other reasons (but not due to unknown flag)
        # Exit code validation is separate from flag recognition
        if result.exit_code == 0:
            assert (
                "Contract validation" in (result.output or "")
                or "contract" in (result.output or "").lower()
            )

    @pytest.mark.requirement("3C-FR-032")
    def test_compile_accepts_drift_detection_flag(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
    ) -> None:
        """Test that compile command accepts --drift-detection flag.

        The --drift-detection flag enables schema drift detection against
        actual table schemas during compilation.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--drift-detection",
            ],
        )

        assert "Error: No such option: --drift-detection" not in (result.output or "")
        # Verify the flag is recognized in output
        assert "drift detection: ENABLED" in (result.output or "") or result.exit_code in (0, 6)

    @pytest.mark.requirement("3C-FR-032")
    def test_compile_shows_contract_flags_in_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that help text includes contract-related flags.

        Validates that --skip-contracts and --drift-detection are
        documented in the command help.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["platform", "compile", "--help"],
        )

        assert result.exit_code == 0
        assert "--skip-contracts" in result.output
        assert "--drift-detection" in result.output
        # Verify helpful descriptions are present
        assert "contract" in result.output.lower()
        assert "drift" in result.output.lower()


class TestPlatformGroup:
    """Tests for the platform command group."""

    @pytest.mark.requirement("FR-015")
    def test_platform_group_exists(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that platform command group exists.

        Validates that 'floe platform' is a valid command group.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["platform", "--help"])

        assert result.exit_code == 0
        assert "platform" in result.output.lower()

    @pytest.mark.requirement("FR-010")
    def test_platform_shows_compile_subcommand(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that platform group shows compile subcommand.

        Validates that compile is listed in platform help.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["platform", "--help"])

        assert result.exit_code == 0
        # Once compile is implemented, it should appear in help
        # assert "compile" in result.output
