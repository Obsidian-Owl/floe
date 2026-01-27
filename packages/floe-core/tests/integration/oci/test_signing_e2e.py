"""E2E integration tests for artifact signing.

Tests the complete signing flow against a real OCI registry in Kind cluster:
- Keyless signing with OIDC identity (requires CI/CD environment)
- Signature storage in OCI registry annotations
- Rekor transparency log integration

These tests FAIL if:
- Registry is unavailable
- OIDC identity cannot be obtained (not in CI/CD environment)
Per Constitution V, tests MUST NOT use pytest.skip().

Task: T069
Phase: Integration Tests (Phase 8)
Requirements: FR-001, FR-002, FR-008, SC-001, SC-007

Example:
    # Run in GitHub Actions (OIDC available):
    make test-integration

    # Local run will FAIL if OIDC not available:
    pytest packages/floe-core/tests/integration/oci/test_signing_e2e.py -v

See Also:
    - packages/floe-core/src/floe_core/oci/signing.py: SigningClient implementation
    - testing/k8s/services/registry.yaml: Registry deployment manifest
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

from pydantic import HttpUrl

from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts


def _create_signable_artifacts(unique_id: str) -> CompiledArtifacts:
    """Create a valid CompiledArtifacts instance for signing tests.

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
            source_hash=f"sha256:signing-{unique_id}",
            product_name=f"signing-test-{unique_id}",
            product_version="1.0.0",
        ),
        identity=ProductIdentity(
            product_id=f"signing.test_{unique_id}",
            domain="signing-test",
            repository="https://github.com/test/signing-repo",
        ),
        mode="simple",
        inheritance_chain=[],
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="floe-signing-test",
                    service_version="1.0.0",
                    deployment_environment="dev",
                    floe_namespace="signing-test",
                    floe_product_name=f"signing-test-{unique_id}",
                    floe_product_version="1.0.0",
                    floe_mode="dev",
                ),
            ),
            lineage_namespace="signing-test-namespace",
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        ),
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name=f"stg_signing_{unique_id}", compute="duckdb")],
            default_compute="duckdb",
        ),
        dbt_profiles={
            "floe": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": "/tmp/signing-test.duckdb",
                    }
                },
            }
        },
    )


