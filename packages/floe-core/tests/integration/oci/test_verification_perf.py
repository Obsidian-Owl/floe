"""Performance benchmark tests for artifact verification.

Tests verification performance against the SC-006 target:
- Verification operations should complete in < 2 seconds

These tests run against real OCI registry in Kind cluster to measure
actual performance including network overhead.

Task: T073
Phase: Integration Tests (Phase 8)
Requirements: SC-006

Example:
    # Run performance tests:
    pytest packages/floe-core/tests/integration/oci/test_verification_perf.py -v

    # Run with benchmark plugin for detailed stats:
    pytest packages/floe-core/tests/integration/oci/test_verification_perf.py --benchmark-enable

See Also:
    - packages/floe-core/src/floe_core/oci/verification.py: VerificationClient
    - specs/8b-artifact-signing/spec.md: SC-006 requirement
"""

from __future__ import annotations

import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import HttpUrl
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts


def _create_benchmark_artifacts(unique_id: str) -> CompiledArtifacts:
    """Create a valid CompiledArtifacts instance for benchmark tests.

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
            source_hash=f"sha256:bench-{unique_id}",
            product_name=f"bench-test-{unique_id}",
            product_version="1.0.0",
        ),
        identity=ProductIdentity(
            product_id=f"bench.test_{unique_id}",
            domain="bench-test",
            repository="https://github.com/test/bench-repo",
        ),
        mode="simple",
        inheritance_chain=[],
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="floe-bench-test",
                    service_version="1.0.0",
                    deployment_environment="dev",
                    floe_namespace="bench-test",
                    floe_product_name=f"bench-test-{unique_id}",
                    floe_product_version="1.0.0",
                    floe_mode="dev",
                ),
            ),
            lineage_namespace="bench-test-namespace",
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        ),
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name=f"stg_bench_{unique_id}", compute="duckdb")],
            default_compute="duckdb",
        ),
        dbt_profiles={
            "floe": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": "/tmp/bench-test.duckdb",
                    }
                },
            }
        },
    )


class TestVerificationPerformance(IntegrationTestBase):
    """Performance benchmark tests for verification operations.

    Tests that verification meets the SC-006 performance target:
    < 2 seconds for verification operations.

    Requirements: SC-006
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.mark.requirement("8B-SC-006")
    def test_verification_latency_under_2_seconds(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test single verification operation completes under 2 seconds.

        SC-006 Target: < 2 seconds for verification

        Verifies:
        - VerificationClient.verify() completes within target
        - Time excludes artifact push (only verification)
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.verification import VerificationClient
        from floe_core.schemas.signing import TrustedIssuer, VerificationPolicy

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_benchmark_artifacts(unique_id)
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        # Push artifact (not timed)
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
        verification_client = VerificationClient(policy)

        content = artifacts_path.read_bytes()
        artifact_ref = (
            f"oci://{client.config.uri.replace('oci://', '')}:{test_artifact_tag}"
        )

        # Time the verification
        start_time = time.monotonic()
        verification_client.verify(
            content=content,
            metadata=None,  # Unsigned
            artifact_ref=artifact_ref,
        )
        elapsed = time.monotonic() - start_time

        assert elapsed < 2.0, f"Verification took {elapsed:.3f}s, target is < 2.0s"

    @pytest.mark.requirement("8B-SC-006")
    def test_verification_average_latency_multiple_runs(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test average verification latency across multiple runs.

        Runs verification multiple times and checks that average
        latency is well within the 2 second target.

        Verifies:
        - Average verification time < 2 seconds
        - P95 verification time < 2 seconds
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.verification import VerificationClient
        from floe_core.schemas.signing import TrustedIssuer, VerificationPolicy

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_benchmark_artifacts(unique_id)
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        # Push artifact
        client = OCIClient.from_manifest(test_manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

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
        verification_client = VerificationClient(policy)

        content = artifacts_path.read_bytes()
        artifact_ref = (
            f"oci://{client.config.uri.replace('oci://', '')}:{test_artifact_tag}"
        )

        # Run multiple iterations
        latencies: list[float] = []
        num_iterations = 5

        for _ in range(num_iterations):
            start_time = time.monotonic()
            verification_client.verify(
                content=content,
                metadata=None,
                artifact_ref=artifact_ref,
            )
            elapsed = time.monotonic() - start_time
            latencies.append(elapsed)

        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        max_latency = max(latencies)

        # Assert performance targets
        assert (
            avg_latency < 2.0
        ), f"Average verification latency {avg_latency:.3f}s > 2.0s target"
        assert (
            p95_latency < 2.0
        ), f"P95 verification latency {p95_latency:.3f}s > 2.0s target"

        # Log performance stats for visibility
        print("\nVerification Performance Stats:")
        print(f"  Iterations: {num_iterations}")
        print(f"  Average: {avg_latency:.3f}s")
        print(f"  P95: {p95_latency:.3f}s")
        print(f"  Max: {max_latency:.3f}s")

    @pytest.mark.requirement("8B-SC-006")
    def test_verification_with_policy_matching_overhead(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test verification with complex policy matching stays within target.

        Tests that even with multiple trusted issuers to match against,
        verification completes within the 2 second target.

        Verifies:
        - Policy matching with 10 trusted issuers < 2 seconds
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.verification import VerificationClient
        from floe_core.schemas.signing import TrustedIssuer, VerificationPolicy

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts = _create_benchmark_artifacts(unique_id)
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

        # Create policy with many trusted issuers
        trusted_issuers = [
            TrustedIssuer(
                issuer=HttpUrl(f"https://issuer-{i}.example.com"),
                subject=f"repo:org/repo-{i}:ref:refs/heads/main",
            )
            for i in range(10)
        ]

        policy = VerificationPolicy(
            enabled=True,
            enforcement="warn",
            trusted_issuers=trusted_issuers,
        )
        verification_client = VerificationClient(policy)

        content = artifacts_path.read_bytes()
        artifact_ref = (
            f"oci://{client.config.uri.replace('oci://', '')}:{test_artifact_tag}"
        )

        start_time = time.monotonic()
        verification_client.verify(
            content=content,
            metadata=None,
            artifact_ref=artifact_ref,
        )
        elapsed = time.monotonic() - start_time

        assert elapsed < 2.0, f"Complex policy verification took {elapsed:.3f}s > 2.0s"


class TestVerificationScalability(IntegrationTestBase):
    """Scalability tests for verification under varying artifact sizes.

    Tests verification performance with different artifact sizes
    to ensure the 2 second target holds across realistic workloads.

    Requirements: SC-006
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    @pytest.mark.requirement("8B-SC-006")
    def test_verification_large_artifact(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test verification of larger artifacts stays within target.

        Creates an artifact with expanded content (many models)
        to test verification with larger payloads.

        Verifies:
        - Verification of ~100KB artifact < 2 seconds
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.verification import VerificationClient
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
        from floe_core.schemas.signing import TrustedIssuer, VerificationPolicy
        from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]

        # Create artifact with many models to increase size
        models = [
            ResolvedModel(name=f"model_{i}_{unique_id}", compute="duckdb")
            for i in range(100)  # 100 models
        ]

        artifacts = CompiledArtifacts(
            version=COMPILED_ARTIFACTS_VERSION,
            metadata=CompilationMetadata(
                compiled_at=datetime.now(timezone.utc),
                floe_version=COMPILED_ARTIFACTS_VERSION,
                source_hash=f"sha256:large-{unique_id}",
                product_name=f"large-test-{unique_id}",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id=f"large.test_{unique_id}",
                domain="large-test",
                repository="https://github.com/test/large-repo",
            ),
            mode="simple",
            inheritance_chain=[],
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    enabled=True,
                    resource_attributes=ResourceAttributes(
                        service_name="floe-large-test",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="large-test",
                        floe_product_name=f"large-test-{unique_id}",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage_namespace="large-test-namespace",
            ),
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.9.0"),
                orchestrator=PluginRef(type="dagster", version="1.5.0"),
            ),
            transforms=ResolvedTransforms(
                models=models,
                default_compute="duckdb",
            ),
            dbt_profiles={
                "floe": {
                    "target": "dev",
                    "outputs": {"dev": {"type": "duckdb", "path": "/tmp/large.duckdb"}},
                }
            },
        )

        artifacts_path = tmp_path / "large_artifacts.json"
        artifacts.to_json_file(artifacts_path)

        # Verify artifact size is non-trivial
        artifact_size = artifacts_path.stat().st_size
        assert (
            artifact_size > 10_000
        ), f"Artifact size {artifact_size} too small for test"

        client = OCIClient.from_manifest(test_manifest_path)
        client.push(artifacts, tag=test_artifact_tag)

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
        verification_client = VerificationClient(policy)

        content = artifacts_path.read_bytes()
        artifact_ref = (
            f"oci://{client.config.uri.replace('oci://', '')}:{test_artifact_tag}"
        )

        start_time = time.monotonic()
        verification_client.verify(
            content=content,
            metadata=None,
            artifact_ref=artifact_ref,
        )
        elapsed = time.monotonic() - start_time

        print(f"\nLarge artifact ({artifact_size} bytes) verification: {elapsed:.3f}s")
        assert elapsed < 2.0, f"Large artifact verification took {elapsed:.3f}s > 2.0s"
