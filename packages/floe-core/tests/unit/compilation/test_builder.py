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
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION


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
        assert artifacts.version == COMPILED_ARTIFACTS_VERSION

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

    @pytest.mark.requirement("2B-FR-001")
    def test_get_git_commit_returns_none_when_git_fails(self) -> None:
        """Test that get_git_commit returns None when git command fails."""
        from unittest.mock import patch

        from floe_core.compilation.builder import get_git_commit

        # Mock subprocess to simulate git failure
        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            result = get_git_commit()
            assert result is None


class TestComputeSourceHashEdgeCases:
    """Tests for compute_source_hash edge cases."""

    @pytest.mark.requirement("2B-FR-001")
    def test_compute_source_hash_with_manifest_path(self, tmp_path: Path) -> None:
        """Test compute_source_hash includes manifest content in hash."""
        from floe_core.compilation.builder import compute_source_hash

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("manifest content")

        hash_value = compute_source_hash(manifest_path=manifest_path)
        assert hash_value.startswith("sha256:")
        assert len(hash_value) == 71  # sha256: + 64 hex chars

    @pytest.mark.requirement("2B-FR-001")
    def test_compute_source_hash_with_both_paths(self, tmp_path: Path) -> None:
        """Test compute_source_hash includes both files in hash."""
        from floe_core.compilation.builder import compute_source_hash

        spec_path = tmp_path / "floe.yaml"
        manifest_path = tmp_path / "manifest.yaml"
        spec_path.write_text("spec content")
        manifest_path.write_text("manifest content")

        hash_both = compute_source_hash(spec_path=spec_path, manifest_path=manifest_path)
        hash_spec_only = compute_source_hash(spec_path=spec_path)
        hash_manifest_only = compute_source_hash(manifest_path=manifest_path)

        # All three should be different
        assert hash_both != hash_spec_only
        assert hash_both != hash_manifest_only
        assert hash_spec_only != hash_manifest_only

    @pytest.mark.requirement("2B-FR-001")
    def test_compute_source_hash_with_no_paths(self) -> None:
        """Test compute_source_hash with no paths returns empty hash."""
        from floe_core.compilation.builder import compute_source_hash

        hash_value = compute_source_hash()
        assert hash_value.startswith("sha256:")

    @pytest.mark.requirement("2B-FR-001")
    def test_compute_source_hash_with_nonexistent_path(self, tmp_path: Path) -> None:
        """Test compute_source_hash handles nonexistent paths."""
        from floe_core.compilation.builder import compute_source_hash

        nonexistent = tmp_path / "nonexistent.yaml"
        hash_value = compute_source_hash(spec_path=nonexistent)
        # Should return hash of empty content since file doesn't exist
        assert hash_value.startswith("sha256:")


class TestBuildArtifactsEdgeCases:
    """Tests for build_artifacts edge cases."""

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_with_source_paths(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
        tmp_path: Path,
    ) -> None:
        """Test build_artifacts computes source_hash when paths provided."""
        from floe_core.compilation.builder import build_artifacts

        spec_path = tmp_path / "floe.yaml"
        manifest_path = tmp_path / "manifest.yaml"
        spec_path.write_text("spec content")
        manifest_path.write_text("manifest content")

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
            spec_path=spec_path,
            manifest_path=manifest_path,
        )

        assert artifacts.metadata.source_hash.startswith("sha256:")
        assert len(artifacts.metadata.source_hash) == 71

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_has_observability_config(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that built artifacts include observability config."""
        from floe_core.compilation.builder import build_artifacts

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )

        assert artifacts.observability is not None
        assert artifacts.observability.telemetry.enabled is True
        assert artifacts.observability.lineage is True

    @pytest.mark.requirement("2B-FR-001")
    def test_build_artifacts_has_identity(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test that built artifacts include product identity."""
        from floe_core.compilation.builder import build_artifacts

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
        )

        assert artifacts.identity is not None
        assert "test_pipeline" in artifacts.identity.product_id
        assert artifacts.identity.domain == "default"

    @pytest.mark.requirement("3B-FR-001")
    def test_build_artifacts_with_enforcement_result(
        self,
        sample_spec: FloeSpec,
        sample_manifest: PlatformManifest,
        sample_plugins: ResolvedPlugins,
        sample_transforms: ResolvedTransforms,
        sample_dbt_profiles: dict[str, object],
    ) -> None:
        """Test build_artifacts includes enforcement_result when provided."""
        from floe_core.compilation.builder import build_artifacts
        from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

        enforcement_result = EnforcementResultSummary(
            passed=True,
            error_count=0,
            warning_count=0,
            policy_types_checked=["coverage", "naming"],
            models_validated=5,
            enforcement_level="strict",
        )

        artifacts = build_artifacts(
            sample_spec,
            sample_manifest,
            sample_plugins,
            sample_transforms,
            sample_dbt_profiles,
            enforcement_result=enforcement_result,
        )

        assert artifacts.enforcement_result is not None
        assert artifacts.enforcement_result.passed is True
        assert artifacts.enforcement_result.error_count == 0
