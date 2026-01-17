"""Unit tests for artifacts builder module.

TDD tests for the compilation artifacts builder. These tests define
the expected behavior before implementation.

Task: T027
Requirements: FR-001
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from floe_core.schemas.compiled_artifacts import (
    PluginRef,
    ResolvedModel,
    ResolvedPlugins,
    ResolvedTransforms,
)
from floe_core.schemas.floe_spec import FloeMetadata, FloeSpec, TransformSpec
from floe_core.schemas.manifest import PlatformManifest


@pytest.fixture
def sample_spec() -> FloeSpec:
    """Create a sample FloeSpec for testing."""
    return FloeSpec(
        api_version="floe.dev/v1",
        kind="FloeSpec",
        metadata=FloeMetadata(name="test-pipeline", version="1.0.0"),
        transforms=[TransformSpec(name="stg_customers")],
    )


@pytest.fixture
def sample_manifest() -> PlatformManifest:
    """Create a sample PlatformManifest for testing."""
    return PlatformManifest(
        api_version="floe.dev/v1",
        kind="Manifest",
        metadata={"name": "test-platform", "version": "1.0.0", "owner": "test@example.com"},
        plugins={
            "compute": {"type": "duckdb", "version": "0.9.0"},
            "orchestrator": {"type": "dagster", "version": "1.5.0"},
        },
    )


@pytest.fixture
def sample_plugins() -> ResolvedPlugins:
    """Create sample ResolvedPlugins for testing."""
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0"),
        orchestrator=PluginRef(type="dagster", version="1.5.0"),
    )


@pytest.fixture
def sample_transforms() -> ResolvedTransforms:
    """Create sample ResolvedTransforms for testing."""
    return ResolvedTransforms(
        models=[ResolvedModel(name="stg_customers", compute="duckdb")],
        default_compute="duckdb",
    )


@pytest.fixture
def sample_dbt_profiles() -> dict[str, object]:
    """Create sample dbt profiles for testing."""
    return {
        "default": {
            "target": "dev",
            "outputs": {
                "dev": {"type": "duckdb", "path": ":memory:"},
            },
        }
    }


class TestBuildArtifacts:
    """Tests for build_artifacts function."""

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_returns_compiled_artifacts(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that build_artifacts returns CompiledArtifacts."""
        from floe_core.compilation.builder import build_artifacts
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )
        assert isinstance(artifacts, CompiledArtifacts)

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_has_version_0_2_0(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that built artifacts have version 0.2.0."""
        from floe_core.compilation.builder import build_artifacts

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )
        assert artifacts.version == "0.2.0"

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_has_metadata(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that built artifacts have compilation metadata."""
        from floe_core.compilation.builder import build_artifacts

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )
        assert artifacts.metadata is not None
        assert artifacts.metadata.product_name == "test-pipeline"
        assert artifacts.metadata.product_version == "1.0.0"

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_metadata_has_timestamp(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that metadata includes compiled_at timestamp."""
        from floe_core.compilation.builder import build_artifacts

        before = datetime.now()
        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )
        after = datetime.now()

        assert artifacts.metadata.compiled_at is not None
        assert before <= artifacts.metadata.compiled_at <= after

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_metadata_has_floe_version(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that metadata includes floe_version."""
        from floe_core.compilation.builder import build_artifacts

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )
        assert artifacts.metadata.floe_version is not None
        # Version should be a non-empty string
        assert len(artifacts.metadata.floe_version) > 0

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_has_plugins(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that built artifacts include plugins."""
        from floe_core.compilation.builder import build_artifacts

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )
        assert artifacts.plugins is not None
        assert artifacts.plugins.compute.type == "duckdb"

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_has_transforms(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that built artifacts include transforms."""
        from floe_core.compilation.builder import build_artifacts

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )
        assert artifacts.transforms is not None
        assert len(artifacts.transforms.models) == 1

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_has_dbt_profiles(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that built artifacts include dbt_profiles."""
        from floe_core.compilation.builder import build_artifacts

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )
        assert artifacts.dbt_profiles is not None
        assert "default" in artifacts.dbt_profiles


class TestComputeSourceHash:
    """Tests for compute_source_hash function."""

    @pytest.mark.requirement("2B-FR-001")
    def test_compute_source_hash_returns_string(self, tmp_path: Path) -> None:
        """Test that compute_source_hash returns a string."""
        from floe_core.compilation.builder import compute_source_hash

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("test content")

        hash_value = compute_source_hash(spec_path=spec_path)
        assert isinstance(hash_value, str)

    @pytest.mark.requirement("2B-FR-001")
    def test_compute_source_hash_has_sha256_prefix(self, tmp_path: Path) -> None:
        """Test that hash is prefixed with 'sha256:'."""
        from floe_core.compilation.builder import compute_source_hash

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("test content")

        hash_value = compute_source_hash(spec_path=spec_path)
        assert hash_value.startswith("sha256:")

    @pytest.mark.requirement("2B-FR-001")
    def test_compute_source_hash_deterministic(self, tmp_path: Path) -> None:
        """Test that same content produces same hash."""
        from floe_core.compilation.builder import compute_source_hash

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("test content")

        hash1 = compute_source_hash(spec_path=spec_path)
        hash2 = compute_source_hash(spec_path=spec_path)
        assert hash1 == hash2

    @pytest.mark.requirement("2B-FR-001")
    def test_compute_source_hash_different_for_different_content(self, tmp_path: Path) -> None:
        """Test that different content produces different hash."""
        from floe_core.compilation.builder import compute_source_hash

        spec_path1 = tmp_path / "floe1.yaml"
        spec_path2 = tmp_path / "floe2.yaml"
        spec_path1.write_text("content 1")
        spec_path2.write_text("content 2")

        hash1 = compute_source_hash(spec_path=spec_path1)
        hash2 = compute_source_hash(spec_path=spec_path2)
        assert hash1 != hash2


class TestGetGitCommit:
    """Tests for get_git_commit function."""

    @pytest.mark.requirement("2B-FR-001")
    def test_get_git_commit_returns_string_or_none(self) -> None:
        """Test that get_git_commit returns str or None."""
        from floe_core.compilation.builder import get_git_commit

        result = get_git_commit()
        assert result is None or isinstance(result, str)

    @pytest.mark.requirement("2B-FR-001")
    def test_get_git_commit_in_repo_returns_sha(self) -> None:
        """Test that get_git_commit returns SHA in git repository."""
        from floe_core.compilation.builder import get_git_commit

        # This test runs in the floe repo, so should return a commit
        result = get_git_commit()
        # In a git repo, should be a 40-char hex string
        if result is not None:
            assert len(result) == 40
            assert all(c in "0123456789abcdef" for c in result)
