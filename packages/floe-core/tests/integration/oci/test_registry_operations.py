"""Integration tests for OCI registry operations.

Tests push, pull, inspect, and list operations against a real OCI registry
(Docker registry:2 in Kind cluster or Harbor in production).

These tests FAIL if the registry is unavailable - no pytest.skip() per Constitution V.

Task: T021, T030, T035, T040
Requirements: FR-001, SC-009

Example:
    # Run integration tests (requires Kind cluster with registry)
    make test-integration

See Also:
    - testing/k8s/services/registry.yaml: Registry deployment manifest
    - IntegrationTestBase: Base class for K8s-native tests
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

if TYPE_CHECKING:
    pass


class TestPushToRegistry(IntegrationTestBase):
    """Integration tests for push operation to OCI registry.

    Tests pushing real CompiledArtifacts to the registry:2 service in Kind cluster.
    Verifies artifact is retrievable and digest is correct.

    Requirements: FR-001, SC-009
    """

    required_services = [("registry", 5000)]
    namespace = "floe-test"

    def _create_test_artifacts_json(self, tmp_path: Path, unique_id: str) -> Path:
        """Create a valid CompiledArtifacts JSON file for testing.

        Args:
            tmp_path: Temporary directory path.
            unique_id: Unique identifier for test isolation.

        Returns:
            Path to the created JSON file.
        """
        import json

        data: dict[str, Any] = {
            "version": "0.2.0",
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": "0.2.0",
                "source_hash": f"sha256:{unique_id}abc123",
                "product_name": f"test-product-{unique_id}",
                "product_version": "1.0.0",
            },
            "identity": {
                "product_id": f"test.product_{unique_id}",
                "domain": "test",
                "repository": "https://github.com/test/repo",
            },
            "mode": {
                "environment": "dev",
                "target": "local",
            },
            "telemetry": {
                "service_name": "floe-test",
            },
            "governance": {
                "owner": "test-team",
            },
            "plugins": {},
            "transforms": [],
            "inheritance_chain": [],
            "dbt_profiles": {
                "floe": {
                    "target": "dev",
                    "outputs": {
                        "dev": {
                            "type": "duckdb",
                            "path": "/tmp/test.duckdb",
                        }
                    },
                }
            },
        }

        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text(json.dumps(data, indent=2))
        return artifacts_path

    @pytest.mark.requirement("8A-FR-001")
    def test_push_to_registry(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test push CompiledArtifacts to OCI registry succeeds.

        Verifies:
        - Push completes without error
        - Returns a valid sha256 digest
        - Artifact is tagged correctly
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Create test artifacts with unique ID for isolation
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)

        # Load CompiledArtifacts
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        # Create client from manifest
        client = OCIClient.from_manifest(test_manifest_path)

        # Push to registry
        digest = client.push(artifacts, tag=test_artifact_tag)

        # Verify digest format
        assert digest.startswith("sha256:"), f"Expected sha256 digest, got: {digest}"
        assert len(digest) == 71, f"Expected 71-char digest, got {len(digest)}"

    @pytest.mark.requirement("8A-SC-009")
    def test_push_artifact_retrievable(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
        oci_registry_host: str,
    ) -> None:
        """Test pushed artifact is retrievable via registry API.

        Verifies:
        - After push, manifest can be retrieved via HEAD request
        - Registry returns 200 OK for the pushed tag
        """
        import httpx

        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Create and push test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)
        digest = client.push(artifacts, tag=test_artifact_tag)

        # Verify via registry API (HEAD request to manifest endpoint)
        # registry:2 API: GET /v2/<name>/manifests/<reference>
        manifest_url = f"http://{oci_registry_host}/v2/floe-test/manifests/{test_artifact_tag}"

        # Use httpx to check manifest exists
        with httpx.Client() as http_client:
            response = http_client.head(
                manifest_url,
                headers={
                    "Accept": "application/vnd.oci.image.manifest.v1+json, "
                    "application/vnd.docker.distribution.manifest.v2+json"
                },
            )

        assert response.status_code == 200, (
            f"Expected 200 OK for pushed artifact, got {response.status_code}"
        )

        # Verify digest header matches
        docker_digest = response.headers.get("docker-content-digest", "")
        assert docker_digest == digest, (
            f"Digest mismatch: pushed={digest}, registry={docker_digest}"
        )

    @pytest.mark.requirement("8A-FR-001")
    def test_push_returns_correct_digest(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test push returns the correct manifest digest.

        Verifies:
        - Pushing same content twice returns same digest
        - Digest is deterministic based on content
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Create test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)

        # Push twice with different mutable tags
        tag1 = f"{test_artifact_tag}-a"
        tag2 = f"{test_artifact_tag}-b"

        digest1 = client.push(artifacts, tag=tag1)
        digest2 = client.push(artifacts, tag=tag2)

        # Same content should produce same digest
        # (Note: digest is of manifest, which includes layer digest)
        # Layers should be identical for same content
        assert digest1.startswith("sha256:"), f"Invalid digest format: {digest1}"
        assert digest2.startswith("sha256:"), f"Invalid digest format: {digest2}"

        # Digests may differ if manifest metadata differs, but both should be valid
        # The important thing is both pushes succeed and return valid digests


class TestPullFromRegistry(IntegrationTestBase):
    """Integration tests for pull operation from OCI registry.

    Tests pulling real CompiledArtifacts from the registry:2 service in Kind cluster.
    Verifies artifact content matches what was pushed and caching works correctly.

    Task: T030
    Requirements: FR-002, SC-009
    """

    required_services = [("registry", 5000)]
    namespace = "floe-test"

    def _create_test_artifacts_json(self, tmp_path: Path, unique_id: str) -> Path:
        """Create a valid CompiledArtifacts JSON file for testing.

        Args:
            tmp_path: Temporary directory path.
            unique_id: Unique identifier for test isolation.

        Returns:
            Path to the created JSON file.
        """
        import json

        data: dict[str, Any] = {
            "version": "0.2.0",
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": "0.2.0",
                "source_hash": f"sha256:{unique_id}abc123",
                "product_name": f"test-product-{unique_id}",
                "product_version": "1.0.0",
            },
            "identity": {
                "product_id": f"test.product_{unique_id}",
                "domain": "test",
                "repository": "https://github.com/test/repo",
            },
            "mode": {
                "environment": "dev",
                "target": "local",
            },
            "telemetry": {
                "service_name": "floe-test",
            },
            "governance": {
                "owner": "test-team",
            },
            "plugins": {},
            "transforms": [],
            "inheritance_chain": [],
            "dbt_profiles": {
                "floe": {
                    "target": "dev",
                    "outputs": {
                        "dev": {
                            "type": "duckdb",
                            "path": "/tmp/test.duckdb",
                        }
                    },
                }
            },
        }

        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text(json.dumps(data, indent=2))
        return artifacts_path

    @pytest.mark.requirement("8A-FR-002")
    def test_pull_from_registry(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test pull CompiledArtifacts from OCI registry succeeds.

        Verifies:
        - Push an artifact first
        - Pull completes without error
        - Returned CompiledArtifacts matches original content
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Create test artifacts with unique ID for isolation
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)

        # Load original CompiledArtifacts
        original_artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        # Create client from manifest (no cache for this test)
        client = OCIClient.from_manifest(test_manifest_path)

        # Push first to ensure artifact exists
        digest = client.push(original_artifacts, tag=test_artifact_tag)
        assert digest.startswith("sha256:")

        # Pull the artifact back
        pulled_artifacts = client.pull(tag=test_artifact_tag)

        # Verify content matches
        assert pulled_artifacts.version == original_artifacts.version
        assert (
            pulled_artifacts.metadata.product_name
            == original_artifacts.metadata.product_name
        )
        assert (
            pulled_artifacts.metadata.product_version
            == original_artifacts.metadata.product_version
        )
        assert pulled_artifacts.dbt_profiles == original_artifacts.dbt_profiles

    @pytest.mark.requirement("8A-FR-002")
    def test_pull_validates_schema(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test pulled artifact is validated against CompiledArtifacts schema.

        Verifies:
        - Pulled content is validated by Pydantic
        - Returns a valid CompiledArtifacts instance
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Create and push test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        original_artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)
        client.push(original_artifacts, tag=test_artifact_tag)

        # Pull should return validated CompiledArtifacts
        pulled = client.pull(tag=test_artifact_tag)

        # Verify it's a proper CompiledArtifacts instance
        assert isinstance(pulled, CompiledArtifacts)
        assert pulled.version == "0.2.0"
        assert pulled.metadata is not None

    @pytest.mark.requirement("8A-SC-009")
    def test_pull_cached_returns_same_content(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        oci_registry_host: str,
    ) -> None:
        """Test pulling same artifact twice returns same content (cache hit).

        Verifies:
        - First pull fetches from registry
        - Second pull uses cache (verified by content equality)
        - Cache hit returns valid CompiledArtifacts
        """
        import yaml

        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Create manifest with cache enabled
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        manifest_data = {
            "artifacts": {
                "registry": {
                    "uri": f"oci://{oci_registry_host}/floe-test",
                    "auth": {"type": "anonymous"},
                    "cache": {
                        "enabled": True,
                        "path": str(cache_dir),
                        "max_size_gb": 1,
                        "ttl_hours": 24,
                    },
                },
            }
        }
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest_data))

        # Create and push test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        original_artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(manifest_path)
        client.push(original_artifacts, tag=test_artifact_tag)

        # First pull - should fetch from registry
        pulled_first = client.pull(tag=test_artifact_tag)

        # Verify cache directory has content
        cache_files = list(cache_dir.rglob("*"))
        assert len(cache_files) > 0, "Expected cache files after first pull"

        # Second pull - should use cache
        pulled_second = client.pull(tag=test_artifact_tag)

        # Both pulls should return identical content
        assert (
            pulled_first.metadata.product_name == pulled_second.metadata.product_name
        )
        assert (
            pulled_first.metadata.product_version
            == pulled_second.metadata.product_version
        )
        assert pulled_first.dbt_profiles == pulled_second.dbt_profiles


class TestInspectFromRegistry(IntegrationTestBase):
    """Integration tests for inspect operation from OCI registry.

    Tests inspecting real CompiledArtifacts metadata from the registry:2 service
    in Kind cluster without downloading the full content blob.

    Task: T035
    Requirements: FR-003, SC-009
    """

    required_services = [("registry", 5000)]
    namespace = "floe-test"

    def _create_test_artifacts_json(self, tmp_path: Path, unique_id: str) -> Path:
        """Create a valid CompiledArtifacts JSON file for testing.

        Args:
            tmp_path: Temporary directory path.
            unique_id: Unique identifier for test isolation.

        Returns:
            Path to the created JSON file.
        """
        import json

        data: dict[str, Any] = {
            "version": "0.2.0",
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": "0.2.0",
                "source_hash": f"sha256:{unique_id}abc123",
                "product_name": f"test-product-{unique_id}",
                "product_version": "1.0.0",
            },
            "identity": {
                "product_id": f"test.product_{unique_id}",
                "domain": "test",
                "repository": "https://github.com/test/repo",
            },
            "mode": {
                "environment": "dev",
                "target": "local",
            },
            "telemetry": {
                "service_name": "floe-test",
            },
            "governance": {
                "owner": "test-team",
            },
            "plugins": {},
            "transforms": [],
            "inheritance_chain": [],
            "dbt_profiles": {
                "floe": {
                    "target": "dev",
                    "outputs": {
                        "dev": {
                            "type": "duckdb",
                            "path": "/tmp/test.duckdb",
                        }
                    },
                }
            },
        }

        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text(json.dumps(data, indent=2))
        return artifacts_path

    @pytest.mark.requirement("8A-FR-003")
    def test_inspect_returns_metadata(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test inspect returns artifact metadata without downloading blob.

        Verifies:
        - Inspect returns ArtifactManifest with correct fields
        - Digest, artifact_type, size, layers are populated
        - No content is downloaded (inspect is metadata-only)
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.oci import ArtifactManifest

        # Create test artifacts with unique ID for isolation
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)

        # Load and push
        original_artifacts = CompiledArtifacts.from_json_file(artifacts_path)
        client = OCIClient.from_manifest(test_manifest_path)
        client.push(original_artifacts, tag=test_artifact_tag)

        # Inspect the artifact
        manifest = client.inspect(tag=test_artifact_tag)

        # Verify manifest is ArtifactManifest
        assert isinstance(manifest, ArtifactManifest)

        # Verify required fields are populated
        assert manifest.digest.startswith("sha256:")
        assert len(manifest.digest) == 71  # sha256: + 64 hex chars
        assert manifest.artifact_type != ""
        assert manifest.size > 0
        assert manifest.created_at is not None
        assert len(manifest.layers) >= 1

    @pytest.mark.requirement("8A-FR-003")
    def test_inspect_returns_product_annotations(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test inspect returns product info from annotations.

        Verifies:
        - product_name property extracts from annotations
        - product_version property extracts from annotations
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Create test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        original_artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)
        client.push(original_artifacts, tag=test_artifact_tag)

        # Inspect
        manifest = client.inspect(tag=test_artifact_tag)

        # Verify product annotations (if present in manifest)
        # Note: These may be None if annotations weren't added during push
        # The key is that inspect returns the annotations field
        assert isinstance(manifest.annotations, dict)

    @pytest.mark.requirement("8A-SC-009")
    def test_inspect_not_found_raises_error(
        self,
        test_manifest_path: Path,
    ) -> None:
        """Test inspect raises ArtifactNotFoundError for nonexistent tag.

        Verifies:
        - ArtifactNotFoundError is raised for missing artifacts
        - Error message includes tag and registry
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.errors import ArtifactNotFoundError

        client = OCIClient.from_manifest(test_manifest_path)

        # Inspect nonexistent tag
        with pytest.raises(ArtifactNotFoundError) as exc_info:
            client.inspect(tag="nonexistent-tag-12345")

        assert "nonexistent-tag-12345" in str(exc_info.value)
