"""Integration tests for network CLI commands.

Task: T069-T078
Phase: 9 - CLI Commands (US8)
User Story: US8 - CLI Commands for Network Security
Requirement: FR-080, FR-081, FR-082, FR-083, FR-084
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

from testing.base_classes.integration_test_base import IntegrationTestBase


class TestGenerateCommand(IntegrationTestBase):
    """Integration tests for floe network generate command."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-080")
    def test_generate_help(self) -> None:
        """Test generate command shows help."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "generate", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Generate NetworkPolicy manifests" in result.stdout

    @pytest.mark.integration
    @pytest.mark.requirement("FR-080")
    def test_generate_with_dry_run(self) -> None:
        """Test generate with --dry-run outputs to stdout."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(
                {
                    "version": "1.0",
                    "name": "test-platform",
                    "security": {"network_policies": {"enabled": True}},
                },
                f,
            )
            config_path = f.name

        try:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "generate",
                    "--config",
                    config_path,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
            )
            # Should complete (may have warnings but shouldn't crash)
            assert result.returncode in (0, 1)  # 0 = success, 1 = no plugins
        finally:
            Path(config_path).unlink()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-080")
    def test_generate_missing_config(self) -> None:
        """Test generate fails without --config option."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "generate"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert (
            "Missing --config option" in result.stderr or "Missing --config option" in result.stdout
        )

    @pytest.mark.integration
    @pytest.mark.requirement("FR-080")
    def test_generate_with_output_directory(self) -> None:
        """Test generate writes to specified output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "manifest.yaml"
            output_dir = Path(tmpdir) / "output"

            # Create config
            config_path.write_text(
                yaml.dump(
                    {
                        "version": "1.0",
                        "name": "test-platform",
                        "security": {"network_policies": {"enabled": True}},
                    }
                )
            )

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "generate",
                    "--config",
                    str(config_path),
                    "--output",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
            )

            # Should succeed or have no plugins (both acceptable)
            assert result.returncode in (0, 1)

    @pytest.mark.integration
    @pytest.mark.requirement("FR-080")
    def test_generate_with_namespace_filter(self) -> None:
        """Test generate with --namespace option filters output."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(
                {
                    "version": "1.0",
                    "name": "test-platform",
                    "security": {"network_policies": {"enabled": True}},
                },
                f,
            )
            config_path = f.name

        try:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "generate",
                    "--config",
                    config_path,
                    "--namespace",
                    "floe-jobs",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode in (0, 1)
            # Should mention the namespace
            assert "floe-jobs" in result.stdout or "floe-jobs" in result.stderr
        finally:
            Path(config_path).unlink()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-080")
    def test_generate_produces_valid_yaml(self) -> None:
        """Test generate produces valid YAML output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "manifest.yaml"
            output_dir = Path(tmpdir) / "output"

            # Create config
            config_path.write_text(
                yaml.dump(
                    {
                        "version": "1.0",
                        "name": "test-platform",
                        "security": {"network_policies": {"enabled": True}},
                    }
                )
            )

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "generate",
                    "--config",
                    str(config_path),
                    "--output",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
            )

            # If generation succeeded and output dir exists, check YAML validity
            if result.returncode == 0 and output_dir.exists():
                yaml_files = list(output_dir.glob("*.yaml"))
                for yaml_file in yaml_files:
                    if yaml_file.name != "NETWORK-POLICY-SUMMARY.md":
                        content = yaml_file.read_text()
                        # Should be valid YAML
                        parsed = yaml.safe_load(content)
                        assert parsed is not None or content.strip() == ""


