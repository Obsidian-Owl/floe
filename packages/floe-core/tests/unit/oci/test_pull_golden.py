"""Golden tests for pull() behavior preservation.

This test file captures the exact output of pull-related functions to enable
safe refactoring. If behavior changes after refactoring, these tests will fail.

Task: T020
User Story: US3 - Reduce Code Complexity
Requirements: FR-011

Usage:
    # Run tests normally
    pytest packages/floe-core/tests/unit/oci/test_pull_golden.py -v

    # Update golden fixtures (after intentional behavior changes)
    UPDATE_GOLDEN=1 pytest packages/floe-core/tests/unit/oci/test_pull_golden.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from floe_core.oci.client import OCIClient
from floe_core.oci.errors import ArtifactNotFoundError
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
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION
from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig


# Determine if we should update fixtures
UPDATE_GOLDEN = os.environ.get("UPDATE_GOLDEN", "0") == "1"

# Golden fixtures directory
# Path: packages/floe-core/tests/unit/oci/test_pull_golden.py
# oci -> unit -> tests -> floe-core -> packages -> floe (6 parents)
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent.parent
    / "testing"
    / "fixtures"
    / "golden"
    / "oci_pull"
)


def _save_golden_fixture(
    fixture_path: Path, name: str, output: Any, function_name: str = ""
) -> None:
    """Save output as a golden fixture."""
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    output_json = json.dumps(output, sort_keys=True, default=str)
    checksum = hashlib.sha256(output_json.encode()).hexdigest()[:16]

    data = {
        "name": name,
        "function_name": function_name,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "checksum": checksum,
        "output": output,
    }
    fixture_path.write_text(json.dumps(data, indent=2, default=str))


def _normalize_for_comparison(data: Any) -> Any:
    """Remove timestamp fields that change between runs."""
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            # Skip timestamp fields that change between runs
            if key in ("compiled_at", "captured_at", "timestamp", "generated_at"):
                continue
            result[key] = _normalize_for_comparison(value)
        return result
    elif isinstance(data, list):
        normalized = [_normalize_for_comparison(item) for item in data]
        # Sort if all items are strings (order may not be deterministic)
        if all(isinstance(x, str) for x in normalized):
            return sorted(normalized)
        return normalized
    return data


def _assert_golden_match(
    actual: Any, fixture_path: Path, *, update: bool = False
) -> None:
    """Assert that actual output matches the golden fixture."""
    if update:
        _save_golden_fixture(fixture_path, fixture_path.stem, actual)
        return

    if not fixture_path.exists():
        pytest.fail(
            f"Golden fixture not found: {fixture_path}\n"
            f"Run with UPDATE_GOLDEN=1 to create it."
        )

    data = json.loads(fixture_path.read_text())
    expected = data["output"]

    # Normalize both for comparison (remove timestamps)
    actual_normalized = _normalize_for_comparison(actual)
    expected_normalized = _normalize_for_comparison(expected)

    if actual_normalized != expected_normalized:
        actual_json = json.dumps(
            actual_normalized, indent=2, sort_keys=True, default=str
        )
        expected_json = json.dumps(
            expected_normalized, indent=2, sort_keys=True, default=str
        )

        pytest.fail(
            f"Golden test failed: output does not match fixture\n"
            f"Fixture: {fixture_path}\n"
            f"\nExpected:\n{expected_json}\n\nActual:\n{actual_json}"
        )


# =============================================================================
# Test Fixtures - Stable, deterministic test data
# =============================================================================

# Fixed timestamp for deterministic testing
FIXED_TIMESTAMP = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def stable_telemetry_config() -> TelemetryConfig:
    """Create a stable TelemetryConfig for golden tests."""
    return TelemetryConfig(
        enabled=True,
        resource_attributes=ResourceAttributes(
            service_name="golden-test-pipeline",
            service_version="1.0.0",
            deployment_environment="dev",  # Must be dev/staging/prod
            floe_namespace="golden",
            floe_product_name="golden-product",
            floe_product_version="1.0.0",
            floe_mode="dev",  # Must be dev/staging/prod
        ),
    )


@pytest.fixture
def stable_observability_config(
    stable_telemetry_config: TelemetryConfig,
) -> ObservabilityConfig:
    """Create a stable ObservabilityConfig for golden tests."""
    return ObservabilityConfig(
        telemetry=stable_telemetry_config,
        lineage=True,
        lineage_namespace="golden-namespace",
    )


@pytest.fixture
def stable_compilation_metadata() -> CompilationMetadata:
    """Create a stable CompilationMetadata for golden tests."""
    return CompilationMetadata(
        compiled_at=FIXED_TIMESTAMP,
        floe_version=COMPILED_ARTIFACTS_VERSION,
        source_hash="sha256:golden123abc",
        product_name="golden-product",
        product_version="1.0.0",
    )


@pytest.fixture
def stable_product_identity() -> ProductIdentity:
    """Create a stable ProductIdentity for golden tests."""
    return ProductIdentity(
        product_id="golden.test_product",
        domain="golden",
        repository="github.com/golden/test",
    )


@pytest.fixture
def stable_resolved_plugins() -> ResolvedPlugins:
    """Create stable ResolvedPlugins for golden tests."""
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0"),
        orchestrator=PluginRef(type="dagster", version="1.5.0"),
    )


@pytest.fixture
def stable_resolved_transforms() -> ResolvedTransforms:
    """Create stable ResolvedTransforms for golden tests."""
    return ResolvedTransforms(
        models=[
            ResolvedModel(name="stg_golden_customers", compute="duckdb"),
            ResolvedModel(name="fct_golden_orders", compute="duckdb"),
        ],
        default_compute="duckdb",
    )


@pytest.fixture
def stable_compiled_artifacts(
    stable_compilation_metadata: CompilationMetadata,
    stable_product_identity: ProductIdentity,
    stable_observability_config: ObservabilityConfig,
    stable_resolved_plugins: ResolvedPlugins,
    stable_resolved_transforms: ResolvedTransforms,
) -> CompiledArtifacts:
    """Create a stable CompiledArtifacts for golden tests."""
    return CompiledArtifacts(
        version=COMPILED_ARTIFACTS_VERSION,
        metadata=stable_compilation_metadata,
        identity=stable_product_identity,
        mode="simple",
        inheritance_chain=[],
        observability=stable_observability_config,
        plugins=stable_resolved_plugins,
        transforms=stable_resolved_transforms,
        dbt_profiles={
            "golden_profile": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": "/tmp/golden.duckdb",
                    }
                },
            }
        },
    )


@pytest.fixture
def stable_registry_config() -> RegistryConfig:
    """Create a stable RegistryConfig for golden tests."""
    return RegistryConfig(
        uri="oci://harbor.golden.com/floe-platform",
        auth=RegistryAuth(type=AuthType.AWS_IRSA),
        tls_verify=True,
        cache=CacheConfig(enabled=False),
    )


@pytest.fixture
def mock_auth_provider() -> MagicMock:
    """Create a mock AuthProvider for golden tests."""
    from floe_core.oci.auth import Credentials

    provider = MagicMock()
    provider.get_credentials.return_value = Credentials(
        username="golden-user",
        password="golden-password",
        expires_at=FIXED_TIMESTAMP,
    )
    provider.refresh_if_needed.return_value = False
    return provider


@pytest.fixture
def oci_client(
    stable_registry_config: RegistryConfig,
    mock_auth_provider: MagicMock,
) -> OCIClient:
    """Create an OCIClient with mocked dependencies for golden tests."""
    return OCIClient(
        registry_config=stable_registry_config,
        auth_provider=mock_auth_provider,
    )


# =============================================================================
# Golden Test Classes
# =============================================================================


class TestPullGolden:
    """Golden tests for pull() operation behavior preservation.

    These tests capture the exact behavior of pull() before refactoring.
    After refactoring, run these tests to verify behavior is preserved.
    """

    @pytest.mark.requirement("FR-011")
    def test_pull_success_artifact_structure(
        self,
        tmp_path: Path,
        oci_client: OCIClient,
        stable_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Golden test: pull() returns correct artifact structure on success."""
        # Setup: Create temp file with serialized artifacts
        artifacts_json = json.dumps(
            stable_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        # Mock ORAS client using patch.object (like existing tests)
        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            result = oci_client.pull(tag="v1.0.0")

        # Convert to dict for golden comparison
        result_dict = result.model_dump()

        fixture_path = FIXTURES_DIR / "pull_success_artifact_structure.json"
        _assert_golden_match(result_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-011")
    def test_pull_artifact_metadata_preserved(
        self,
        tmp_path: Path,
        oci_client: OCIClient,
        stable_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Golden test: pull() preserves all metadata fields correctly."""
        artifacts_json = json.dumps(
            stable_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            result = oci_client.pull(tag="latest-dev")

        # Extract just metadata for focused comparison
        metadata_dict = {
            "version": result.version,
            "metadata": result.metadata.model_dump(),
            "identity": result.identity.model_dump(),
            "mode": result.mode,
        }

        fixture_path = FIXTURES_DIR / "pull_artifact_metadata.json"
        _assert_golden_match(metadata_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-011")
    def test_pull_plugins_config_preserved(
        self,
        tmp_path: Path,
        oci_client: OCIClient,
        stable_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Golden test: pull() preserves plugins configuration correctly."""
        artifacts_json = json.dumps(
            stable_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            result = oci_client.pull(tag="v1.0.0")

        # Extract plugins and dbt config
        plugins_dict = {
            "plugins": result.plugins.model_dump() if result.plugins else None,
            "dbt_profiles": result.dbt_profiles,
        }

        fixture_path = FIXTURES_DIR / "pull_plugins_config.json"
        _assert_golden_match(plugins_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-011")
    def test_pull_transforms_preserved(
        self,
        tmp_path: Path,
        oci_client: OCIClient,
        stable_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Golden test: pull() preserves transforms configuration correctly."""
        artifacts_json = json.dumps(
            stable_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            result = oci_client.pull(tag="v1.0.0")

        # Extract transforms
        transforms_dict = (
            result.transforms.model_dump() if result.transforms else None
        )

        fixture_path = FIXTURES_DIR / "pull_transforms.json"
        _assert_golden_match(transforms_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-011")
    def test_pull_observability_preserved(
        self,
        tmp_path: Path,
        oci_client: OCIClient,
        stable_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Golden test: pull() preserves observability configuration correctly."""
        artifacts_json = json.dumps(
            stable_compiled_artifacts.model_dump(mode="json", by_alias=True)
        )
        pull_dir = tmp_path / "pull"
        pull_dir.mkdir()
        (pull_dir / "compiled_artifacts.json").write_text(artifacts_json)

        mock_oras = MagicMock()
        mock_oras.pull.return_value = [str(pull_dir / "compiled_artifacts.json")]

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            result = oci_client.pull(tag="v1.0.0")

        # Extract observability config
        observability_dict = (
            result.observability.model_dump() if result.observability else None
        )

        fixture_path = FIXTURES_DIR / "pull_observability.json"
        _assert_golden_match(observability_dict, fixture_path, update=UPDATE_GOLDEN)


class TestPullErrorsGolden:
    """Golden tests for pull() error handling behavior preservation."""

    @pytest.mark.requirement("FR-011")
    def test_pull_not_found_error_structure(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Golden test: ArtifactNotFoundError has correct structure."""
        mock_oras = MagicMock()
        mock_oras.pull.side_effect = Exception("manifest unknown")

        with patch.object(oci_client, "_create_oras_client", return_value=mock_oras):
            with pytest.raises(ArtifactNotFoundError) as exc_info:
                oci_client.pull(tag="nonexistent-tag")

        # Capture error details
        error_dict = {
            "error_type": type(exc_info.value).__name__,
            "tag": exc_info.value.tag,
            "registry": exc_info.value.registry,
        }

        fixture_path = FIXTURES_DIR / "pull_not_found_error.json"
        _assert_golden_match(error_dict, fixture_path, update=UPDATE_GOLDEN)


class TestBuildTargetRefGolden:
    """Golden tests for _build_target_ref() helper method."""

    @pytest.mark.requirement("FR-011")
    def test_build_target_ref_with_oci_prefix(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Golden test: _build_target_ref removes oci:// prefix correctly."""
        # Test various tags
        refs = {
            "semver": oci_client._build_target_ref("v1.0.0"),
            "latest_dev": oci_client._build_target_ref("latest-dev"),
            "snapshot": oci_client._build_target_ref("snapshot-20260115"),
        }

        fixture_path = FIXTURES_DIR / "build_target_ref.json"
        _assert_golden_match(refs, fixture_path, update=UPDATE_GOLDEN)


class TestTagClassificationGolden:
    """Golden tests for tag immutability classification."""

    @pytest.mark.requirement("FR-011")
    def test_tag_classification_results(
        self,
        oci_client: OCIClient,
    ) -> None:
        """Golden test: Tag classification produces consistent results."""
        # Test a variety of tags
        tags_to_test = [
            # Semver tags (immutable)
            "v1.0.0",
            "v0.1.0",
            "1.0.0",
            "v1.0.0-alpha",
            "v1.0.0-beta.1",
            "v1.0.0+build123",
            # Mutable tags
            "latest",
            "latest-dev",
            "latest-staging",
            "dev",
            "dev-feature",
            "snapshot",
            "snapshot-20260115",
            # Edge cases
            "main",
            "feature-branch",
        ]

        results = {
            tag: {
                "is_immutable": oci_client.is_tag_immutable(tag),
            }
            for tag in tags_to_test
        }

        fixture_path = FIXTURES_DIR / "tag_classification.json"
        _assert_golden_match(results, fixture_path, update=UPDATE_GOLDEN)


__all__: list[str] = [
    "TestPullGolden",
    "TestPullErrorsGolden",
    "TestBuildTargetRefGolden",
    "TestTagClassificationGolden",
]
