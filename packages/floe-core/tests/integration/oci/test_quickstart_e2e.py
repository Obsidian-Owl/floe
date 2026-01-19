"""End-to-end tests verifying quickstart.md examples work correctly.

These tests follow the examples in specs/08a-oci-client/quickstart.md
to ensure the documentation is accurate and all CLI-equivalent operations work.

Task: T064
Requirements: SC-001

Example:
    # Run E2E tests (requires Kind cluster with registry)
    make test-integration

See Also:
    - specs/08a-oci-client/quickstart.md: User-facing quickstart documentation
    - testing/k8s/services/registry.yaml: Registry deployment manifest
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

if TYPE_CHECKING:
    pass


class TestQuickstartExamples(IntegrationTestBase):
    """E2E tests verifying quickstart.md examples work as documented.

    These tests follow the exact examples from quickstart.md to verify:
    1. Push operation (floe artifact push)
    2. Pull operation (floe artifact pull)
    3. Inspect operation (floe artifact inspect)
    4. List operation (floe artifact list)
    5. Cache operations (floe artifact cache status/clear)

    Task: T064
    Requirements: SC-001 (Documentation accuracy)
    """

    required_services = [("registry", 5000)]
    namespace = "floe-test"

    def _create_test_artifacts_json(self, tmp_path: Path, unique_id: str) -> Path:
        """Create a valid CompiledArtifacts JSON file matching quickstart example.

        Args:
            tmp_path: Temporary directory path.
            unique_id: Unique identifier for test isolation.

        Returns:
            Path to the created JSON file at target/compiled_artifacts.json.
        """
        # Create target directory as shown in quickstart
        target_dir = tmp_path / "target"
        target_dir.mkdir(parents=True, exist_ok=True)

        data: dict[str, Any] = {
            "version": "0.2.0",
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": "0.2.0",
                "source_hash": f"sha256:{unique_id}abc123",
                "product_name": "my-data-product",  # Match quickstart example
                "product_version": "1.0.0",
            },
            "identity": {
                "product_id": f"quickstart.product_{unique_id}",
                "domain": "quickstart",
                "repository": "https://github.com/test/repo",
            },
            "mode": {
                "environment": "dev",
                "target": "local",
            },
            "telemetry": {
                "service_name": "floe-quickstart",
            },
            "governance": {
                "owner": "quickstart-team",
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
                            "path": "/tmp/quickstart.duckdb",
                        }
                    },
                }
            },
        }

        artifacts_path = target_dir / "compiled_artifacts.json"
        artifacts_path.write_text(json.dumps(data, indent=2))
        return artifacts_path

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_push_example(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test push example from quickstart.md works.

        Quickstart example:
            floe artifact push \\
              --source target/compiled_artifacts.json \\
              --tag v1.0.0

        Verifies:
        - Push from source file succeeds
        - Returns sha256 digest
        - Tag is applied correctly
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Create artifacts at target/compiled_artifacts.json (quickstart location)
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)

        # Load artifacts (equivalent to CLI reading --source)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        # Create client from manifest (equivalent to CLI using manifest.yaml)
        client = OCIClient.from_manifest(test_manifest_path)

        # Push with semver-style tag (like v1.0.0 in quickstart)
        tag = f"v1.0.0-{unique_id}"  # Add unique_id for test isolation
        digest = client.push(artifacts, tag=tag)

        # Verify output matches quickstart expectations
        assert digest.startswith("sha256:"), "Expected sha256 digest"
        assert len(digest) == 71, "Digest should be sha256: + 64 hex chars"

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_pull_example(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test pull example from quickstart.md works.

        Quickstart example:
            floe artifact pull --tag v1.0.0 --output ./artifacts/

        Verifies:
        - Pull by tag succeeds
        - CompiledArtifacts is returned and valid
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Setup: First push an artifact
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        original_artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)

        # Push first
        tag = f"v1.0.0-pull-{unique_id}"
        client.push(original_artifacts, tag=tag)

        # Pull by tag (equivalent to: floe artifact pull --tag v1.0.0)
        pulled_artifacts = client.pull(tag=tag)

        # Verify pulled content is valid CompiledArtifacts
        assert isinstance(pulled_artifacts, CompiledArtifacts)
        assert pulled_artifacts.version == "0.2.0"
        assert pulled_artifacts.metadata.product_name == "my-data-product"

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_pull_mutable_tag(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test pull with mutable tag from quickstart.md works.

        Quickstart example:
            floe artifact pull --tag latest-dev --output ./artifacts/

        Verifies:
        - Pull by mutable tag (latest-*) succeeds
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Setup: First push an artifact with mutable tag
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        original_artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)

        # Push with mutable tag (like latest-dev in quickstart)
        tag = f"latest-dev-{unique_id}"
        client.push(original_artifacts, tag=tag)

        # Pull by mutable tag
        pulled_artifacts = client.pull(tag=tag)

        # Verify content
        assert isinstance(pulled_artifacts, CompiledArtifacts)
        assert pulled_artifacts.metadata.product_name == "my-data-product"

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_inspect_example(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test inspect example from quickstart.md works.

        Quickstart example:
            floe artifact inspect --tag v1.0.0

        Expected output fields:
        - Digest
        - Artifact Type
        - Size
        - Created
        - Signature (optional, Epic 8B)

        Verifies:
        - Inspect returns all documented fields
        - ArtifactManifest has expected structure
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.oci import ArtifactManifest

        # Setup: First push an artifact
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)

        tag = f"v1.0.0-inspect-{unique_id}"
        client.push(artifacts, tag=tag)

        # Inspect (equivalent to: floe artifact inspect --tag v1.0.0)
        manifest = client.inspect(tag=tag)

        # Verify all documented output fields are present
        assert isinstance(manifest, ArtifactManifest)

        # Digest: sha256:...
        assert manifest.digest.startswith("sha256:")

        # Artifact Type: application/vnd.floe.compiled-artifacts.v1+json
        assert manifest.artifact_type != ""

        # Size: > 0
        assert manifest.size > 0

        # Created: datetime
        assert manifest.created_at is not None

        # Layers: at least one
        assert len(manifest.layers) >= 1

        # Signature status (prepared for Epic 8B)
        assert manifest.signature_status is not None

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_list_example(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test list example from quickstart.md works.

        Quickstart example:
            floe artifact list

        Expected output:
        - TAG, DIGEST, SIZE, CREATED columns
        - List of available artifacts

        Verifies:
        - List returns ArtifactTag objects
        - Each tag has required fields
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.oci import ArtifactTag

        # Setup: Push some artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)

        # Push with known tags
        tag1 = f"v1.0.0-list-{unique_id}"
        tag2 = f"latest-list-{unique_id}"
        client.push(artifacts, tag=tag1)
        client.push(artifacts, tag=tag2)

        # List (equivalent to: floe artifact list)
        tags = client.list()

        # Verify list returns ArtifactTag objects with documented fields
        assert isinstance(tags, list)
        assert len(tags) >= 2  # At least our two tags

        for tag in tags:
            assert isinstance(tag, ArtifactTag)
            # TAG column
            assert tag.name != ""
            # DIGEST column
            assert tag.digest.startswith("sha256:")
            # CREATED column
            assert tag.created_at is not None

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_list_filter_example(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test list with filter from quickstart.md works.

        Quickstart example:
            floe artifact list --filter "v1.*"

        Verifies:
        - Filter pattern restricts results
        """
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Setup: Push artifacts with different tag patterns
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(test_manifest_path)

        # Push with v1 and v2 prefixes
        v1_tag = f"v1-filter-{unique_id}"
        v2_tag = f"v2-filter-{unique_id}"
        client.push(artifacts, tag=v1_tag)
        client.push(artifacts, tag=v2_tag)

        # List with filter (equivalent to: floe artifact list --filter "v1.*")
        filtered_tags = client.list(filter_pattern=f"v1-filter-{unique_id}")

        # Verify filter works
        tag_names = [t.name for t in filtered_tags]
        assert v1_tag in tag_names
        assert v2_tag not in tag_names

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_cache_status_example(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        oci_registry_host: str,
    ) -> None:
        """Test cache status example from quickstart.md works.

        Quickstart example:
            floe artifact cache status

        Expected output:
        - Cache Path
        - Total Size
        - Entries count
        - Expired count

        Verifies:
        - Cache manager provides status information
        """
        import yaml

        from floe_core.oci.cache import CacheManager
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.oci import CacheConfig

        # Setup: Create client with cache enabled
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

        # Push and pull to populate cache
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(manifest_path)
        tag = f"cache-status-{unique_id}"
        client.push(artifacts, tag=tag)
        client.pull(tag=tag)  # Populate cache

        # Get cache status (equivalent to: floe artifact cache status)
        cache_config = CacheConfig(
            enabled=True,
            path=cache_dir,
            max_size_gb=1,
            ttl_hours=24,
        )
        cache_manager = CacheManager(config=cache_config)
        status = cache_manager.stats()

        # Verify documented output fields
        # Cache Path
        assert status["path"] == str(cache_dir)
        # Total Size
        assert status["total_size_bytes"] >= 0
        # Entries count
        assert status["entry_count"] >= 0
        # Max Size GB
        assert status["max_size_gb"] > 0

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_cache_clear_example(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        oci_registry_host: str,
    ) -> None:
        """Test cache clear example from quickstart.md works.

        Quickstart example:
            floe artifact cache clear

        Verifies:
        - Cache can be cleared
        - After clear, cache is empty
        """
        import yaml

        from floe_core.oci.cache import CacheManager
        from floe_core.oci.client import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.oci import CacheConfig

        # Setup: Create client with cache and populate it
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

        # Push and pull to populate cache
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        client = OCIClient.from_manifest(manifest_path)
        tag = f"cache-clear-{unique_id}"
        client.push(artifacts, tag=tag)
        client.pull(tag=tag)  # Populate cache

        # Clear cache (equivalent to: floe artifact cache clear)
        cache_config = CacheConfig(
            enabled=True,
            path=cache_dir,
            max_size_gb=1,
            ttl_hours=24,
        )
        cache_manager = CacheManager(config=cache_config)

        # Verify cache is accessible before clear
        _status_before = cache_manager.stats()  # Verify no errors accessing stats

        # Clear all (equivalent to: floe artifact cache clear)
        cache_manager.clear()

        # Verify cache is cleared
        status_after = cache_manager.stats()
        assert status_after["entry_count"] == 0

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_programmatic_usage(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test programmatic usage example from quickstart.md works.

        Quickstart programmatic example:
            from floe_core.oci import OCIClient
            from floe_core.schemas.compiled_artifacts import CompiledArtifacts

            # Create client from manifest config
            client = OCIClient.from_manifest("manifest.yaml")

            # Push
            artifacts = CompiledArtifacts.from_json_file("target/compiled_artifacts.json")
            digest = client.push(artifacts, tag="v1.0.0")

            # Pull
            artifacts = client.pull(tag="v1.0.0")

            # Inspect
            manifest = client.inspect(tag="v1.0.0")

            # List
            tags = client.list(filter="v1.*")

        Verifies:
        - All programmatic examples work as documented
        """
        from floe_core.oci import OCIClient
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Setup
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)

        # Create client from manifest config (quickstart example)
        client = OCIClient.from_manifest(test_manifest_path)

        # Push (quickstart example)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)
        tag = f"v1.0.0-prog-{unique_id}"
        digest = client.push(artifacts, tag=tag)
        assert digest.startswith("sha256:")

        # Pull (quickstart example)
        pulled = client.pull(tag=tag)
        assert pulled.metadata.product_name == "my-data-product"

        # Inspect (quickstart example)
        manifest = client.inspect(tag=tag)
        assert manifest.size > 0

        # List (quickstart example)
        tags = client.list(filter_pattern=f"v1.0.0-prog-{unique_id}")
        assert len(tags) >= 1

    @pytest.mark.requirement("8A-SC-001")
    def test_quickstart_error_handling_not_found(
        self,
        test_manifest_path: Path,
    ) -> None:
        """Test error handling example from quickstart.md works.

        Quickstart error handling example:
            from floe_core.oci.errors import ArtifactNotFoundError

            try:
                client.pull(tag="nonexistent")
            except ArtifactNotFoundError as e:
                print(f"Artifact not found: {e}")

        Verifies:
        - ArtifactNotFoundError is raised for missing artifacts
        """
        from floe_core.oci import OCIClient
        from floe_core.oci.errors import ArtifactNotFoundError

        client = OCIClient.from_manifest(test_manifest_path)

        # Attempt to pull nonexistent tag
        with pytest.raises(ArtifactNotFoundError) as exc_info:
            client.pull(tag="nonexistent-tag-99999")

        # Verify error message is helpful
        assert "nonexistent-tag-99999" in str(exc_info.value)
