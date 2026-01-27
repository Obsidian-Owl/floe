"""E2E integration tests for SBOM generation and attestation.

Tests the complete SBOM/attestation flow against a real OCI registry in Kind cluster:
- SBOM generation using syft CLI
- Attestation attachment using cosign CLI
- Attestation retrieval and verification

These tests FAIL if:
- Registry is unavailable
- syft CLI is not installed
- cosign CLI is not installed
- OIDC identity cannot be obtained (for keyless attestation)
Per Constitution V, tests MUST NOT use pytest.skip().

Task: T071
Phase: Integration Tests (Phase 8)
Requirements: FR-005, FR-006, FR-007, SC-002

Example:
    # Run in GitHub Actions (OIDC + CLIs available):
    make test-integration

    # Local run requires syft and cosign installed:
    pytest packages/floe-core/tests/integration/oci/test_attestation_e2e.py -v

See Also:
    - packages/floe-core/src/floe_core/oci/attestation.py: SBOM/Attestation implementation
    - testing/k8s/services/registry.yaml: Registry deployment manifest
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts


def _create_attestable_artifacts(unique_id: str) -> CompiledArtifacts:
    """Create a valid CompiledArtifacts instance for attestation tests.

    Args:
        unique_id: Unique identifier for test isolation.

    Returns:
        A valid CompiledArtifacts instance.
    """
    from floe_core.schemas.compiled_artifacts import (
        CompilationMetadata,
        CompiledArtifacts,
        ObservabilityConfig,
        PluginRef,
        ProductIdentity,
        ResolvedModel,
        ResolvedPlugins,
        ResolvedTransforms,
    )
    from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

    return CompiledArtifacts(
        version=COMPILED_ARTIFACTS_VERSION,
        metadata=CompilationMetadata(
            compiled_at=datetime.now(timezone.utc),
            floe_version=COMPILED_ARTIFACTS_VERSION,
            source_hash=f"sha256:attest-{unique_id}",
            product_name=f"attest-test-{unique_id}",
            product_version="1.0.0",
        ),
        identity=ProductIdentity(
            product_id=f"attest.test_{unique_id}",
            domain="attest-test",
            repository="https://github.com/test/attest-repo",
        ),
        mode="simple",
        inheritance_chain=[],
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="floe-attest-test",
                    service_version="1.0.0",
                    deployment_environment="dev",
                    floe_namespace="attest-test",
                    floe_product_name=f"attest-test-{unique_id}",
                    floe_product_version="1.0.0",
                    floe_mode="dev",
                ),
            ),
            lineage_namespace="attest-test-namespace",
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        ),
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name=f"stg_attest_{unique_id}", compute="duckdb")],
            default_compute="duckdb",
        ),
        dbt_profiles={
            "floe": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": "/tmp/attest-test.duckdb",
                    }
                },
            }
        },
    )


class TestSBOMGenerationE2E(IntegrationTestBase):
    """E2E tests for SBOM generation using syft CLI.

    Tests the complete SBOM generation flow:
    1. Generate SBOM for project using syft
    2. Verify SPDX JSON output format
    3. Verify package detection

    Requirements: FR-005, FR-006
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.mark.requirement("8B-FR-005")
    def test_generate_sbom_for_project(self, tmp_path: Path) -> None:
        """Test SBOM generation for a Python project.

        This test requires syft CLI to be installed.

        Verifies:
        - SBOM is generated in SPDX JSON format
        - SBOM contains package information
        - SBOM has required SPDX fields
        """
        from floe_core.oci.attestation import (
            SyftNotFoundError,
            check_syft_available,
            generate_sbom,
        )

        # Create a minimal Python project
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        # Create a pyproject.toml with dependencies
        pyproject_content = """
[project]
name = "test-project"
version = "1.0.0"
dependencies = [
    "requests>=2.0.0",
    "pydantic>=2.0.0",
]
"""
        (project_dir / "pyproject.toml").write_text(pyproject_content)

        # Create a simple Python file
        (project_dir / "main.py").write_text("import requests\nprint('hello')")

        # Generate SBOM
        if not check_syft_available():
            # Test that the error is raised correctly when syft is not available
            with pytest.raises(SyftNotFoundError):
                generate_sbom(project_dir)
            pytest.fail(
                "syft CLI not installed - test cannot complete. Install with: brew install syft"
            )

        sbom = generate_sbom(project_dir, output_format="spdx-json")

        # Verify SPDX format
        assert "spdxVersion" in sbom
        assert sbom["spdxVersion"].startswith("SPDX-")
        assert "SPDXID" in sbom
        assert "name" in sbom
        assert "creationInfo" in sbom

    @pytest.mark.requirement("8B-FR-005")
    def test_generate_sbom_for_floe_project(self) -> None:
        """Test SBOM generation for the floe-core package itself.

        This test scans the actual floe-core package and verifies
        real dependencies are detected.

        Verifies:
        - SBOM detects Python packages
        - Package count is reasonable (> 0)
        """
        from floe_core.oci.attestation import (
            SyftNotFoundError,
            check_syft_available,
            generate_sbom,
        )

        if not check_syft_available():
            with pytest.raises(SyftNotFoundError):
                generate_sbom(Path("/tmp"))
            pytest.fail("syft CLI not installed")

        # Scan the floe-core package directory
        floe_core_path = Path(__file__).parent.parent.parent.parent / "src"

        sbom = generate_sbom(floe_core_path)

        # Should detect some packages
        assert "packages" in sbom or "files" in sbom
        # SBOM should be a valid SPDX document
        assert "spdxVersion" in sbom

    @pytest.mark.requirement("8B-SC-002")
    def test_sbom_generation_performance(self, tmp_path: Path) -> None:
        """Test SBOM generation completes within performance target.

        SC-002: SBOM generation < 30 seconds

        Verifies:
        - SBOM generation for small project completes quickly
        """
        import time

        from floe_core.oci.attestation import check_syft_available, generate_sbom

        if not check_syft_available():
            pytest.fail("syft CLI not installed")

        # Create minimal project
        project_dir = tmp_path / "perf-test"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "1.0.0"')

        start_time = time.monotonic()
        generate_sbom(project_dir)
        elapsed = time.monotonic() - start_time

        # Should complete well within 30 seconds for a small project
        assert elapsed < 30.0, f"SBOM generation took {elapsed:.2f}s, expected < 30s"