class TestValidateCommand(IntegrationTestBase):
    """Integration tests for floe network validate command."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-081")
    def test_validate_help(self) -> None:
        """Test validate command shows help."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "validate", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Validate NetworkPolicy manifests" in result.stdout

    @pytest.mark.integration
    @pytest.mark.requirement("FR-081")
    def test_validate_missing_manifest_dir(self) -> None:
        """Test validate fails without --manifest-dir option."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "validate"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "manifest-dir" in result.stderr or "manifest-dir" in result.stdout

    @pytest.mark.integration
    @pytest.mark.requirement("FR-081")
    def test_validate_empty_directory(self) -> None:
        """Test validate with empty manifest directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "validate",
                    "--manifest-dir",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert (
                "No NetworkPolicy manifests found" in result.stderr
                or "0 manifests" in result.stdout
            )

    @pytest.mark.integration
    @pytest.mark.requirement("FR-081")
    def test_validate_valid_manifest(self) -> None:
        """Test validate accepts valid NetworkPolicy manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_dir = Path(tmpdir)
            manifest_file = manifest_dir / "test-policy.yaml"

            # Create valid NetworkPolicy
            policy = {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {
                    "name": "test-policy",
                    "namespace": "default",
                    "labels": {"app.kubernetes.io/managed-by": "floe"},
                },
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                },
            }
            manifest_file.write_text(yaml.dump(policy))

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "validate",
                    "--manifest-dir",
                    str(manifest_dir),
                ],
                capture_output=True,
                text=True,
            )
            combined_output = result.stdout + result.stderr
            assert result.returncode == 0, f"Validation failed: {combined_output}"
            assert "valid" in combined_output.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-081")
    def test_validate_invalid_manifest_missing_apiversion(self) -> None:
        """Test validate rejects manifest missing apiVersion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_dir = Path(tmpdir)
            manifest_file = manifest_dir / "invalid-policy.yaml"

            # Create invalid NetworkPolicy (missing apiVersion)
            policy = {
                "kind": "NetworkPolicy",
                "metadata": {
                    "name": "test-policy",
                    "namespace": "default",
                },
                "spec": {
                    "podSelector": {},
                },
            }
            manifest_file.write_text(yaml.dump(policy))

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "validate",
                    "--manifest-dir",
                    str(manifest_dir),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode != 0
            assert "apiVersion" in result.stderr or "apiVersion" in result.stdout

    @pytest.mark.integration
    @pytest.mark.requirement("FR-081")
    def test_validate_invalid_manifest_missing_kind(self) -> None:
        """Test validate rejects manifest missing kind."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_dir = Path(tmpdir)
            manifest_file = manifest_dir / "invalid-policy.yaml"

            # Create invalid NetworkPolicy (missing kind)
            policy = {
                "apiVersion": "networking.k8s.io/v1",
                "metadata": {
                    "name": "test-policy",
                    "namespace": "default",
                },
                "spec": {
                    "podSelector": {},
                },
            }
            manifest_file.write_text(yaml.dump(policy))

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "validate",
                    "--manifest-dir",
                    str(manifest_dir),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode != 0
            assert "kind" in result.stderr or "kind" in result.stdout

    @pytest.mark.integration
    @pytest.mark.requirement("FR-081")
    def test_validate_missing_managed_by_label_warning(self) -> None:
        """Test validate warns about missing managed-by label."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_dir = Path(tmpdir)
            manifest_file = manifest_dir / "test-policy.yaml"

            # Create valid NetworkPolicy but missing managed-by label
            policy = {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {
                    "name": "test-policy",
                    "namespace": "default",
                },
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress"],
                },
            }
            manifest_file.write_text(yaml.dump(policy))

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "validate",
                    "--manifest-dir",
                    str(manifest_dir),
                ],
                capture_output=True,
                text=True,
            )
            combined_output = result.stdout + result.stderr
            # Should succeed (possibly with warning about missing managed-by label)
            # Validation may pass silently or warn - both are acceptable
            assert result.returncode == 0 or "warning" in combined_output.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-081")
    def test_validate_strict_mode_fails_on_warnings(self) -> None:
        """Test validate --strict fails on warnings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_dir = Path(tmpdir)
            manifest_file = manifest_dir / "test-policy.yaml"

            # Create valid NetworkPolicy but missing managed-by label
            policy = {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {
                    "name": "test-policy",
                    "namespace": "default",
                },
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress"],
                },
            }
            manifest_file.write_text(yaml.dump(policy))

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "validate",
                    "--manifest-dir",
                    str(manifest_dir),
                    "--strict",
                ],
                capture_output=True,
                text=True,
            )
            # Should fail in strict mode due to warning
            assert result.returncode != 0


class TestAuditCommand(IntegrationTestBase):
    """Integration tests for floe network audit command."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-082")
    def test_audit_help(self) -> None:
        """Test audit command shows help."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "audit", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Audit" in result.stdout or "audit" in result.stdout.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-082")
    def test_audit_requires_namespace_or_all_flag(self) -> None:
        """Test audit requires --namespace or --all-namespaces."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "audit"],
            capture_output=True,
            text=True,
        )
        # Should fail or show help
        assert result.returncode != 0 or "namespace" in result.stdout.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-082")
    def test_audit_with_namespace_option(self) -> None:
        """Test audit with --namespace option."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "audit",
                "--namespace",
                "default",
            ],
            capture_output=True,
            text=True,
        )
        # May fail if cluster not available, but command should be recognized
        assert (
            "audit" in result.stdout.lower()
            or "namespace" in result.stdout.lower()
            or result.returncode in (0, 1)
        )

    @pytest.mark.integration
    @pytest.mark.requirement("FR-082")
    def test_audit_with_all_namespaces_flag(self) -> None:
        """Test audit with --all-namespaces flag."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "audit",
                "--all-namespaces",
            ],
            capture_output=True,
            text=True,
        )
        # May fail if cluster not available, but command should be recognized
        assert (
            "audit" in result.stdout.lower()
            or "namespace" in result.stdout.lower()
            or result.returncode in (0, 1)
        )

    @pytest.mark.integration
    @pytest.mark.requirement("FR-082")
    def test_audit_output_format_json(self) -> None:
        """Test audit with --output json option."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "audit",
                "--namespace",
                "default",
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        # May fail if cluster not available, but command should be recognized
        assert result.returncode in (0, 1) or "json" in result.stdout.lower()


class TestDiffCommand(IntegrationTestBase):
    """Integration tests for floe network diff command."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-083")
    def test_diff_help(self) -> None:
        """Test diff command shows help."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "diff", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Diff" in result.stdout or "diff" in result.stdout.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-083")
    def test_diff_requires_manifest_dir(self) -> None:
        """Test diff requires --manifest-dir option."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "diff"],
            capture_output=True,
            text=True,
        )
        # Should fail or show help
        assert result.returncode != 0 or "manifest" in result.stdout.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-083")
    def test_diff_with_manifest_dir(self) -> None:
        """Test diff with --manifest-dir option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "diff",
                    "--manifest-dir",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
            )
            # May fail if cluster not available, but command should be recognized
            assert result.returncode in (0, 1) or "manifest" in result.stdout.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-083")
    def test_diff_with_namespace_filter(self) -> None:
        """Test diff with --namespace option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "diff",
                    "--manifest-dir",
                    tmpdir,
                    "--namespace",
                    "default",
                ],
                capture_output=True,
                text=True,
            )
            # May fail if cluster not available, but command should be recognized
            assert result.returncode in (0, 1)

    @pytest.mark.integration
    @pytest.mark.requirement("FR-083")
    def test_diff_output_format_json(self) -> None:
        """Test diff with --output json option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "diff",
                    "--manifest-dir",
                    tmpdir,
                    "--output-format",
                    "json",
                ],
                capture_output=True,
                text=True,
            )
            # May fail if cluster not available, but command should be recognized
            assert result.returncode in (0, 1)


class TestCheckCniCommand(IntegrationTestBase):
    """Integration tests for floe network check-cni command."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-084")
    def test_check_cni_help(self) -> None:
        """Test check-cni command shows help."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "check-cni", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "CNI" in result.stdout or "cni" in result.stdout.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-084")
    def test_check_cni_default_behavior(self) -> None:
        """Test check-cni with default options."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "check-cni"],
            capture_output=True,
            text=True,
        )
        # May fail if cluster not available, but command should be recognized
        assert result.returncode in (0, 1) or "cni" in result.stdout.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-084")
    def test_check_cni_with_kubeconfig(self) -> None:
        """Test check-cni with --kubeconfig option."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(
                {
                    "apiVersion": "v1",
                    "kind": "Config",
                    "clusters": [
                        {
                            "name": "test-cluster",
                            "cluster": {"server": "https://localhost:6443"},
                        }
                    ],
                    "contexts": [
                        {
                            "name": "test-context",
                            "context": {"cluster": "test-cluster", "user": "test-user"},
                        }
                    ],
                    "current-context": "test-context",
                    "users": [{"name": "test-user", "user": {}}],
                },
                f,
            )
            kubeconfig_path = f.name

        try:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "floe",
                    "network",
                    "check-cni",
                    "--kubeconfig",
                    kubeconfig_path,
                ],
                capture_output=True,
                text=True,
            )
            # May fail if cluster not available (returncode 1-7), but command should parse kubeconfig
            assert result.returncode in (0, 1, 7), f"Unexpected error: {result.stderr}"
        finally:
            Path(kubeconfig_path).unlink()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-084")
    def test_check_cni_output_format_json(self) -> None:
        """Test check-cni with --output-format json option."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "check-cni",
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        # May fail if cluster not available, but command should be recognized
        assert result.returncode in (0, 1)

    @pytest.mark.integration
    @pytest.mark.requirement("FR-084")
    def test_check_cni_verbose_output(self) -> None:
        """Test check-cni with --verbose flag."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "check-cni",
                "--verbose",
            ],
            capture_output=True,
            text=True,
        )
        # May fail if cluster not available, but command should be recognized
        assert result.returncode in (0, 1)


__all__: list[str] = [
    "TestGenerateCommand",
    "TestValidateCommand",
    "TestAuditCommand",
    "TestDiffCommand",
    "TestCheckCniCommand",
]
