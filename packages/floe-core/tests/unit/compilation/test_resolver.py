"""Unit tests for plugin resolver module.

TDD tests for the compilation plugin resolver. These tests define
the expected behavior before implementation.

Task: T026
Requirements: FR-008
"""

from __future__ import annotations

import pytest

from floe_core.schemas.floe_spec import FloeMetadata, FloeSpec, TransformSpec
from floe_core.schemas.manifest import PlatformManifest


@pytest.fixture
def simple_manifest() -> PlatformManifest:
    """Create a simple 2-tier manifest for testing."""
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
def manifest_with_defaults() -> PlatformManifest:
    """Create a manifest with default_compute setting."""
    return PlatformManifest(
        api_version="floe.dev/v1",
        kind="Manifest",
        metadata={"name": "test-platform", "version": "1.0.0", "owner": "test@example.com"},
        plugins={
            "compute": {"type": "duckdb", "version": "0.9.0"},
            "orchestrator": {"type": "dagster", "version": "1.5.0"},
        },
        defaults={"compute": "duckdb"},
    )


@pytest.fixture
def simple_floe_spec() -> FloeSpec:
    """Create a simple FloeSpec for testing."""
    return FloeSpec(
        api_version="floe.dev/v1",
        kind="FloeSpec",
        metadata=FloeMetadata(name="test-pipeline", version="1.0.0"),
        transforms=[
            TransformSpec(name="stg_customers"),
            TransformSpec(name="fct_orders"),
        ],
    )


@pytest.fixture
def floe_spec_with_compute_override() -> FloeSpec:
    """Create a FloeSpec with compute override on a transform."""
    return FloeSpec(
        api_version="floe.dev/v1",
        kind="FloeSpec",
        metadata=FloeMetadata(name="test-pipeline", version="1.0.0"),
        transforms=[
            TransformSpec(name="stg_customers"),  # Uses default
            TransformSpec(name="fct_orders", compute="snowflake"),  # Override
        ],
    )


class TestResolvePlugins:
    """Tests for resolve_plugins function."""

    @pytest.mark.requirement("2B-FR-008")
    def test_resolve_plugins_returns_resolved_plugins(self, simple_manifest: PlatformManifest) -> None:
        """Test that resolve_plugins returns ResolvedPlugins."""
        from floe_core.compilation.resolver import resolve_plugins
        from floe_core.schemas.compiled_artifacts import ResolvedPlugins

        plugins = resolve_plugins(simple_manifest)
        assert isinstance(plugins, ResolvedPlugins)

    @pytest.mark.requirement("2B-FR-008")
    def test_resolve_plugins_has_compute(self, simple_manifest: PlatformManifest) -> None:
        """Test that resolved plugins include compute."""
        from floe_core.compilation.resolver import resolve_plugins

        plugins = resolve_plugins(simple_manifest)
        assert plugins.compute is not None
        assert plugins.compute.type == "duckdb"
        assert plugins.compute.version == "0.9.0"

    @pytest.mark.requirement("2B-FR-008")
    def test_resolve_plugins_has_orchestrator(self, simple_manifest: PlatformManifest) -> None:
        """Test that resolved plugins include orchestrator."""
        from floe_core.compilation.resolver import resolve_plugins

        plugins = resolve_plugins(simple_manifest)
        assert plugins.orchestrator is not None
        assert plugins.orchestrator.type == "dagster"
        assert plugins.orchestrator.version == "1.5.0"

    @pytest.mark.requirement("2B-FR-008")
    def test_resolve_plugins_missing_compute_fails(self) -> None:
        """Test that missing compute plugin raises CompilationException."""
        from floe_core.compilation.errors import CompilationException
        from floe_core.compilation.resolver import resolve_plugins

        manifest_no_compute = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={"name": "test", "version": "1.0.0", "owner": "test"},
            plugins={"orchestrator": {"type": "dagster", "version": "1.5.0"}},
        )

        with pytest.raises(CompilationException) as exc_info:
            resolve_plugins(manifest_no_compute)
        assert exc_info.value.error.code == "E201"  # Plugin not found


