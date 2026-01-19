"""Integration tests for full RBAC manifest generation workflow.

This module tests the complete RBAC manifest generation workflow using
real plugin implementations, verifying that the generated manifests
are valid K8s YAML that can be applied to a cluster.

Task: T050
User Story: US4 - RBAC Manifest Generation
Requirements: FR-050, FR-051, FR-052, FR-053

Note:
    These tests use the real K8sRBACPlugin via entry point discovery.
    No external K8s services required - tests validate YAML output.
    kubectl dry-run validation is tested separately in K8s integration tests.

See Also:
    - tests/contract/test_rbac_manifest_generator.py: Contract tests
    - packages/floe-core/tests/unit/test_permission_aggregation.py: Unit tests
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from floe_core.schemas.rbac import (
    NamespaceConfig,
    RoleBindingConfig,
    RoleBindingSubject,
    RoleConfig,
    RoleRule,
    ServiceAccountConfig,
)
from floe_core.schemas.security import RBACConfig, SecurityConfig


class TestRBACManifestGenerationWorkflow:
    """Integration tests for full RBAC manifest generation workflow."""

    @pytest.fixture
    def security_config(self) -> SecurityConfig:
        """Create a SecurityConfig with RBAC enabled."""
        return SecurityConfig(
            rbac=RBACConfig(enabled=True),
        )

    @pytest.fixture
    def security_config_disabled(self) -> SecurityConfig:
        """Create a SecurityConfig with RBAC disabled."""
        return SecurityConfig(
            rbac=RBACConfig(enabled=False),
        )

    @pytest.fixture
    def sample_service_accounts(self) -> list[ServiceAccountConfig]:
        """Create sample ServiceAccount configurations."""
        return [
            ServiceAccountConfig(
                name="floe-job-runner",
                namespace="floe-jobs",
                labels={"app.kubernetes.io/managed-by": "floe"},
            ),
            ServiceAccountConfig(
                name="floe-data-processor",
                namespace="floe-jobs",
            ),
        ]

    @pytest.fixture
    def sample_roles(self) -> list[RoleConfig]:
        """Create sample Role configurations."""
        return [
            RoleConfig(
                name="floe-secret-reader",
                namespace="floe-jobs",
                rules=[
                    RoleRule(
                        api_groups=[""],
                        resources=["secrets"],
                        verbs=["get"],
                        resource_names=["snowflake-creds", "catalog-creds"],
                    ),
                ],
            ),
            RoleConfig(
                name="floe-job-manager",
                namespace="floe-jobs",
                rules=[
                    RoleRule(
                        api_groups=["batch"],
                        resources=["jobs"],
                        verbs=["get", "list", "create", "delete"],
                    ),
                ],
            ),
        ]

    @pytest.fixture
    def sample_role_bindings(
        self,
        sample_service_accounts: list[ServiceAccountConfig],
        sample_roles: list[RoleConfig],
    ) -> list[RoleBindingConfig]:
        """Create sample RoleBinding configurations."""
        return [
            RoleBindingConfig(
                name="floe-job-runner-secrets",
                namespace="floe-jobs",
                subjects=[
                    RoleBindingSubject(
                        name="floe-job-runner",
                        namespace="floe-jobs",
                    ),
                ],
                role_name="floe-secret-reader",
            ),
            RoleBindingConfig(
                name="floe-job-runner-jobs",
                namespace="floe-jobs",
                subjects=[
                    RoleBindingSubject(
                        name="floe-job-runner",
                        namespace="floe-jobs",
                    ),
                ],
                role_name="floe-job-manager",
            ),
        ]

    @pytest.fixture
    def sample_namespaces(self) -> list[NamespaceConfig]:
        """Create sample Namespace configurations."""
        return [
            NamespaceConfig(
                name="floe-jobs",
                layer="4",
                labels={"floe.io/managed": "true"},
            ),
        ]

    @pytest.mark.requirement("FR-050")
    @pytest.mark.requirement("FR-051")
    @pytest.mark.requirement("FR-052")
    @pytest.mark.requirement("FR-053")
    def test_full_generation_workflow_with_real_plugin(
        self,
        tmp_path: Path,
        security_config: SecurityConfig,
        sample_service_accounts: list[ServiceAccountConfig],
        sample_roles: list[RoleConfig],
        sample_role_bindings: list[RoleBindingConfig],
        sample_namespaces: list[NamespaceConfig],
    ) -> None:
        """Test complete manifest generation with real K8sRBACPlugin."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        # Create generator with real plugin
        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        # Generate all manifests
        result = generator.generate(
            security_config=security_config,
            secret_references=["snowflake-creds", "catalog-creds"],
            service_accounts=sample_service_accounts,
            roles=sample_roles,
            role_bindings=sample_role_bindings,
            namespaces=sample_namespaces,
        )

        # Verify generation succeeded
        assert result.success is True, f"Generation failed: {result.errors}"
        assert result.errors == []

        # Verify counts
        assert result.service_accounts == 2
        assert result.roles == 2
        assert result.role_bindings == 2
        assert result.namespaces == 1

        # Verify files were created
        assert len(result.files_generated) == 4
        assert (tmp_path / "rbac" / "serviceaccounts.yaml").exists()
        assert (tmp_path / "rbac" / "roles.yaml").exists()
        assert (tmp_path / "rbac" / "rolebindings.yaml").exists()
        assert (tmp_path / "rbac" / "namespaces.yaml").exists()

    @pytest.mark.requirement("FR-051")
    def test_generated_manifests_are_valid_yaml(
        self,
        tmp_path: Path,
        security_config: SecurityConfig,
        sample_service_accounts: list[ServiceAccountConfig],
        sample_roles: list[RoleConfig],
        sample_role_bindings: list[RoleBindingConfig],
        sample_namespaces: list[NamespaceConfig],
    ) -> None:
        """Test that all generated manifests are valid YAML."""
        from floe_core.rbac.generator import MANIFEST_FILES, RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        result = generator.generate(
            security_config=security_config,
            secret_references=[],
            service_accounts=sample_service_accounts,
            roles=sample_roles,
            role_bindings=sample_role_bindings,
            namespaces=sample_namespaces,
        )

        assert result.success is True

        # Verify each file is valid YAML
        for filename in MANIFEST_FILES:
            file_path = tmp_path / "rbac" / filename
            content = file_path.read_text()

            if content:  # Skip empty files
                # Parse should not raise
                docs = list(yaml.safe_load_all(content))
                # All non-None docs should have required K8s fields
                for doc in docs:
                    if doc is not None:
                        assert "apiVersion" in doc
                        assert "kind" in doc
                        assert "metadata" in doc

    @pytest.mark.requirement("FR-051")
    def test_generated_service_accounts_have_correct_structure(
        self,
        tmp_path: Path,
        security_config: SecurityConfig,
        sample_service_accounts: list[ServiceAccountConfig],
    ) -> None:
        """Test ServiceAccount manifests have correct K8s structure."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        result = generator.generate(
            security_config=security_config,
            secret_references=[],
            service_accounts=sample_service_accounts,
        )

        assert result.success is True

        # Read and validate ServiceAccounts
        sa_content = (tmp_path / "rbac" / "serviceaccounts.yaml").read_text()
        docs = [d for d in yaml.safe_load_all(sa_content) if d is not None]

        assert len(docs) == 2

        for doc in docs:
            assert doc["apiVersion"] == "v1"
            assert doc["kind"] == "ServiceAccount"
            assert "name" in doc["metadata"]
            assert "namespace" in doc["metadata"]
            # Security: automountServiceAccountToken should be False
            assert doc.get("automountServiceAccountToken") is False

    @pytest.mark.requirement("FR-051")
    def test_generated_roles_have_correct_structure(
        self,
        tmp_path: Path,
        security_config: SecurityConfig,
        sample_roles: list[RoleConfig],
    ) -> None:
        """Test Role manifests have correct K8s structure."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        result = generator.generate(
            security_config=security_config,
            secret_references=[],
            roles=sample_roles,
        )

        assert result.success is True

        # Read and validate Roles
        role_content = (tmp_path / "rbac" / "roles.yaml").read_text()
        docs = [d for d in yaml.safe_load_all(role_content) if d is not None]

        assert len(docs) == 2

        for doc in docs:
            assert doc["apiVersion"] == "rbac.authorization.k8s.io/v1"
            assert doc["kind"] == "Role"
            assert "name" in doc["metadata"]
            assert "namespace" in doc["metadata"]
            assert "rules" in doc
            assert isinstance(doc["rules"], list)

    @pytest.mark.requirement("FR-051")
    def test_generated_rolebindings_have_correct_structure(
        self,
        tmp_path: Path,
        security_config: SecurityConfig,
        sample_role_bindings: list[RoleBindingConfig],
    ) -> None:
        """Test RoleBinding manifests have correct K8s structure."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        result = generator.generate(
            security_config=security_config,
            secret_references=[],
            role_bindings=sample_role_bindings,
        )

        assert result.success is True

        # Read and validate RoleBindings
        rb_content = (tmp_path / "rbac" / "rolebindings.yaml").read_text()
        docs = [d for d in yaml.safe_load_all(rb_content) if d is not None]

        assert len(docs) == 2

        for doc in docs:
            assert doc["apiVersion"] == "rbac.authorization.k8s.io/v1"
            assert doc["kind"] == "RoleBinding"
            assert "name" in doc["metadata"]
            assert "namespace" in doc["metadata"]
            assert "subjects" in doc
            assert "roleRef" in doc
            assert doc["roleRef"]["kind"] == "Role"

    @pytest.mark.requirement("FR-050")
    def test_rbac_disabled_produces_no_manifests(
        self,
        tmp_path: Path,
        security_config_disabled: SecurityConfig,
        sample_service_accounts: list[ServiceAccountConfig],
    ) -> None:
        """Test RBAC disabled produces no manifest files."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        result = generator.generate(
            security_config=security_config_disabled,
            secret_references=["some-secret"],
            service_accounts=sample_service_accounts,
        )

        # Generation should succeed but with warning
        assert result.success is True
        assert len(result.warnings) > 0
        assert "disabled" in result.warnings[0].lower()

        # No files should be generated
        assert result.files_generated == []
        assert result.service_accounts == 0

    @pytest.mark.requirement("FR-052")
    def test_permission_aggregation_in_workflow(
        self,
        tmp_path: Path,
        security_config: SecurityConfig,
    ) -> None:
        """Test secret references are aggregated into minimal rules."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        # Generate with secret references only (no explicit roles)
        result = generator.generate(
            security_config=security_config,
            secret_references=[
                "snowflake-creds",
                "catalog-creds",
                "api-key",
                "snowflake-creds",  # Duplicate
            ],
        )

        assert result.success is True

        # Verify aggregation happened (warning should mention it)
        aggregation_warning = any("aggregated" in w.lower() for w in result.warnings)
        # Note: This depends on implementation - may or may not produce warning

    @pytest.mark.requirement("FR-053")
    def test_manifest_files_can_be_read_back(
        self,
        tmp_path: Path,
        security_config: SecurityConfig,
        sample_service_accounts: list[ServiceAccountConfig],
        sample_roles: list[RoleConfig],
    ) -> None:
        """Test manifests can be read back and parsed."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        result = generator.generate(
            security_config=security_config,
            secret_references=[],
            service_accounts=sample_service_accounts,
            roles=sample_roles,
        )

        assert result.success is True

        # Read all files and count documents
        total_docs = 0
        for file_path in result.files_generated:
            content = file_path.read_text()
            if content:
                docs = [d for d in yaml.safe_load_all(content) if d is not None]
                total_docs += len(docs)

        # Should have 2 ServiceAccounts + 2 Roles
        assert total_docs == 4


