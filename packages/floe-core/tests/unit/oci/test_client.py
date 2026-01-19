"""Unit tests for OCIClient push and pull operations.

This module tests the OCIClient class for:
- Push operations (T013, T017-T019)
- Pull operations (T022, T024-T027)
- Immutability enforcement (FR-010, FR-011)
- Error handling

All tests use mocked ORAS SDK - no network calls.

Task: T013, T022
Requirements: FR-001, FR-002, FR-010, FR-011
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from floe_core.oci.client import MUTABLE_TAG_PATTERNS, SEMVER_PATTERN, OCIClient
from floe_core.oci.errors import ArtifactNotFoundError, ImmutabilityViolationError
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
from floe_core.schemas.oci import AuthType, CacheConfig, RegistryAuth, RegistryConfig
from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

if TYPE_CHECKING:
    pass


# =============================================================================
# Test Constants
# =============================================================================

# Valid SHA256 digest for test layers (64 hex characters)
TEST_LAYER_DIGEST = "sha256:abc123def456789012345678901234567890123456789012345678901234abcd"

# Mock tag list for list operation tests (avoids duplication in multiple tests)
MOCK_LIST_TAGS = ["v1.0.0", "v1.1.0", "latest-dev"]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_telemetry_config() -> TelemetryConfig:
    """Create a sample TelemetryConfig for testing."""
    return TelemetryConfig(
        enabled=True,
        resource_attributes=ResourceAttributes(
            service_name="test-pipeline",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        ),
    )


@pytest.fixture
def sample_observability_config(sample_telemetry_config: TelemetryConfig) -> ObservabilityConfig:
    """Create a sample ObservabilityConfig for testing."""
    return ObservabilityConfig(
        telemetry=sample_telemetry_config,
        lineage=True,
        lineage_namespace="test-namespace",
    )


@pytest.fixture
def sample_compilation_metadata() -> CompilationMetadata:
    """Create a sample CompilationMetadata for testing."""
    return CompilationMetadata(
        compiled_at=datetime.now(timezone.utc),
        floe_version="0.2.0",
        source_hash="sha256:abc123",
        product_name="test-product",
        product_version="1.0.0",
    )


@pytest.fixture
def sample_product_identity() -> ProductIdentity:
    """Create a sample ProductIdentity for testing."""
    return ProductIdentity(
        product_id="default.test_product",
        domain="default",
        repository="github.com/acme/test",
    )


@pytest.fixture
def sample_resolved_plugins() -> ResolvedPlugins:
    """Create sample ResolvedPlugins for testing."""
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0"),
        orchestrator=PluginRef(type="dagster", version="1.5.0"),
    )


@pytest.fixture
def sample_resolved_transforms() -> ResolvedTransforms:
    """Create sample ResolvedTransforms for testing."""
    return ResolvedTransforms(
        models=[
            ResolvedModel(name="stg_customers", compute="duckdb"),
            ResolvedModel(name="fct_orders", compute="duckdb"),
        ],
        default_compute="duckdb",
    )


@pytest.fixture
def sample_compiled_artifacts(
    sample_compilation_metadata: CompilationMetadata,
    sample_product_identity: ProductIdentity,
    sample_observability_config: ObservabilityConfig,
    sample_resolved_plugins: ResolvedPlugins,
    sample_resolved_transforms: ResolvedTransforms,
) -> CompiledArtifacts:
    """Create a valid CompiledArtifacts for testing push operations."""
    return CompiledArtifacts(
        version="0.2.0",
        metadata=sample_compilation_metadata,
        identity=sample_product_identity,
        mode="simple",
        inheritance_chain=[],  # Required by mypy, default_factory=list
        observability=sample_observability_config,
        plugins=sample_resolved_plugins,
        transforms=sample_resolved_transforms,
        dbt_profiles={
            "default": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": "/tmp/test.duckdb",
                    }
                },
            }
        },
    )


@pytest.fixture
def sample_registry_config() -> RegistryConfig:
    """Create a sample RegistryConfig with AWS IRSA auth (no secrets required)."""
    return RegistryConfig(
        uri="oci://harbor.example.com/floe-platform",
        auth=RegistryAuth(type=AuthType.AWS_IRSA),
        tls_verify=True,
        cache=CacheConfig(enabled=False),  # Disable cache for unit tests
    )


@pytest.fixture
def mock_auth_provider() -> MagicMock:
    """Create a mock AuthProvider for testing."""
    from floe_core.oci.auth import Credentials

    provider = MagicMock()
    provider.get_credentials.return_value = Credentials(
        username="test-user",
        password="test-password",
        expires_at=datetime.now(timezone.utc),
    )
    provider.refresh_if_needed.return_value = False
    return provider


@pytest.fixture
def oci_client(
    sample_registry_config: RegistryConfig,
    mock_auth_provider: MagicMock,
) -> OCIClient:
    """Create an OCIClient with mocked dependencies for testing."""
    return OCIClient(
        registry_config=sample_registry_config,
        auth_provider=mock_auth_provider,
    )


# =============================================================================
# Test Classes
# =============================================================================


class TestOCIClientTagClassification:
    """Tests for tag immutability classification."""

    @pytest.mark.requirement("8A-FR-010")
    def test_semver_tags_are_immutable(self, oci_client: OCIClient) -> None:
        """Test that semver tags are classified as immutable.

        FR-010: System MUST reject pushes to existing semver tags.
        """
        # Standard semver tags
        assert oci_client.is_tag_immutable("v1.0.0") is True
        assert oci_client.is_tag_immutable("v0.1.0") is True
        assert oci_client.is_tag_immutable("v2.10.5") is True

        # Semver without v prefix
        assert oci_client.is_tag_immutable("1.0.0") is True
        assert oci_client.is_tag_immutable("0.1.0") is True

        # Semver with pre-release
        assert oci_client.is_tag_immutable("v1.0.0-alpha") is True
        assert oci_client.is_tag_immutable("v1.0.0-beta.1") is True
        assert oci_client.is_tag_immutable("1.0.0-rc.2") is True

        # Semver with build metadata
        assert oci_client.is_tag_immutable("v1.0.0+build123") is True
        assert oci_client.is_tag_immutable("1.0.0+20260119") is True

    @pytest.mark.requirement("8A-FR-011")
    def test_mutable_tags_are_not_immutable(self, oci_client: OCIClient) -> None:
        """Test that mutable pattern tags are classified as mutable.

        FR-011: System MUST allow pushes to mutable tags.
        """
        # latest-* pattern
        assert oci_client.is_tag_immutable("latest") is False
        assert oci_client.is_tag_immutable("latest-dev") is False
        assert oci_client.is_tag_immutable("latest-staging") is False

        # dev-* pattern
        assert oci_client.is_tag_immutable("dev") is False
        assert oci_client.is_tag_immutable("dev-feature-branch") is False

        # snapshot-* pattern
        assert oci_client.is_tag_immutable("snapshot") is False
        assert oci_client.is_tag_immutable("snapshot-20260119") is False
        assert oci_client.is_tag_immutable("snapshot-abc123") is False

    @pytest.mark.requirement("8A-FR-010")
    def test_unknown_tags_default_to_immutable(self, oci_client: OCIClient) -> None:
        """Test that unknown tag patterns default to immutable (safe default)."""
        # Random strings should be treated as immutable by default
        assert oci_client.is_tag_immutable("release-candidate") is True
        assert oci_client.is_tag_immutable("production") is True
        assert oci_client.is_tag_immutable("main") is True


class TestSemverPatternRegex:
    """Tests for the SEMVER_PATTERN regex."""

    @pytest.mark.requirement("8A-FR-010")
    def test_semver_pattern_matches_valid_versions(self) -> None:
        """Test SEMVER_PATTERN matches valid semantic versions."""
        valid_versions = [
            "1.0.0",
            "v1.0.0",
            "0.1.0",
            "v0.1.0",
            "10.20.30",
            "v10.20.30",
            "1.0.0-alpha",
            "v1.0.0-beta.1",
            "1.0.0-rc.2",
            "1.0.0+build123",
            "v1.0.0-alpha+build",
        ]
        for version in valid_versions:
            assert SEMVER_PATTERN.match(version) is not None, f"Should match: {version}"

    @pytest.mark.requirement("8A-FR-011")
    def test_semver_pattern_rejects_invalid_versions(self) -> None:
        """Test SEMVER_PATTERN rejects non-semver strings."""
        invalid_versions = [
            "latest",
            "dev",
            "main",
            "1.0",
            "v1",
            "1.0.0.0",
            "v1.0.0.0",
            "release-1.0",
            "",
        ]
        for version in invalid_versions:
            assert SEMVER_PATTERN.match(version) is None, f"Should not match: {version}"


class TestMutableTagPatterns:
    """Tests for MUTABLE_TAG_PATTERNS list."""

    @pytest.mark.requirement("8A-FR-011")
    def test_mutable_patterns_match_expected_tags(self) -> None:
        """Test MUTABLE_TAG_PATTERNS match expected mutable tags."""
        mutable_tags = [
            ("latest", True),
            ("latest-dev", True),
            ("latest-staging", True),
            ("dev", True),
            ("dev-feature", True),
            ("snapshot", True),
            ("snapshot-123", True),
            ("v1.0.0", False),  # Semver should NOT match mutable patterns
            ("production", False),  # Random string should NOT match
        ]

        for tag, should_match in mutable_tags:
            matched = any(p.match(tag) for p in MUTABLE_TAG_PATTERNS)
            assert matched == should_match, f"Tag '{tag}' match={matched}, expected={should_match}"


class TestOCIClientPush:
    """Tests for OCIClient.push() operation."""

    @pytest.mark.requirement("8A-FR-001")
    def test_push_artifact_success(
        self,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test successful push of CompiledArtifacts to registry.

        FR-001: System MUST push CompiledArtifacts to OCI registries.
        """
        # Mock ORAS client push response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 201

        mock_oras_client = MagicMock()
        mock_oras_client.push.return_value = mock_response

        # Mock tag_exists to return False (new tag)
        with (
            patch.object(oci_client, "tag_exists", return_value=False),
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras_client),
        ):
            digest = oci_client.push(sample_compiled_artifacts, tag="v1.0.0")

            # Verify digest is returned
            assert digest.startswith("sha256:")
            assert len(digest) == 71  # sha256: + 64 hex chars

            # Verify ORAS push was called
            mock_oras_client.push.assert_called_once()
            call_kwargs = mock_oras_client.push.call_args.kwargs
            assert "v1.0.0" in call_kwargs.get("target", "")

    @pytest.mark.requirement("8A-FR-001")
    def test_push_artifact_with_annotations(
        self,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test push includes custom annotations.

        FR-001: System MUST push CompiledArtifacts with metadata annotations.
        """
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 201

        mock_oras_client = MagicMock()
        mock_oras_client.push.return_value = mock_response

        custom_annotations = {"custom.key": "custom-value"}

        with (
            patch.object(oci_client, "tag_exists", return_value=False),
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras_client),
        ):
            digest = oci_client.push(
                sample_compiled_artifacts,
                tag="v1.0.0",
                annotations=custom_annotations,
            )

            assert digest.startswith("sha256:")

            # Verify annotations were passed to ORAS
            call_kwargs = mock_oras_client.push.call_args.kwargs
            manifest_annotations = call_kwargs.get("manifest_annotations", {})
            assert "io.floe.product.name" in manifest_annotations
            assert manifest_annotations.get("custom.key") == "custom-value"

    @pytest.mark.requirement("8A-FR-010")
    def test_push_rejects_existing_semver_tag(
        self,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test push() raises ImmutabilityViolationError for existing semver tags.

        FR-010: System MUST reject pushes to existing semver tags.

        This tests that the full push() operation enforces immutability,
        not just the internal helper.
        """
        # Mock tag_exists to return True (tag already exists)
        with patch.object(oci_client, "tag_exists", return_value=True):
            with pytest.raises(ImmutabilityViolationError) as exc_info:
                oci_client.push(sample_compiled_artifacts, tag="v1.0.0")

            # Verify error contains useful information
            assert "v1.0.0" in str(exc_info.value)
            assert "immutable" in str(exc_info.value).lower()

    @pytest.mark.requirement("8A-FR-011")
    def test_push_allows_mutable_tags_to_be_overwritten(
        self,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test push() allows overwriting mutable tags.

        FR-011: System MUST allow pushes to mutable tags (latest-*, dev-*, etc).
        """
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 201

        mock_oras_client = MagicMock()
        mock_oras_client.push.return_value = mock_response

        # Tag exists but is mutable
        with (
            patch.object(oci_client, "tag_exists", return_value=True),
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras_client),
        ):
            # Should succeed for mutable tag even though it exists
            digest = oci_client.push(sample_compiled_artifacts, tag="latest-dev")
            assert digest.startswith("sha256:")

    @pytest.mark.requirement("8A-FR-010")
    def test_push_immutability_check_raises_error(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Test that immutability check raises error for existing semver tags.

        FR-010: System MUST reject pushes to existing semver tags.

        Note: This tests the _check_immutability_before_push helper.
        The full push operation will use this check.
        """
        # Mock tag_exists to return True (tag already exists)
        with patch.object(oci_client, "tag_exists", return_value=True):
            with pytest.raises(ImmutabilityViolationError) as exc_info:
                oci_client._check_immutability_before_push("v1.0.0")

            # Verify error contains useful information
            assert "v1.0.0" in str(exc_info.value)
            assert "immutable" in str(exc_info.value).lower()

    @pytest.mark.requirement("8A-FR-010")
    def test_push_immutability_check_allows_new_tags(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Test that immutability check allows pushing to non-existent tags.

        Even semver tags can be pushed if they don't exist yet.
        """
        # Mock tag_exists to return False (tag doesn't exist)
        with patch.object(oci_client, "tag_exists", return_value=False):
            # Should not raise - new tag can be pushed
            oci_client._check_immutability_before_push("v1.0.0")

    @pytest.mark.requirement("8A-FR-011")
    def test_push_immutability_check_allows_mutable_tags(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Test that immutability check allows mutable tags even if they exist.

        FR-011: System MUST allow pushes to mutable tags.
        """
        # Mock tag_exists to return True (tag already exists)
        with patch.object(oci_client, "tag_exists", return_value=True):
            # Should not raise for mutable tags
            oci_client._check_immutability_before_push("latest-dev")
            oci_client._check_immutability_before_push("dev")
            oci_client._check_immutability_before_push("snapshot-123")


class TestOCIClientPull:
    """Tests for OCIClient.pull() operation.

    FR-002: System MUST pull OCI artifacts and deserialize to CompiledArtifacts.
    FR-018: System MUST implement retry with exponential backoff.
    """

    @pytest.mark.requirement("8A-FR-002")
    def test_pull_artifact_success(
        self,
        tmp_path: Path,
        sample_compiled_artifacts: CompiledArtifacts,
        oci_client: OCIClient,
    ) -> None:
        """Test successful pull of CompiledArtifacts from registry.

        Verifies:
        - pull() returns CompiledArtifacts instance
        - Returned artifacts have correct product_name
        - ORAS client pull was called with correct reference
        """
        import json

        # Setup: Create temp file with serialized artifacts
        artifacts_json = json.dumps(
            sample_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        # Mock ORAS client and its pull method
        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            result = oci_client.pull(tag="v1.0.0")

        assert isinstance(result, CompiledArtifacts)
        assert result.metadata.product_name == sample_compiled_artifacts.metadata.product_name
        mock_oras.pull.assert_called_once()

    @pytest.mark.requirement("8A-FR-002")
    def test_pull_not_found_raises_error(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Test that pulling non-existent tag raises ArtifactNotFoundError.

        Verifies:
        - ArtifactNotFoundError raised for missing tags
        - Error message includes tag name
        """
        # Mock ORAS to raise 404-equivalent error
        mock_oras = MagicMock()
        mock_oras.pull.side_effect = Exception("manifest unknown")

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            with pytest.raises(ArtifactNotFoundError) as exc_info:
                oci_client.pull(tag="nonexistent")

            assert "nonexistent" in str(exc_info.value)

    @pytest.mark.requirement("8A-FR-018")
    def test_pull_with_retry_on_transient_failure(
        self,
        tmp_path: Path,
        sample_compiled_artifacts: CompiledArtifacts,
        oci_client: OCIClient,
    ) -> None:
        """Test that pull retries on transient failures.

        Verifies:
        - Pull succeeds after transient failures
        - ORAS pull is called multiple times on retry
        """
        import json

        # Setup artifacts
        artifacts_json = json.dumps(
            sample_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        artifacts_file = pull_dir / "compiled_artifacts.json"
        artifacts_file.write_text(artifacts_json)

        # Mock: First call fails, second succeeds
        call_count = 0

        def mock_pull(*args: Any, **kwargs: Any) -> list[str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection reset by peer")
            return [str(artifacts_file)]

        mock_oras = MagicMock()
        mock_oras.pull.side_effect = mock_pull

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            result = oci_client.pull(tag="v1.0.0")

        assert isinstance(result, CompiledArtifacts)
        # Exact assertion: 1 failure + 1 success = 2 total calls
        assert call_count == 2, f"Expected exactly 2 attempts (1 fail + 1 success), got {call_count}"

    @pytest.mark.requirement("8A-FR-002")
    def test_pull_validates_artifact_schema(
        self,
        tmp_path: Path,
        oci_client: OCIClient,
    ) -> None:
        """Test that pull validates artifact against CompiledArtifacts schema.

        Verifies:
        - Invalid JSON content raises error
        - Corrupt artifacts are rejected
        """
        from pydantic import ValidationError

        from floe_core.oci.errors import OCIError

        # Setup: Create invalid JSON
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        invalid_file = pull_dir / "compiled_artifacts.json"
        invalid_file.write_text('{"invalid": "schema"}')

        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(invalid_file)]

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            # Should raise validation error for invalid schema
            with pytest.raises((ValidationError, OCIError)):
                oci_client.pull(tag="v1.0.0")


class TestOCIClientList:
    """Tests for OCIClient.list() operation.

    Task: T036
    Requirements: FR-004
    """

    @pytest.mark.requirement("8A-FR-004")
    def test_list_artifacts(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Test list() returns all artifacts in namespace.

        FR-004: System MUST support listing artifacts with filtering.

        Verifies:
        - list() returns list of ArtifactTag objects
        - Each ArtifactTag has name, digest, created_at fields
        """
        from datetime import datetime

        from floe_core.schemas.oci import ArtifactTag

        # Mock the ORAS client to return tag list
        # Note: ORAS get_tags() returns list directly, not {"tags": [...]}
        mock_tags_list = MOCK_LIST_TAGS

        with patch.object(oci_client, "_create_oras_client") as mock_create:
            mock_oras = MagicMock()
            mock_oras.get_tags.return_value = mock_tags_list

            # Mock get_manifest for each tag to get digest and created_at
            # Note: ORAS uses container= parameter, not target=
            def mock_get_manifest(container: str | None = None, **_kwargs: Any) -> dict[str, Any]:
                # Return mock manifest data (accepts **kwargs for ORAS client flexibility)
                return {
                    "schemaVersion": 2,
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "config": {
                        "mediaType": "application/vnd.oci.empty.v1+json",
                        "digest": "sha256:abc123",
                        "size": 0,
                    },
                    "layers": [
                        {
                            "mediaType": "application/vnd.floe.compiled-artifacts.v1+json",
                            "digest": "sha256:layer123",
                            "size": 1000,
                        }
                    ],
                    "annotations": {
                        "org.opencontainers.image.created": "2026-01-19T10:00:00Z",
                    },
                }

            mock_oras.get_manifest.side_effect = mock_get_manifest
            mock_create.return_value = mock_oras

            # Call list()
            result = oci_client.list()

        # Verify result is a list
        assert isinstance(result, list)
        assert len(result) == 3

        # Verify each item is an ArtifactTag
        for tag in result:
            assert isinstance(tag, ArtifactTag)
            assert tag.name in MOCK_LIST_TAGS
            assert tag.digest.startswith("sha256:")
            assert isinstance(tag.created_at, datetime)

    @pytest.mark.requirement("8A-FR-004")
    def test_list_with_filter(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Test list() with filter_pattern filters results.

        FR-004: System MUST support filtering by tag pattern.

        Verifies:
        - filter_pattern="v1.*" returns only v1.x tags
        - Pattern matching uses glob-style wildcards
        """
        # Note: ORAS get_tags() returns list directly, not {"tags": [...]}
        mock_tags_list = ["v1.0.0", "v1.1.0", "v2.0.0", "latest-dev"]

        with patch.object(oci_client, "_create_oras_client") as mock_create:
            mock_oras = MagicMock()
            mock_oras.get_tags.return_value = mock_tags_list

            # Note: ORAS uses container= parameter, not target=
            def mock_get_manifest(container: str | None = None, **_kwargs: Any) -> dict[str, Any]:
                return {
                    "schemaVersion": 2,
                    "layers": [
                        {
                            "mediaType": "application/vnd.floe.compiled-artifacts.v1+json",
                            "digest": "sha256:layer123",
                            "size": 1000,
                        }
                    ],
                    "annotations": {
                        "org.opencontainers.image.created": "2026-01-19T10:00:00Z",
                    },
                }

            mock_oras.get_manifest.side_effect = mock_get_manifest
            mock_create.return_value = mock_oras

            # Call list() with filter
            result = oci_client.list(filter_pattern="v1.*")

        # Should only return v1.x tags
        assert len(result) == 2
        tag_names = [tag.name for tag in result]
        assert "v1.0.0" in tag_names
        assert "v1.1.0" in tag_names
        assert "v2.0.0" not in tag_names
        assert "latest-dev" not in tag_names

    @pytest.mark.requirement("8A-FR-004")
    def test_list_empty_namespace(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Test list() returns empty list when no artifacts exist.

        Verifies:
        - Empty namespace returns empty list, not None
        - No error raised for empty results
        """
        mock_tags_response: dict[str, list[str]] = {
            "tags": [],
        }

        with patch.object(oci_client, "_create_oras_client") as mock_create:
            mock_oras = MagicMock()
            mock_oras.get_tags.return_value = mock_tags_response
            mock_create.return_value = mock_oras

            result = oci_client.list()

        assert isinstance(result, list)
        assert len(result) == 0


class TestOCIClientCapabilities:
    """Tests for OCIClient.check_registry_capabilities() operation."""

    @pytest.mark.requirement("8A-FR-012")
    def test_check_capabilities_returns_expected_fields(
        self,
        oci_client: OCIClient,
        mock_auth_provider: MagicMock,
    ) -> None:
        """Test that check_registry_capabilities returns expected fields.

        FR-012: System MUST validate registry supports immutability.
        """
        capabilities = oci_client.check_registry_capabilities()

        # Verify all expected fields are present
        assert "reachable" in capabilities
        assert "authenticated" in capabilities
        assert "oci_v1_1" in capabilities
        assert "artifact_type_filtering" in capabilities
        assert "immutability_enforcement" in capabilities
        assert "registry" in capabilities
        assert "auth_type" in capabilities

        # Verify immutability is client-side enforced
        assert capabilities["immutability_enforcement"] == "client-side"

        # Verify auth provider was called
        mock_auth_provider.get_credentials.assert_called_once()

    @pytest.mark.requirement("8A-FR-012")
    def test_check_capabilities_returns_registry_info(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Test that capabilities includes registry information."""
        capabilities = oci_client.check_registry_capabilities()

        assert capabilities["registry"] == "harbor.example.com"
        assert capabilities["auth_type"] == "aws-irsa"


class TestOCIClientFromManifest:
    """Tests for OCIClient.from_manifest() factory method."""

    @pytest.mark.requirement("8A-FR-022")
    def test_from_manifest_creates_client(self, tmp_path: Path) -> None:
        """Test that from_manifest creates client from manifest.yaml.

        FR-022: System MUST read registry config from manifest.yaml.
        """
        manifest_path = tmp_path / "manifest.yaml"
        manifest_content = """
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe-platform"
    auth:
      type: aws-irsa
    tls_verify: true
    cache:
      enabled: false
"""
        manifest_path.write_text(manifest_content)

        client = OCIClient.from_manifest(manifest_path)

        assert client.registry_uri == "oci://harbor.example.com/floe-platform"
        assert client.config.auth.type == AuthType.AWS_IRSA
        assert client.config.tls_verify is True

    @pytest.mark.requirement("8A-FR-022")
    def test_from_manifest_raises_on_missing_file(self, tmp_path: Path) -> None:
        """Test that from_manifest raises error for missing file."""
        from floe_core.oci.errors import OCIError

        manifest_path = tmp_path / "nonexistent.yaml"

        with pytest.raises(OCIError, match="Manifest file not found"):
            OCIClient.from_manifest(manifest_path)

    @pytest.mark.requirement("8A-FR-022")
    def test_from_manifest_raises_on_missing_registry_section(
        self, tmp_path: Path
    ) -> None:
        """Test that from_manifest raises error when registry section missing."""
        from floe_core.oci.errors import OCIError

        manifest_path = tmp_path / "manifest.yaml"
        manifest_content = """
metadata:
  name: test
"""
        manifest_path.write_text(manifest_content)

        with pytest.raises(OCIError, match="Missing 'artifacts.registry'"):
            OCIClient.from_manifest(manifest_path)


class TestOCIClientPushOTelInstrumentation:
    """Tests for OpenTelemetry instrumentation in push operations.

    Task: T019
    Requirements: FR-031, FR-034
    """

    @pytest.mark.requirement("8A-FR-031")
    def test_push_creates_span_with_correct_name(
        self,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test push() creates a span named 'floe.oci.push'.

        FR-031: System MUST emit OpenTelemetry spans for all operations.
        """
        from floe_core.oci.metrics import OCIMetrics

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 201

        mock_oras_client = MagicMock()
        mock_oras_client.push.return_value = mock_response

        # Track span creation
        span_created = []

        # Create real metrics object and mock its create_span method
        original_metrics = oci_client.metrics

        # Mock the create_span context manager
        from contextlib import contextmanager

        @contextmanager
        def mock_create_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
            span_created.append({"name": name, "attributes": attributes or {}})
            mock_span = MagicMock()
            mock_span.set_attribute = MagicMock()
            mock_span.set_status = MagicMock()
            mock_span.record_exception = MagicMock()
            yield mock_span

        with (
            patch.object(oci_client, "tag_exists", return_value=False),
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras_client),
            patch.object(original_metrics, "create_span", side_effect=mock_create_span),
        ):
            oci_client.push(sample_compiled_artifacts, tag="v1.0.0")

        # Verify span was created with correct name
        assert len(span_created) == 1
        assert span_created[0]["name"] == OCIMetrics.SPAN_PUSH

    @pytest.mark.requirement("8A-FR-031")
    def test_push_span_includes_required_attributes(
        self,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test push() span includes registry, tag, and product attributes.

        FR-031: Spans MUST include operation-specific attributes.
        """
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 201

        mock_oras_client = MagicMock()
        mock_oras_client.push.return_value = mock_response

        span_attributes: dict[str, Any] = {}

        from contextlib import contextmanager

        @contextmanager
        def mock_create_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
            span_attributes.update(attributes or {})
            mock_span = MagicMock()

            def capture_attribute(key: str, value: Any) -> None:
                span_attributes[key] = value

            mock_span.set_attribute = capture_attribute
            mock_span.set_status = MagicMock()
            mock_span.record_exception = MagicMock()
            yield mock_span

        original_metrics = oci_client.metrics

        with (
            patch.object(oci_client, "tag_exists", return_value=False),
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras_client),
            patch.object(original_metrics, "create_span", side_effect=mock_create_span),
        ):
            oci_client.push(sample_compiled_artifacts, tag="v1.0.0")

        # Verify required attributes
        assert "oci.registry" in span_attributes
        assert span_attributes["oci.registry"] == "harbor.example.com"
        assert "oci.tag" in span_attributes
        assert span_attributes["oci.tag"] == "v1.0.0"
        assert "oci.product.name" in span_attributes
        assert "oci.product.version" in span_attributes

    @pytest.mark.requirement("8A-FR-034")
    def test_push_records_duration_metric(
        self,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test push() records operation duration in histogram.

        FR-034: System MUST emit operation duration metrics.
        """
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 201

        mock_oras_client = MagicMock()
        mock_oras_client.push.return_value = mock_response

        # Track duration recording
        duration_recorded: list[tuple[str, str, float]] = []

        def mock_record_duration(
            operation: str, registry: str, duration: float, **kwargs: Any
        ) -> None:
            duration_recorded.append((operation, registry, duration))

        original_metrics = oci_client.metrics

        # Also need to mock create_span to avoid actual OTel calls
        from contextlib import contextmanager

        @contextmanager
        def mock_create_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
            mock_span = MagicMock()
            mock_span.set_attribute = MagicMock()
            mock_span.set_status = MagicMock()
            mock_span.record_exception = MagicMock()
            yield mock_span

        with (
            patch.object(oci_client, "tag_exists", return_value=False),
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras_client),
            patch.object(original_metrics, "record_duration", side_effect=mock_record_duration),
            patch.object(original_metrics, "create_span", side_effect=mock_create_span),
        ):
            oci_client.push(sample_compiled_artifacts, tag="v1.0.0")

        # Verify duration was recorded for push operation
        assert len(duration_recorded) == 1
        operation, registry, duration = duration_recorded[0]
        assert operation == "push"
        assert "harbor" in registry
        assert duration >= 0  # Duration should be non-negative

    @pytest.mark.requirement("8A-FR-034")
    def test_push_failure_records_error_in_span(
        self,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test push() records exception in span on failure.

        FR-034: Spans MUST record exceptions on failure.

        Note: The OCIMetrics.create_span context manager automatically calls
        span.set_status() and span.record_exception() when an exception occurs
        within the `with` block. This test verifies that flow works correctly.
        """
        from floe_core.oci.errors import RegistryUnavailableError

        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        mock_oras_client = MagicMock()
        mock_oras_client.push.return_value = mock_response

        exception_recorded: list[Exception] = []
        status_set: list[Any] = []

        from contextlib import contextmanager

        from opentelemetry.trace import Status, StatusCode

        @contextmanager
        def mock_create_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
            mock_span = MagicMock()
            mock_span.set_attribute = MagicMock()

            def capture_status(status: Status) -> None:
                status_set.append(status)

            def capture_exception(exc: Exception) -> None:
                exception_recorded.append(exc)

            mock_span.set_status = capture_status
            mock_span.record_exception = capture_exception

            # Mimic the real create_span behavior: catch exceptions, record, re-raise
            try:
                yield mock_span
            except Exception as e:
                mock_span.set_status(Status(StatusCode.ERROR, str(e)))
                mock_span.record_exception(e)
                raise

        original_metrics = oci_client.metrics

        with (
            patch.object(oci_client, "tag_exists", return_value=False),
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras_client),
            patch.object(original_metrics, "create_span", side_effect=mock_create_span),
        ):
            with pytest.raises(RegistryUnavailableError):
                oci_client.push(sample_compiled_artifacts, tag="v1.0.0")

        # Verify exception was recorded in span
        assert len(exception_recorded) == 1
        assert isinstance(exception_recorded[0], RegistryUnavailableError)

        # Verify span status was set to ERROR
        assert len(status_set) == 1
        assert status_set[0].status_code == StatusCode.ERROR


class TestOCIClientPullOTelInstrumentation:
    """Tests for OpenTelemetry instrumentation in pull operations.

    Task: T028
    Requirements: FR-031, FR-032, FR-034
    """

    @pytest.mark.requirement("8A-FR-031")
    def test_pull_creates_span_with_correct_name(
        self,
        tmp_path: Path,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test pull() creates a span named 'floe.oci.pull'.

        FR-031: System MUST emit OpenTelemetry spans for all operations.
        """
        import json

        from floe_core.oci.metrics import OCIMetrics

        # Setup artifacts
        artifacts_json = json.dumps(
            sample_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        # Track span creation
        span_created: list[dict[str, Any]] = []

        from contextlib import contextmanager

        @contextmanager
        def mock_create_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
            span_created.append({"name": name, "attributes": attributes or {}})
            mock_span = MagicMock()
            mock_span.set_attribute = MagicMock()
            mock_span.set_status = MagicMock()
            mock_span.record_exception = MagicMock()
            yield mock_span

        original_metrics = oci_client.metrics

        with (
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras),
            patch.object(original_metrics, "create_span", side_effect=mock_create_span),
        ):
            oci_client.pull(tag="v1.0.0")

        # Verify span was created with correct name
        assert len(span_created) == 1
        assert span_created[0]["name"] == OCIMetrics.SPAN_PULL

    @pytest.mark.requirement("8A-FR-031")
    def test_pull_span_includes_required_attributes(
        self,
        tmp_path: Path,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test pull span includes registry, tag, and operation attributes.

        FR-031: Spans MUST include registry, tag, and operation type.
        """
        import json

        # Setup artifacts
        artifacts_json = json.dumps(
            sample_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        # Track span attributes
        span_attributes: dict[str, Any] = {}

        from contextlib import contextmanager

        @contextmanager
        def mock_create_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
            span_attributes.update(attributes or {})
            mock_span = MagicMock()
            mock_span.set_attribute = lambda k, v: span_attributes.update({k: v})
            mock_span.set_status = MagicMock()
            mock_span.record_exception = MagicMock()
            yield mock_span

        original_metrics = oci_client.metrics

        with (
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras),
            patch.object(original_metrics, "create_span", side_effect=mock_create_span),
        ):
            oci_client.pull(tag="v1.0.0")

        # Verify required attributes
        assert "oci.registry" in span_attributes
        assert span_attributes["oci.registry"] == "harbor.example.com"
        assert "oci.tag" in span_attributes
        assert span_attributes["oci.tag"] == "v1.0.0"
        assert "oci.operation" in span_attributes
        assert span_attributes["oci.operation"] == "pull"

    @pytest.mark.requirement("8A-FR-034")
    def test_pull_records_duration_metric(
        self,
        tmp_path: Path,
        oci_client: OCIClient,
        sample_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Test pull() records operation duration in histogram.

        FR-034: System MUST emit operation duration metrics.
        """
        import json

        # Setup artifacts
        artifacts_json = json.dumps(
            sample_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        # Track duration recording
        duration_recorded: list[tuple[str, str, float]] = []

        def mock_record_duration(
            operation: str, registry: str, duration: float, **kwargs: Any
        ) -> None:
            duration_recorded.append((operation, registry, duration))

        original_metrics = oci_client.metrics

        from contextlib import contextmanager

        @contextmanager
        def mock_create_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
            mock_span = MagicMock()
            mock_span.set_attribute = MagicMock()
            mock_span.set_status = MagicMock()
            mock_span.record_exception = MagicMock()
            yield mock_span

        with (
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras),
            patch.object(original_metrics, "record_duration", side_effect=mock_record_duration),
            patch.object(original_metrics, "create_span", side_effect=mock_create_span),
        ):
            oci_client.pull(tag="v1.0.0")

        # Verify duration was recorded for pull operation
        assert len(duration_recorded) == 1
        operation, registry, duration = duration_recorded[0]
        assert operation == "pull"
        assert "harbor" in registry
        assert duration >= 0  # Duration should be non-negative

    @pytest.mark.requirement("8A-FR-032")
    def test_pull_records_cache_hit_metric(
        self,
        tmp_path: Path,
        sample_compiled_artifacts: CompiledArtifacts,
        mock_auth_provider: MagicMock,
    ) -> None:
        """Test pull() records cache hit metric when artifact is cached.

        FR-032: System MUST emit cache operation metrics (hit/miss).
        """
        import hashlib
        import json

        from floe_core.oci.cache import CacheManager

        # Create cache with artifact
        cache_config = CacheConfig(enabled=True, path=tmp_path / "cache")
        cache_manager = CacheManager(cache_config)

        # Store artifact in cache
        artifacts_json = json.dumps(
            sample_compiled_artifacts.model_dump(mode="json", by_alias=True)
        ).encode()
        digest = f"sha256:{hashlib.sha256(artifacts_json).hexdigest()}"
        cache_manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe/artifacts",
            content=artifacts_json,
        )

        # Create client with cache
        registry_config = RegistryConfig(
            uri="oci://harbor.example.com/floe/artifacts",
            auth=RegistryAuth(type=AuthType.AWS_IRSA),
            cache=CacheConfig(enabled=True, path=tmp_path / "cache"),
        )
        client = OCIClient(
            registry_config,
            auth_provider=mock_auth_provider,
            cache_manager=cache_manager,
        )

        # Track cache operation recording
        cache_ops_recorded: list[str] = []

        def mock_record_cache_operation(operation: str, **_kwargs: Any) -> None:
            cache_ops_recorded.append(operation)

        original_metrics = client.metrics

        from contextlib import contextmanager

        @contextmanager
        def mock_create_span(_name: str, _attributes: dict[str, Any] | None = None) -> Any:
            mock_span = MagicMock()
            mock_span.set_attribute = MagicMock()
            mock_span.set_status = MagicMock()
            mock_span.record_exception = MagicMock()
            yield mock_span

        with (
            patch.object(
                original_metrics,
                "record_cache_operation",
                side_effect=mock_record_cache_operation,
            ),
            patch.object(original_metrics, "create_span", side_effect=mock_create_span),
        ):
            client.pull(tag="v1.0.0")

        # Verify cache hit was recorded
        assert "hit" in cache_ops_recorded

    @pytest.mark.requirement("8A-FR-032")
    def test_pull_records_cache_miss_metric(
        self,
        tmp_path: Path,
        sample_compiled_artifacts: CompiledArtifacts,
        mock_auth_provider: MagicMock,
    ) -> None:
        """Test pull() records cache miss metric when artifact is not cached.

        FR-032: System MUST emit cache operation metrics (hit/miss).
        """
        import json

        from floe_core.oci.cache import CacheManager

        # Setup artifacts for ORAS pull
        artifacts_json = json.dumps(
            sample_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        # Create cache (empty - will be a miss)
        cache_config = CacheConfig(enabled=True, path=tmp_path / "cache")
        cache_manager = CacheManager(cache_config)

        # Create client with cache enabled
        registry_config = RegistryConfig(
            uri="oci://harbor.example.com/floe/artifacts",
            auth=RegistryAuth(type=AuthType.AWS_IRSA),
            cache=CacheConfig(enabled=True, path=tmp_path / "cache"),
        )
        client = OCIClient(
            registry_config,
            auth_provider=mock_auth_provider,
            cache_manager=cache_manager,
        )

        # Track cache operation recording
        cache_ops_recorded: list[str] = []

        def mock_record_cache_operation(operation: str, **_kwargs: Any) -> None:
            cache_ops_recorded.append(operation)

        original_metrics = client.metrics

        from contextlib import contextmanager

        @contextmanager
        def mock_create_span(_name: str, _attributes: dict[str, Any] | None = None) -> Any:
            mock_span = MagicMock()
            mock_span.set_attribute = MagicMock()
            mock_span.set_status = MagicMock()
            mock_span.record_exception = MagicMock()
            yield mock_span

        with (
            patch.object(client, "_create_oras_client", return_value=mock_oras),
            patch.object(
                original_metrics,
                "record_cache_operation",
                side_effect=mock_record_cache_operation,
            ),
            patch.object(original_metrics, "create_span", side_effect=mock_create_span),
        ):
            client.pull(tag="v1.0.0")

        # Verify cache miss was recorded
        assert "miss" in cache_ops_recorded


# =============================================================================
# Inspect Operation Tests (T031)
# =============================================================================


class TestOCIClientInspect:
    """Tests for OCIClient.inspect() operation.

    Tests metadata retrieval without downloading blob content.
    TDD: Write tests first, implementation comes in T032.

    Task: T031
    Requirements: FR-003
    """

    @pytest.fixture
    def mock_manifest_response(self) -> dict[str, Any]:
        """Create a mock OCI manifest response."""
        return {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "artifactType": "application/vnd.floe.compiled-artifacts.v1+json",
            "config": {
                "mediaType": "application/vnd.oci.empty.v1+json",
                "digest": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
                "size": 2,
            },
            "layers": [
                {
                    "mediaType": "application/vnd.floe.compiled-artifacts.v1+json",
                    "digest": TEST_LAYER_DIGEST,
                    "size": 12345,
                    "annotations": {
                        "org.opencontainers.image.created": "2026-01-19T12:00:00Z",
                        "io.floe.product.name": "test-product",
                        "io.floe.product.version": "1.0.0",
                    },
                }
            ],
            "annotations": {
                "org.opencontainers.image.created": "2026-01-19T12:00:00Z",
                "io.floe.product.name": "test-product",
                "io.floe.product.version": "1.0.0",
            },
        }

    @pytest.mark.requirement("8A-FR-003")
    def test_inspect_returns_artifact_manifest(
        self,
        oci_client: OCIClient,
        mock_manifest_response: dict[str, Any],
    ) -> None:
        """Test inspect returns ArtifactManifest without downloading content.

        Verifies:
        - inspect() returns ArtifactManifest
        - Manifest contains correct digest, type, and size
        - No blob content is downloaded (only manifest)
        """
        from floe_core.schemas.oci import ArtifactManifest

        # Mock ORAS client to return manifest without pull
        mock_oras = MagicMock()
        # Mock get_manifest method that returns manifest dict
        mock_oras.get_manifest.return_value = mock_manifest_response

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            manifest = oci_client.inspect(tag="v1.0.0")

        # Verify return type
        assert isinstance(manifest, ArtifactManifest)

        # Verify manifest properties
        assert manifest.artifact_type == "application/vnd.floe.compiled-artifacts.v1+json"
        assert len(manifest.layers) == 1
        assert manifest.layers[0].size == 12345

        # Verify ORAS was called with manifest request, not pull
        mock_oras.get_manifest.assert_called_once()
        # Should NOT call pull (which downloads blobs)
        mock_oras.pull.assert_not_called()

    @pytest.mark.requirement("8A-FR-003")
    def test_inspect_not_found_raises_error(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Test inspect raises ArtifactNotFoundError for non-existent tags.

        Verifies:
        - ArtifactNotFoundError raised for missing tag
        - Error contains tag and registry info
        """
        # Mock ORAS client to raise 404-equivalent error
        mock_oras = MagicMock()
        mock_oras.get_manifest.side_effect = Exception("MANIFEST_UNKNOWN: manifest unknown")

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            with pytest.raises(ArtifactNotFoundError) as exc_info:
                oci_client.inspect(tag="nonexistent-tag")

        # Verify error contains context
        assert "nonexistent-tag" in str(exc_info.value)

    @pytest.mark.requirement("8A-FR-003")
    def test_inspect_returns_manifest_with_annotations(
        self,
        oci_client: OCIClient,
        mock_manifest_response: dict[str, Any],
    ) -> None:
        """Test inspect returns manifest with annotations.

        Verifies:
        - Product name and version annotations extracted
        - Created timestamp included
        """
        mock_oras = MagicMock()
        mock_oras.get_manifest.return_value = mock_manifest_response

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            manifest = oci_client.inspect(tag="v1.0.0")

        # Verify annotations are accessible
        assert manifest.annotations is not None
        assert manifest.annotations.get("io.floe.product.name") == "test-product"
        assert manifest.annotations.get("io.floe.product.version") == "1.0.0"

    @pytest.mark.requirement("8A-FR-003")
    def test_inspect_uses_otel_tracing(
        self,
        oci_client: OCIClient,
        mock_manifest_response: dict[str, Any],
    ) -> None:
        """Test inspect creates OTel span for observability.

        Verifies:
        - Span created with operation name
        - Span includes tag attribute
        """
        from contextlib import contextmanager

        mock_oras = MagicMock()
        mock_oras.get_manifest.return_value = mock_manifest_response

        span_created = False
        span_attributes: dict[str, Any] = {}

        @contextmanager
        def mock_create_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
            nonlocal span_created, span_attributes
            span_created = True
            if attributes:
                span_attributes.update(attributes)
            mock_span = MagicMock()

            def set_attr(k: str, v: Any) -> None:
                span_attributes[k] = v

            mock_span.set_attribute = set_attr
            mock_span.set_status = MagicMock()
            yield mock_span

        with (
            patch.object(oci_client, "_create_oras_client", return_value=mock_oras),
            patch.object(oci_client.metrics, "create_span", side_effect=mock_create_span),
        ):
            oci_client.inspect(tag="v1.0.0")

        assert span_created, "Expected OTel span to be created"
        assert span_attributes.get("oci.tag") == "v1.0.0"
