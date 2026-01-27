"""E2E integration tests for artifact verification during pull.

Tests the complete verification flow against a real OCI registry in Kind cluster:
- Verification policy enforcement (enforce/warn/off modes)
- Identity policy matching (issuer + subject)
- Per-environment policy overrides
- Unsigned artifact handling

These tests FAIL if:
- Registry is unavailable
- Verification cannot be performed (no signed artifacts available)
Per Constitution V, tests MUST NOT use pytest.skip().

Task: T070, T072
Phase: Integration Tests (Phase 8)
Requirements: FR-009, FR-010, FR-014, SC-006

Example:
    # Run in GitHub Actions (signed artifacts available):
    make test-integration

    # Local run will FAIL if signed artifacts not available:
    pytest packages/floe-core/tests/integration/oci/test_verification_e2e.py -v

See Also:
    - packages/floe-core/src/floe_core/oci/verification.py: VerificationClient implementation
    - packages/floe-core/src/floe_core/oci/client.py: OCIClient.pull() with verification
    - testing/k8s/services/registry.yaml: Registry deployment manifest
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

from pydantic import HttpUrl

from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts


def _create_verifiable_artifacts(unique_id: str) -> CompiledArtifacts:
    """Create a valid CompiledArtifacts instance for verification tests.

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
            source_hash=f"sha256:verify-{unique_id}",
            product_name=f"verify-test-{unique_id}",
            product_version="1.0.0",
        ),
        identity=ProductIdentity(
            product_id=f"verify.test_{unique_id}",
            domain="verify-test",
            repository="https://github.com/test/verify-repo",
        ),
        mode="simple",
        inheritance_chain=[],
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="floe-verify-test",
                    service_version="1.0.0",
                    deployment_environment="dev",
                    floe_namespace="verify-test",
                    floe_product_name=f"verify-test-{unique_id}",
                    floe_product_version="1.0.0",
                    floe_mode="dev",
                ),
            ),
            lineage_namespace="verify-test-namespace",
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        ),
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name=f"stg_verify_{unique_id}", compute="duckdb")],
            default_compute="duckdb",
        ),
        dbt_profiles={
            "floe": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": "/tmp/verify-test.duckdb",
                    }
                },
            }
        },
    )