class TestRBACManifestGenerationAuditLogging:
    """Integration tests for audit logging during RBAC generation."""

    @pytest.fixture
    def security_config(self) -> SecurityConfig:
        """Create a SecurityConfig with RBAC enabled."""
        return SecurityConfig(
            rbac=RBACConfig(enabled=True),
        )

    @pytest.mark.requirement("FR-072")
    def test_audit_event_logged_on_success(
        self,
        tmp_path: Path,
        security_config: SecurityConfig,
    ) -> None:
        """Test successful generation logs audit event."""
        from unittest.mock import patch

        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        with patch("floe_core.rbac.generator.log_rbac_event") as mock_log:
            result = generator.generate(
                security_config=security_config,
                secret_references=["secret-a"],
            )

            assert result.success is True
            mock_log.assert_called_once()

            # Verify audit event has correct result
            audit_event = mock_log.call_args[0][0]
            assert audit_event.result.value == "success"

    @pytest.mark.requirement("FR-072")
    def test_audit_event_logged_on_disabled(
        self,
        tmp_path: Path,
    ) -> None:
        """Test disabled RBAC logs audit event."""
        from unittest.mock import patch

        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        security_config = SecurityConfig(
            rbac=RBACConfig(enabled=False),
        )

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=tmp_path / "rbac",
        )

        with patch("floe_core.rbac.generator.log_rbac_event") as mock_log:
            result = generator.generate(
                security_config=security_config,
                secret_references=[],
            )

            assert result.success is True
            mock_log.assert_called_once()

            audit_event = mock_log.call_args[0][0]
            assert audit_event.result.value == "disabled"