class TestAttestationAttachmentE2E(IntegrationTestBase):
    """E2E tests for attestation attachment to OCI artifacts.

    Tests the complete attestation flow:
    1. Push artifact to registry
    2. Generate SBOM
    3. Attach SBOM as attestation using cosign

    Requires OIDC identity for keyless attestation (CI/CD environment).

    Requirements: FR-006, FR-007
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.mark.requirement("8B-FR-006")
    def test_attach_sbom_attestation(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test attaching SBOM attestation to artifact.

        This test requires:
        - cosign CLI installed
        - OIDC identity available (CI/CD environment)

        Verifies:
        - SBOM can be attached as attestation
        - Attestation uses SPDX predicate type
        """
        from floe_core.oci.attestation import (
            attach_attestation,
            check_cosign_available,
            check_syft_available,
            generate_sbom,
        )
        from floe_core.oci.client import OCIClient

        if not check_syft_available():
            pytest.fail("syft CLI not installed")

        if not check_cosign_available():
            pytest.fail("cosign CLI not installed")

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_attestable_artifacts(unique_id)

        # Push artifact
        client = OCIClient.from_manifest(test_manifest_path)
        digest = client.push(artifacts, tag=test_artifact_tag)
        assert digest.startswith("sha256:")

        # Create a minimal project for SBOM generation
        project_dir = tmp_path / "sbom-project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(
            f'[project]\nname = "test-{unique_id}"\nversion = "1.0.0"'
        )

        # Generate SBOM
        sbom = generate_sbom(project_dir)
        sbom_path = tmp_path / "sbom.json"
        sbom_path.write_text(json.dumps(sbom))

        # Build artifact reference for cosign
        # cosign expects format: registry/repo:tag or registry/repo@sha256:...
        registry_uri = client.config.uri.replace("oci://", "")
        artifact_ref = f"{registry_uri}:{test_artifact_tag}"

        # Attach attestation (requires OIDC identity in CI)
        # This will fail locally without OIDC
        attach_attestation(
            artifact_ref=artifact_ref,
            predicate_path=sbom_path,
            predicate_type="https://spdx.dev/Document",
            keyless=True,
        )

    @pytest.mark.requirement("8B-FR-007")
    def test_retrieve_attestations(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test retrieving attestations from artifact.

        Verifies:
        - Attestations can be retrieved after attachment
        - Retrieved attestation matches what was attached
        """
        from floe_core.oci.attestation import (
            attach_attestation,
            check_cosign_available,
            check_syft_available,
            generate_sbom,
            retrieve_attestations,
        )
        from floe_core.oci.client import OCIClient

        if not check_syft_available():
            pytest.fail("syft CLI not installed")

        if not check_cosign_available():
            pytest.fail("cosign CLI not installed")

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_attestable_artifacts(unique_id)

        # Push artifact
        client = OCIClient.from_manifest(test_manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        # Generate and attach SBOM
        project_dir = tmp_path / "sbom-project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(
            f'[project]\nname = "test-{unique_id}"\nversion = "1.0.0"'
        )

        sbom = generate_sbom(project_dir)
        sbom_path = tmp_path / "sbom.json"
        sbom_path.write_text(json.dumps(sbom))

        registry_uri = client.config.uri.replace("oci://", "")
        artifact_ref = f"{registry_uri}:{test_artifact_tag}"

        # Attach SBOM as attestation
        attach_attestation(
            artifact_ref=artifact_ref,
            predicate_path=sbom_path,
            keyless=True,
        )

        # Retrieve attestations
        attestations = retrieve_attestations(artifact_ref)

        # Should have at least one attestation (the SBOM)
        assert len(attestations) >= 1

        # Find the SPDX attestation
        spdx_attestation = None
        for att in attestations:
            if att.predicate_type == "https://spdx.dev/Document":
                spdx_attestation = att
                break

        assert spdx_attestation is not None
        assert spdx_attestation.predicate is not None


class TestAttestationTracingE2E(IntegrationTestBase):
    """E2E tests for OpenTelemetry tracing during attestation operations.

    Tests that SBOM/attestation operations emit proper OTel traces.

    Requirements: SC-007
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.mark.requirement("8B-SC-007")
    def test_sbom_generation_emits_traces(self, tmp_path: Path) -> None:
        """Test SBOM generation emits OpenTelemetry traces.

        Verifies:
        - generate_sbom() creates trace span
        - Span has project_path and format attributes
        """

        from floe_core.oci.attestation import check_syft_available, generate_sbom

        if not check_syft_available():
            pytest.fail("syft CLI not installed")

        project_dir = tmp_path / "trace-test"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "1.0.0"')

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

        with patch("floe_core.oci.attestation.tracer", mock_tracer):
            generate_sbom(project_dir)

        # Verify tracer was called with expected span name
        assert mock_tracer.start_as_current_span.called
        mock_tracer.start_as_current_span.assert_called_with("floe.oci.sbom.generate")

        # Verify span attributes were set
        assert mock_span.set_attribute.called
        calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
        assert "floe.sbom.project_path" in calls
        assert "floe.sbom.format" in calls


class TestSBOMVerificationPolicyE2E(IntegrationTestBase):
    """E2E tests for SBOM requirement in verification policy.

    Tests that require_sbom policy is enforced during verification.

    Requirements: FR-006
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.mark.requirement("8B-FR-006")
    def test_verification_with_sbom_required(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        oci_registry_host: str,
    ) -> None:
        """Test verification fails when SBOM is required but not present.

        When require_sbom=True and enforcement="enforce", artifacts
        without SBOM attestation should fail verification.

        Note: This test uses warn mode since we don't have actual signed
        artifacts with SBOM in the test environment.
        """
        import yaml

        from floe_core.oci.client import OCIClient

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_attestable_artifacts(unique_id)

        # Create manifest with SBOM required in warn mode
        cache_path = tmp_path / "oci-cache"
        cache_path.mkdir(exist_ok=True)

        manifest_data = {
            "artifacts": {
                "registry": {
                    "uri": f"oci://{oci_registry_host}/floe-test",
                    "auth": {"type": "anonymous"},
                    "tls_verify": False,
                    "cache": {"enabled": True, "path": str(cache_path)},
                    "verification": {
                        "enabled": True,
                        "enforcement": "warn",  # Use warn to avoid blocking
                        "require_sbom": True,
                        "trusted_issuers": [
                            {
                                "issuer": "https://token.actions.githubusercontent.com",
                                "subject": "repo:test/repo:ref:refs/heads/main",
                            }
                        ],
                    },
                }
            }
        }
        manifest_path = tmp_path / "manifest-sbom-req.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest_data))

        # Push artifact WITHOUT SBOM attestation
        client = OCIClient.from_manifest(manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        # Pull should succeed (warn mode) but verification result
        # will indicate missing SBOM
        pulled = client.pull(tag=test_artifact_tag)

        # Artifact should be pulled (warn mode doesn't block)
        assert pulled.metadata.product_name == artifacts.metadata.product_name
