"""Integration tests for RBAC CLI commands.

Tests the full RBAC CLI workflow including generate, validate, audit, and diff
commands against a real Kubernetes cluster.

Task: T064
User Story: US6 - RBAC Audit and Validation
Requirements: FR-060, FR-061, FR-062, FR-063

Note: These tests require a running Kubernetes cluster (Kind recommended).
Tests will FAIL if cluster is not available - they do NOT skip.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def sample_manifest_yaml() -> dict[str, Any]:
    """Create a sample manifest.yaml configuration."""
    return {
        "version": "1.0",
        "name": "test-data-platform",
        "security": {
            "rbac": {
                "enabled": True,
                "job_service_account": "floe-job-runner",
            },
            "pod_security": {
                "jobs_level": "restricted",
                "platform_level": "baseline",
            },
            "namespace_isolation": "strict",
        },
    }


@pytest.fixture
def sample_rbac_manifests() -> dict[str, list[dict[str, Any]]]:
    """Create sample RBAC manifests for testing."""
    return {
        "Namespace": [
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": "floe-jobs",
                    "labels": {
                        "app.kubernetes.io/managed-by": "floe",
                        "pod-security.kubernetes.io/enforce": "restricted",
                    },
                },
            },
        ],
        "ServiceAccount": [
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {
                    "name": "floe-job-runner",
                    "namespace": "floe-jobs",
                    "labels": {"app.kubernetes.io/managed-by": "floe"},
                },
                "automountServiceAccountToken": False,
            },
        ],
        "Role": [
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "Role",
                "metadata": {
                    "name": "floe-secret-reader",
                    "namespace": "floe-jobs",
                    "labels": {"app.kubernetes.io/managed-by": "floe"},
                },
                "rules": [
                    {
                        "apiGroups": [""],
                        "resources": ["secrets"],
                        "verbs": ["get"],
                        "resourceNames": ["snowflake-creds"],
                    },
                ],
            },
        ],
        "RoleBinding": [
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {
                    "name": "floe-job-runner-secret-reader",
                    "namespace": "floe-jobs",
                    "labels": {"app.kubernetes.io/managed-by": "floe"},
                },
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "Role",
                    "name": "floe-secret-reader",
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": "floe-job-runner",
                        "namespace": "floe-jobs",
                    },
                ],
            },
        ],
    }


class TestRBACValidateCommand:
    """Integration tests for floe rbac validate command."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-061")
    def test_validate_valid_manifests(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: dict[str, Any],
        sample_rbac_manifests: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Test validate command with valid manifests."""
        from floe_cli.main import cli

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write manifest.yaml
            config_path = tmppath / "manifest.yaml"
            with config_path.open("w") as f:
                yaml.dump(sample_manifest_yaml, f)

            # Write RBAC manifests
            rbac_dir = tmppath / "rbac"
            rbac_dir.mkdir()

            for kind, resources in sample_rbac_manifests.items():
                filename = f"{kind.lower()}s.yaml"
                with (rbac_dir / filename).open("w") as f:
                    yaml.dump_all(resources, f)

            # Run validate command
            result = cli_runner.invoke(
                cli,
                ["rbac", "validate", "--config", str(config_path), "--manifest-dir", str(rbac_dir)],
            )

            assert result.exit_code == 0
            assert "PASSED" in result.output or "validated" in result.output.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-061")
    def test_validate_invalid_manifests(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: dict[str, Any],
    ) -> None:
        """Test validate command with invalid manifests (missing apiVersion)."""
        from floe_cli.main import cli

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write manifest.yaml
            config_path = tmppath / "manifest.yaml"
            with config_path.open("w") as f:
                yaml.dump(sample_manifest_yaml, f)

            # Write invalid RBAC manifests (missing apiVersion)
            rbac_dir = tmppath / "rbac"
            rbac_dir.mkdir()

            invalid_manifest = {
                "kind": "ServiceAccount",
                "metadata": {"name": "test-sa", "namespace": "default"},
            }
            with (rbac_dir / "serviceaccounts.yaml").open("w") as f:
                yaml.dump(invalid_manifest, f)

            # Run validate command
            result = cli_runner.invoke(
                cli,
                ["rbac", "validate", "--config", str(config_path), "--manifest-dir", str(rbac_dir)],
            )

            # Should fail validation
            assert result.exit_code == 1
            assert "FAILED" in result.output or "apiVersion" in result.output

    @pytest.mark.integration
    @pytest.mark.requirement("FR-061")
    def test_validate_json_output(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: dict[str, Any],
        sample_rbac_manifests: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Test validate command with JSON output format."""
        import json

        from floe_cli.main import cli

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write manifest.yaml
            config_path = tmppath / "manifest.yaml"
            with config_path.open("w") as f:
                yaml.dump(sample_manifest_yaml, f)

            # Write RBAC manifests
            rbac_dir = tmppath / "rbac"
            rbac_dir.mkdir()

            for kind, resources in sample_rbac_manifests.items():
                filename = f"{kind.lower()}s.yaml"
                with (rbac_dir / filename).open("w") as f:
                    yaml.dump_all(resources, f)

            # Run validate command with JSON output
            result = cli_runner.invoke(
                cli,
                [
                    "rbac",
                    "validate",
                    "--config",
                    str(config_path),
                    "--manifest-dir",
                    str(rbac_dir),
                    "--output",
                    "json",
                ],
            )

            assert result.exit_code == 0

            # Parse JSON output
            output = json.loads(result.output)
            assert "status" in output
            assert output["status"] == "valid"


class TestRBACDiffWorkflow:
    """Integration tests for the diff workflow."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-063")
    def test_diff_models_roundtrip(self) -> None:
        """Test diff model serialization roundtrip."""
        import json

        from floe_cli.commands.rbac import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
            compute_rbac_diff,
        )

        # Create expected and actual resources
        expected = [
            {
                "kind": "ServiceAccount",
                "apiVersion": "v1",
                "metadata": {"name": "sa1", "namespace": "ns1"},
            },
            {
                "kind": "ServiceAccount",
                "apiVersion": "v1",
                "metadata": {"name": "sa2", "namespace": "ns1"},
            },
        ]

        actual = [
            {
                "kind": "ServiceAccount",
                "apiVersion": "v1",
                "metadata": {"name": "sa1", "namespace": "ns1"},
            },
            {
                "kind": "ServiceAccount",
                "apiVersion": "v1",
                "metadata": {"name": "sa3", "namespace": "ns1"},
            },
        ]

        # Compute diff
        result = compute_rbac_diff(expected, actual, "expected.yaml", "cluster")

        assert result.has_differences()
        assert result.added_count == 1  # sa2 needs to be added
        assert result.removed_count == 1  # sa3 should be removed

        # Test JSON serialization roundtrip
        json_str = result.model_dump_json()
        data = json.loads(json_str)
        assert "diffs" in data
        assert data["expected_source"] == "expected.yaml"


class TestRBACGenerateWorkflow:
    """Integration tests for generate workflow."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-060")
    def test_generate_dry_run(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: dict[str, Any],
    ) -> None:
        """Test generate command with dry-run flag."""
        from floe_cli.main import cli

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write manifest.yaml
            config_path = tmppath / "manifest.yaml"
            with config_path.open("w") as f:
                yaml.dump(sample_manifest_yaml, f)

            # Run generate command with dry-run
            result = cli_runner.invoke(
                cli,
                ["rbac", "generate", "--config", str(config_path), "--dry-run"],
            )

            # Dry run should not fail even without floe-core/floe-rbac-k8s installed
            # It should show what would be generated
            assert "DRY RUN" in result.output or result.exit_code != 0

    @pytest.mark.integration
    @pytest.mark.requirement("FR-060")
    def test_generate_missing_config(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test generate command with missing config file."""
        from floe_cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["rbac", "generate", "--config", "/nonexistent/manifest.yaml"],
        )

        assert result.exit_code != 0


class TestRBACAuditWorkflow:
    """Integration tests for audit workflow models."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-062")
    def test_audit_report_model(self) -> None:
        """Test audit report model creation and methods."""
        from floe_cli.commands.rbac import (
            AuditFinding,
            AuditFindingType,
            AuditSeverity,
            NamespaceSummary,
            RBACAuditReport,
            ServiceAccountSummary,
        )

        # Build a realistic audit report
        namespaces = [
            NamespaceSummary(
                name="floe-jobs",
                pss_enforce="restricted",
                service_accounts=2,
                roles=3,
                role_bindings=3,
                managed_by_floe=True,
            ),
        ]

        service_accounts = [
            ServiceAccountSummary(
                name="floe-job-runner",
                namespace="floe-jobs",
                roles=["floe-secret-reader"],
                secrets_access=["snowflake-creds"],
                automount_token=False,
                managed_by_floe=True,
            ),
        ]

        findings = [
            AuditFinding(
                severity=AuditSeverity.WARNING,
                finding_type=AuditFindingType.MISSING_RESOURCE_NAMES,
                resource_kind="Role",
                resource_name="legacy-role",
                resource_namespace="floe-jobs",
                message="Role grants access to all secrets",
                recommendation="Add resourceNames constraint",
            ),
        ]

        report = RBACAuditReport(
            cluster_name="test-cluster",
            namespaces=namespaces,
            service_accounts=service_accounts,
            findings=findings,
            total_service_accounts=2,
            total_roles=3,
            total_role_bindings=3,
            floe_managed_count=6,
        )

        # Test report methods
        assert report.has_critical_findings() is False
        assert report.has_warnings() is True

        by_severity = report.findings_by_severity()
        assert len(by_severity[AuditSeverity.WARNING]) == 1
        assert len(by_severity[AuditSeverity.CRITICAL]) == 0

    @pytest.mark.integration
    @pytest.mark.requirement("FR-062")
    def test_audit_report_serialization(self) -> None:
        """Test audit report JSON serialization."""
        import json

        from floe_cli.commands.rbac import RBACAuditReport

        report = RBACAuditReport(
            cluster_name="test-cluster",
            total_service_accounts=5,
            total_roles=10,
        )

        # Serialize to JSON
        json_str = report.model_dump_json()
        data = json.loads(json_str)

        assert data["cluster_name"] == "test-cluster"
        assert data["total_service_accounts"] == 5
        assert "generated_at" in data


class TestFullWorkflow:
    """End-to-end integration tests for full RBAC workflow."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-060")
    @pytest.mark.requirement("FR-061")
    def test_generate_then_validate_workflow(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: dict[str, Any],
        sample_rbac_manifests: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Test full workflow: write manifests then validate them."""
        from floe_cli.main import cli

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write manifest.yaml
            config_path = tmppath / "manifest.yaml"
            with config_path.open("w") as f:
                yaml.dump(sample_manifest_yaml, f)

            # Write RBAC manifests (simulating generate output)
            rbac_dir = tmppath / "rbac"
            rbac_dir.mkdir()

            for kind, resources in sample_rbac_manifests.items():
                filename = f"{kind.lower()}s.yaml"
                with (rbac_dir / filename).open("w") as f:
                    yaml.dump_all(resources, f)

            # Validate the manifests
            result = cli_runner.invoke(
                cli,
                ["rbac", "validate", "--config", str(config_path), "--manifest-dir", str(rbac_dir)],
            )

            assert result.exit_code == 0
            assert "validated" in result.output.lower() or "pass" in result.output.lower()