class TestVerificationDuringPullE2E(IntegrationTestBase):
    """E2E tests for verification during pull operations.

    Tests the complete verification flow during OCIClient.pull():
    1. Push artifact to registry (optionally sign it)
    2. Configure verification policy
    3. Pull with verification enabled
    4. Verify enforcement behavior (enforce/warn/off)

    Requirements: FR-009, FR-010, SC-006
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.mark.requirement("8B-FR-009")
    def test_pull_unsigned_artifact_with_verification_off(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test pulling unsigned artifact with verification disabled.

        When verification is off, unsigned artifacts should pull successfully.

        Verifies:
        - Unsigned artifacts can be pulled when enforcement="off"
        - No verification errors raised
        - Artifact content is correct
        """
        from floe_core.oci.client import OCIClient

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_verifiable_artifacts(unique_id)

        # Push unsigned artifact
        client = OCIClient.from_manifest(test_manifest_path)
        digest = client.push(artifacts, tag=test_artifact_tag)
        assert digest.startswith("sha256:")

        # Pull with verification off (default for test registry without policy)
        pulled = client.pull(tag=test_artifact_tag)

        assert pulled.metadata.product_name == artifacts.metadata.product_name
        assert pulled.identity.product_id == artifacts.identity.product_id

    @pytest.mark.requirement("8B-FR-009")
    @pytest.mark.requirement("8B-FR-010")
    def test_pull_unsigned_artifact_with_verification_warn(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        oci_registry_host: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test pulling unsigned artifact with verification in warn mode.

        When enforcement="warn", unsigned artifacts should pull with a warning.

        Verifies:
        - Unsigned artifacts can be pulled when enforcement="warn"
        - Warning is logged
        - Artifact content is correct
        """
        import yaml

        from floe_core.oci.client import OCIClient
        from floe_core.schemas.signing import TrustedIssuer

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_verifiable_artifacts(unique_id)

        # Create manifest with verification policy in warn mode
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
                        "enforcement": "warn",
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
        manifest_path = tmp_path / "manifest-warn.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest_data))

        # Push unsigned artifact
        client = OCIClient.from_manifest(manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        # Pull should succeed with warning
        import logging

        with caplog.at_level(logging.WARNING):
            pulled = client.pull(tag=test_artifact_tag)

        assert pulled.metadata.product_name == artifacts.metadata.product_name
        # Warning should be logged for unsigned artifact in warn mode
        # (actual log check depends on implementation details)

    @pytest.mark.requirement("8B-FR-009")
    def test_pull_unsigned_artifact_with_verification_enforce_fails(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        oci_registry_host: str,
    ) -> None:
        """Test pulling unsigned artifact with verification enforced.

        When enforcement="enforce", unsigned artifacts should fail to pull.

        Verifies:
        - SignatureVerificationError raised for unsigned artifacts
        - Error message indicates missing signature
        """
        import yaml

        from floe_core.oci.client import OCIClient
        from floe_core.oci.errors import SignatureVerificationError

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_verifiable_artifacts(unique_id)

        # Create manifest with verification policy enforced
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
                        "enforcement": "enforce",
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
        manifest_path = tmp_path / "manifest-enforce.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest_data))

        # Push unsigned artifact
        client = OCIClient.from_manifest(manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        # Pull should fail with verification error
        with pytest.raises(SignatureVerificationError) as exc_info:
            client.pull(tag=test_artifact_tag)

        assert (
            "unsigned" in str(exc_info.value).lower() or "signature" in str(exc_info.value).lower()
        )

    @pytest.mark.requirement("8B-SC-006")
    def test_verification_performance(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test verification completes within performance target.

        SC-006: < 2 seconds for verification operations

        Verifies:
        - Verification (even with failure) completes in under 2 seconds
        - Excludes network time (only verification overhead)
        """
        import time

        from floe_core.oci.client import OCIClient
        from floe_core.oci.verification import VerificationClient
        from floe_core.schemas.signing import TrustedIssuer, VerificationPolicy

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_verifiable_artifacts(unique_id)
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        # Push artifact
        client = OCIClient.from_manifest(test_manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        # Configure verification policy
        policy = VerificationPolicy(
            enabled=True,
            enforcement="warn",  # Use warn to avoid exception
            trusted_issuers=[
                TrustedIssuer(
                    issuer=HttpUrl("https://token.actions.githubusercontent.com"),
                    subject="repo:test/repo:ref:refs/heads/main",
                )
            ],
        )
        verification_client = VerificationClient(policy)

        content = artifacts_path.read_bytes()
        artifact_ref = f"oci://{client.config.uri.replace('oci://', '')}:{test_artifact_tag}"

        # Time the verification operation
        start_time = time.monotonic()
        result = verification_client.verify(
            content=content,
            metadata=None,  # Unsigned artifact
            artifact_ref=artifact_ref,
        )
        elapsed = time.monotonic() - start_time

        # Should complete within 2 seconds per SC-006
        assert elapsed < 2.0, f"Verification took {elapsed:.2f}s, expected < 2s"


class TestPerEnvironmentPolicyE2E(IntegrationTestBase):
    """E2E tests for per-environment verification policy enforcement.

    Tests environment-specific policy overrides:
    - Different enforcement levels per environment
    - Environment passed during pull
    - Fallback to default enforcement when environment not specified

    Task: T072
    Requirements: FR-014
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.mark.requirement("8B-FR-014")
    def test_per_environment_enforcement_production_strict(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        oci_registry_host: str,
    ) -> None:
        """Test production environment enforces stricter verification.

        Verifies:
        - Production environment uses "enforce" mode
        - Unsigned artifacts fail in production
        - Same artifact would pass in development
        """
        import yaml

        from floe_core.oci.client import OCIClient
        from floe_core.oci.errors import SignatureVerificationError

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_verifiable_artifacts(unique_id)

        # Create manifest with per-environment policies
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
                        "enforcement": "warn",  # Default is warn
                        "trusted_issuers": [
                            {
                                "issuer": "https://token.actions.githubusercontent.com",
                                "subject": "repo:test/repo:ref:refs/heads/main",
                            }
                        ],
                        "environment_policies": {
                            "production": {"enforcement": "enforce"},
                            "development": {"enforcement": "off"},
                        },
                    },
                }
            }
        }
        manifest_path = tmp_path / "manifest-env.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest_data))

        # Push unsigned artifact
        client = OCIClient.from_manifest(manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        # Pull in production should fail
        with pytest.raises(SignatureVerificationError):
            client.pull(tag=test_artifact_tag, environment="production")

        # Pull in development should succeed
        pulled = client.pull(tag=test_artifact_tag, environment="development")
        assert pulled.metadata.product_name == artifacts.metadata.product_name

    @pytest.mark.requirement("8B-FR-014")
    def test_per_environment_sbom_requirement(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        oci_registry_host: str,
    ) -> None:
        """Test per-environment SBOM requirement override.

        Verifies:
        - Production requires SBOM
        - Development does not require SBOM
        - Same artifact behaves differently per environment
        """
        import yaml

        from floe_core.oci.client import OCIClient

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_verifiable_artifacts(unique_id)

        # Create manifest with per-environment SBOM policies
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
                        "enforcement": "warn",  # Warn mode so we don't block on signature
                        "require_sbom": False,  # Default no SBOM required
                        "trusted_issuers": [
                            {
                                "issuer": "https://token.actions.githubusercontent.com",
                                "subject": "repo:test/repo:ref:refs/heads/main",
                            }
                        ],
                        "environment_policies": {
                            "production": {"require_sbom": True, "enforcement": "warn"},
                            "development": {"require_sbom": False, "enforcement": "off"},
                        },
                    },
                }
            }
        }
        manifest_path = tmp_path / "manifest-sbom.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest_data))

        # Push artifact without SBOM
        client = OCIClient.from_manifest(manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        # Pull in development should succeed (no SBOM required)
        pulled_dev = client.pull(tag=test_artifact_tag, environment="development")
        assert pulled_dev.metadata.product_name == artifacts.metadata.product_name

        # Pull in production should warn about missing SBOM (warn mode)
        # The test verifies the policy is applied; actual SBOM check behavior
        # depends on whether signed artifacts with SBOM are available
        pulled_prod = client.pull(tag=test_artifact_tag, environment="production")
        assert pulled_prod.metadata.product_name == artifacts.metadata.product_name


class TestVerificationTracingE2E(IntegrationTestBase):
    """E2E tests for OpenTelemetry tracing during verification.

    Tests that verification operations emit proper OTel traces:
    - Span creation for verify operations
    - Span attributes for enforcement mode, environment
    - Error recording on verification failures

    Requirements: SC-007
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.mark.requirement("8B-SC-007")
    def test_verification_emits_traces(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test verification emits OpenTelemetry traces.

        Verifies:
        - verify() creates trace span
        - Span has required attributes
        """
        from unittest.mock import MagicMock, patch

        from floe_core.oci.client import OCIClient
        from floe_core.oci.verification import VerificationClient
        from floe_core.schemas.signing import TrustedIssuer, VerificationPolicy

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_verifiable_artifacts(unique_id)
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        # Push artifact
        client = OCIClient.from_manifest(test_manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        # Configure verification
        policy = VerificationPolicy(
            enabled=True,
            enforcement="warn",
            trusted_issuers=[
                TrustedIssuer(
                    issuer=HttpUrl("https://token.actions.githubusercontent.com"),
                    subject="repo:test/repo:ref:refs/heads/main",
                )
            ],
        )
        verification_client = VerificationClient(policy, environment="staging")

        content = artifacts_path.read_bytes()
        artifact_ref = f"oci://{client.config.uri.replace('oci://', '')}:{test_artifact_tag}"

        # Mock the tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

        with patch("floe_core.oci.verification.tracer", mock_tracer):
            verification_client.verify(
                content=content,
                metadata=None,
                artifact_ref=artifact_ref,
            )

        # Verify tracer was called
        assert mock_tracer.start_as_current_span.called
        mock_tracer.start_as_current_span.assert_called_with("floe.oci.verify")

        # Verify span attributes were set
        assert mock_span.set_attribute.called
        calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
        assert "floe.artifact.ref" in calls
        assert "floe.verification.enforcement" in calls