class TestResolveManifestInheritance:
    """Tests for resolve_manifest_inheritance function."""

    @pytest.mark.requirement("2B-FR-008")
    def test_simple_manifest_returns_self(self, simple_manifest: PlatformManifest) -> None:
        """Test that simple manifest (no parent) returns itself."""
        from floe_core.compilation.resolver import resolve_manifest_inheritance

        resolved = resolve_manifest_inheritance(simple_manifest)
        assert resolved.metadata.name == simple_manifest.metadata.name

    @pytest.mark.requirement("2B-FR-008")
    def test_inheritance_returns_platform_manifest(self, simple_manifest: PlatformManifest) -> None:
        """Test that resolved inheritance returns PlatformManifest."""
        from floe_core.compilation.resolver import resolve_manifest_inheritance

        resolved = resolve_manifest_inheritance(simple_manifest)
        assert isinstance(resolved, PlatformManifest)


class TestResolveTransformCompute:
    """Tests for resolve_transform_compute function."""

    @pytest.mark.requirement("2B-FR-008")
    def test_resolve_returns_resolved_transforms(
        self,
        simple_floe_spec: FloeSpec,
        manifest_with_defaults: PlatformManifest,
    ) -> None:
        """Test that resolve_transform_compute returns ResolvedTransforms."""
        from floe_core.compilation.resolver import resolve_transform_compute
        from floe_core.schemas.compiled_artifacts import ResolvedTransforms

        transforms = resolve_transform_compute(simple_floe_spec, manifest_with_defaults)
        assert isinstance(transforms, ResolvedTransforms)

    @pytest.mark.requirement("2B-FR-008")
    def test_all_transforms_have_compute(
        self,
        simple_floe_spec: FloeSpec,
        manifest_with_defaults: PlatformManifest,
    ) -> None:
        """Test that all resolved transforms have compute (never None)."""
        from floe_core.compilation.resolver import resolve_transform_compute

        transforms = resolve_transform_compute(simple_floe_spec, manifest_with_defaults)
        for model in transforms.models:
            assert model.compute is not None
            assert len(model.compute) > 0

    @pytest.mark.requirement("2B-FR-008")
    def test_uses_default_compute_when_not_specified(
        self,
        simple_floe_spec: FloeSpec,
        manifest_with_defaults: PlatformManifest,
    ) -> None:
        """Test that transforms without compute use platform default."""
        from floe_core.compilation.resolver import resolve_transform_compute

        transforms = resolve_transform_compute(simple_floe_spec, manifest_with_defaults)
        # All transforms in simple_floe_spec have no compute override
        for model in transforms.models:
            assert model.compute == "duckdb"  # Platform default

    @pytest.mark.requirement("2B-FR-008")
    def test_respects_compute_override(
        self,
        floe_spec_with_compute_override: FloeSpec,
        manifest_with_defaults: PlatformManifest,
    ) -> None:
        """Test that per-model compute override is respected."""
        from floe_core.compilation.resolver import resolve_transform_compute

        transforms = resolve_transform_compute(floe_spec_with_compute_override, manifest_with_defaults)

        # Find models by name
        stg_customers = next(m for m in transforms.models if m.name == "stg_customers")
        fct_orders = next(m for m in transforms.models if m.name == "fct_orders")

        assert stg_customers.compute == "duckdb"  # Uses default
        assert fct_orders.compute == "snowflake"  # Override

    @pytest.mark.requirement("2B-FR-008")
    def test_default_compute_is_set(
        self,
        simple_floe_spec: FloeSpec,
        manifest_with_defaults: PlatformManifest,
    ) -> None:
        """Test that ResolvedTransforms has default_compute set."""
        from floe_core.compilation.resolver import resolve_transform_compute

        transforms = resolve_transform_compute(simple_floe_spec, manifest_with_defaults)
        assert transforms.default_compute == "duckdb"