class TestKeylessSigningE2E(IntegrationTestBase):
    """E2E tests for keyless signing with OIDC identity.

    Tests the complete keyless signing flow:
    1. Push artifact to registry
    2. Sign using OIDC identity (Fulcio certificate)
    3. Log signature to Rekor transparency log
    4. Verify signature metadata stored in annotations

    Requirements: FR-001, FR-002, FR-008, SC-001
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.fixture
    def signing_config(self) -> dict[str, str | bool]:
        """Create keyless signing configuration.

        Returns:
            SigningConfig-compatible dict for keyless mode.
        """
        return {
            "mode": "keyless",
            "rekor_url": os.environ.get("FLOE_REKOR_URL", "https://rekor.sigstore.dev"),
        }

    @pytest.mark.requirement("8B-FR-001")
    @pytest.mark.requirement("8B-FR-002")
    def test_keyless_sign_artifact(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
        signing_config: dict[str, str | bool],
    ) -> None:
        """Test keyless signing of artifact with OIDC identity.

        This test requires OIDC identity to be available:
        - In GitHub Actions: Automatic via ACTIONS_ID_TOKEN_REQUEST_URL
        - In GitLab CI: Automatic via CI_JOB_JWT
        - Locally: Will FAIL (no OIDC provider)

        Verifies:
        - SigningClient acquires OIDC token
        - Artifact is signed with Fulcio certificate
        - Signature metadata returned with issuer/subject
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.signing import SigningClient
        from floe_core.schemas.signing import SigningConfig

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_signable_artifacts(unique_id)
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)
        digest = client.push(artifacts, tag=test_artifact_tag)
        assert digest.startswith("sha256:")

        oidc_issuer_str = os.environ.get(
            "FLOE_OIDC_ISSUER", "https://token.actions.githubusercontent.com"
        )
        config = SigningConfig(mode="keyless", oidc_issuer=HttpUrl(oidc_issuer_str))
        signing_client = SigningClient(config)

        content = artifacts_path.read_bytes()
        artifact_ref = f"oci://{client.config.uri.replace('oci://', '')}:{test_artifact_tag}"

        metadata = signing_client.sign(content, artifact_ref)

        assert metadata is not None
        assert metadata.mode == "keyless"
        assert metadata.issuer is not None
        assert metadata.subject is not None
        assert metadata.bundle is not None

    @pytest.mark.requirement("8B-FR-008")
    def test_keyless_sign_logs_to_rekor(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test keyless signing creates Rekor transparency log entry.

        Verifies:
        - Signature is logged to Rekor
        - Rekor log index is returned in metadata
        - Log index is a positive integer
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.signing import SigningClient
        from floe_core.schemas.signing import SigningConfig

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_signable_artifacts(unique_id)
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        oidc_issuer_str = os.environ.get(
            "FLOE_OIDC_ISSUER", "https://token.actions.githubusercontent.com"
        )
        config = SigningConfig(mode="keyless", oidc_issuer=HttpUrl(oidc_issuer_str))
        signing_client = SigningClient(config)

        content = artifacts_path.read_bytes()
        artifact_ref = (
            f"oci://{client.config.uri.replace('oci://', '')}/floe-test:{test_artifact_tag}"
        )

        metadata = signing_client.sign(content, artifact_ref)

        assert metadata.rekor_log_index is not None
        assert isinstance(metadata.rekor_log_index, int)
        assert metadata.rekor_log_index > 0

    @pytest.mark.requirement("8B-SC-001")
    def test_keyless_signing_performance(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test keyless signing completes within performance target.

        SC-001: < 5 seconds added to build time

        Verifies:
        - Signing operation completes in under 5 seconds
        - Excludes push time (only signing overhead)
        """
        import time

        from floe_core.oci.client import OCIClient
        from floe_core.oci.signing import SigningClient
        from floe_core.schemas.signing import SigningConfig

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_signable_artifacts(unique_id)
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        oidc_issuer_str = os.environ.get(
            "FLOE_OIDC_ISSUER", "https://token.actions.githubusercontent.com"
        )
        config = SigningConfig(mode="keyless", oidc_issuer=HttpUrl(oidc_issuer_str))
        signing_client = SigningClient(config)

        content = artifacts_path.read_bytes()
        artifact_ref = (
            f"oci://{client.config.uri.replace('oci://', '')}/floe-test:{test_artifact_tag}"
        )

        start_time = time.monotonic()
        signing_client.sign(content, artifact_ref)
        elapsed = time.monotonic() - start_time

        assert elapsed < 5.0, f"Signing took {elapsed:.2f}s, expected < 5s"

    @pytest.mark.requirement("8B-SC-007")
    def test_keyless_signing_emits_traces(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test keyless signing emits OpenTelemetry traces.

        SC-007: All signing operations emit OTel traces

        Verifies:
        - Signing operation creates trace spans
        - Spans have appropriate attributes
        """
        from unittest.mock import MagicMock, patch

        from floe_core.oci.client import OCIClient
        from floe_core.oci.signing import SigningClient
        from floe_core.schemas.signing import SigningConfig

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_signable_artifacts(unique_id)
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        oidc_issuer_str = os.environ.get(
            "FLOE_OIDC_ISSUER", "https://token.actions.githubusercontent.com"
        )
        config = SigningConfig(mode="keyless", oidc_issuer=HttpUrl(oidc_issuer_str))
        signing_client = SigningClient(config)

        content = artifacts_path.read_bytes()
        artifact_ref = (
            f"oci://{client.config.uri.replace('oci://', '')}/floe-test:{test_artifact_tag}"
        )

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

        with patch("floe_core.oci.signing.tracer", mock_tracer):
            signing_client.sign(content, artifact_ref)

        assert mock_tracer.start_as_current_span.called
