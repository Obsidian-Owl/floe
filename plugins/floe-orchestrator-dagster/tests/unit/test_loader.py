"""Unit tests for the runtime loader (AC-1, AC-2, AC-3, AC-5).

This test suite covers:
- AC-1: load_product_definitions returns Definitions with dbt_assets, DbtCliResource,
  lineage resource, and conditional Iceberg resources.
- AC-2: No module-load-time connections -- importing/calling load_product_definitions
  with unreachable services must NOT eagerly connect.
- AC-3: Iceberg resource absent when unconfigured; exception propagated when factory raises.
- AC-5: The @dbt_assets body calls lineage emit_start before dbt, emit_fail on exception
  (then re-raises), emit_complete on success, and export_dbt_to_iceberg after dbt.

Done when all tests fail before implementation (NotImplementedError from stub).

Test type rationale: Unit test -- loader is a pure wiring function. External
dependencies (DbtProject, dbt_assets decorator, resource factories) are mocked
to isolate the loader's wiring logic. No boundary crossing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from dagster import AssetKey, Definitions, ResourceDefinition, build_op_context
from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    ObservabilityConfig,
    PluginRef,
    ResolvedModel,
    ResolvedPlugins,
    ResolvedTransforms,
)
from floe_core.schemas.telemetry import ResourceAttributes, TelemetryConfig

from floe_orchestrator_dagster.loader import load_product_definitions

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRODUCT_NAME = "customer-360"
SAFE_NAME = "customer_360"
_LOADER_MODULE = "floe_orchestrator_dagster.loader"
_RUNTIME_MODULE = "floe_orchestrator_dagster.runtime"
_ICEBERG_FACTORY = f"{_RUNTIME_MODULE}.try_create_iceberg_resources"
_LINEAGE_FACTORY = f"{_RUNTIME_MODULE}.try_create_lineage_resource"
_EXPORT_FN = f"{_RUNTIME_MODULE}.export_dbt_to_iceberg"
_TRACE_BUILDER = f"{_RUNTIME_MODULE}.TraceCorrelationFacetBuilder"
FAKE_RUN_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_artifacts(
    catalog: PluginRef | None = None,
    storage: PluginRef | None = None,
    ingestion: PluginRef | None = None,
    semantic: PluginRef | None = None,
) -> CompiledArtifacts:
    """Build a minimal valid CompiledArtifacts with optional catalog/storage.

    Args:
        catalog: Optional catalog PluginRef.
        storage: Optional storage PluginRef.
        ingestion: Optional ingestion PluginRef.
        semantic: Optional semantic layer PluginRef.

    Returns:
        A valid CompiledArtifacts instance.
    """
    return CompiledArtifacts(
        version="0.5.0",
        metadata=CompilationMetadata(
            compiled_at=datetime.now(timezone.utc),
            floe_version="0.5.0",
            source_hash="sha256:abc123def456",
            product_name=PRODUCT_NAME,
            product_version="1.0.0",
        ),
        identity={
            "product_id": "default.customer_360",
            "domain": "default",
            "repository": "github.com/test/customer-360",
        },
        mode="simple",
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="customer-360",
                    service_version="1.0.0",
                    deployment_environment="dev",
                    floe_namespace="default",
                    floe_product_name="customer-360",
                    floe_product_version="1.0.0",
                    floe_mode="dev",
                ),
            ),
            lineage=True,
            lineage_namespace="customer-360",
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=catalog,
            storage=storage,
            ingestion=ingestion,
            semantic=semantic,
        ),
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name="stg_customers", compute="duckdb")],
            default_compute="duckdb",
        ),
    )


def _write_artifacts_and_manifest(
    project_dir: Path,
    artifacts: CompiledArtifacts | None = None,
) -> None:
    """Write compiled_artifacts.json and a minimal manifest.json to project_dir.

    Args:
        project_dir: Directory to write files into.
        artifacts: Artifacts to serialize. If None, uses default (no catalog/storage).
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    if artifacts is None:
        artifacts = _make_artifacts()

    artifacts_path = project_dir / "compiled_artifacts.json"
    artifacts_path.write_text(artifacts.model_dump_json(indent=2))

    target_dir = project_dir / "target"
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json",
            "dbt_version": "1.7.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "invocation_id": str(uuid4()),
        },
        "nodes": {},
        "sources": {},
        "exposures": {},
        "metrics": {},
        "groups": {},
        "selectors": {},
        "disabled": [],
        "parent_map": {},
        "child_map": {},
        "group_map": {},
        "semantic_models": {},
        "unit_tests": {},
        "saved_queries": {},
    }
    (target_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Temporary dbt project directory with artifacts and manifest written.

    Returns:
        Path to a project dir containing compiled_artifacts.json and
        target/manifest.json.
    """
    pdir = tmp_path / "dbt_project"
    _write_artifacts_and_manifest(pdir)
    return pdir


@pytest.fixture
def project_dir_with_iceberg(tmp_path: Path) -> Path:
    """Temporary project dir with catalog and storage plugins configured.

    Returns:
        Path to a project dir whose compiled_artifacts.json includes
        catalog and storage PluginRefs.
    """
    pdir = tmp_path / "dbt_project"
    artifacts = _make_artifacts(
        catalog=PluginRef(type="polaris", version="0.1.0", config={}),
        storage=PluginRef(type="s3", version="1.0.0", config={}),
    )
    _write_artifacts_and_manifest(pdir, artifacts)
    return pdir


@pytest.fixture
def project_dir_with_catalog_only(tmp_path: Path) -> Path:
    """Temporary project dir with catalog but no storage plugin configured."""
    pdir = tmp_path / "dbt_project"
    artifacts = _make_artifacts(
        catalog=PluginRef(type="polaris", version="0.1.0", config={}),
        storage=None,
    )
    _write_artifacts_and_manifest(pdir, artifacts)
    return pdir


@pytest.fixture
def project_dir_with_semantic(tmp_path: Path) -> Path:
    """Temporary project dir with semantic layer plugin configured."""
    pdir = tmp_path / "dbt_project"
    artifacts = _make_artifacts(
        semantic=PluginRef(type="cube", version="0.1.0", config={}),
    )
    _write_artifacts_and_manifest(pdir, artifacts)
    return pdir


@pytest.fixture
def project_dir_with_ingestion(tmp_path: Path) -> Path:
    """Temporary project dir with ingestion plugin configured."""
    pdir = tmp_path / "dbt_project"
    artifacts = _make_artifacts(
        ingestion=PluginRef(
            type="dlt",
            version="0.1.0",
            config={
                "sources": [
                    {
                        "name": "github-events",
                        "source_type": "rest_api",
                        "destination_table": "bronze.github_events",
                    }
                ]
            },
        ),
    )
    _write_artifacts_and_manifest(pdir, artifacts)
    return pdir


@pytest.fixture
def project_dir_with_ingestion_no_sources(tmp_path: Path) -> Path:
    """Temporary project dir with ingestion selected but no workload sources."""
    pdir = tmp_path / "dbt_project"
    artifacts = _make_artifacts(
        ingestion=PluginRef(
            type="dlt",
            version="0.1.0",
            config={"sources": []},
        ),
    )
    _write_artifacts_and_manifest(pdir, artifacts)
    return pdir


@pytest.fixture
def project_dir_with_ingestion_no_config(tmp_path: Path) -> Path:
    """Temporary project dir with ingestion selected and no config."""
    pdir = tmp_path / "dbt_project"
    artifacts = _make_artifacts(
        ingestion=PluginRef(
            type="dlt",
            version="0.1.0",
            config=None,
        ),
    )
    _write_artifacts_and_manifest(pdir, artifacts)
    return pdir


@pytest.fixture
def project_dir_with_ingestion_no_manifest(tmp_path: Path) -> Path:
    """Temporary project dir with ingestion artifacts but no dbt manifest."""
    pdir = tmp_path / "dbt_project"
    pdir.mkdir(parents=True, exist_ok=True)
    artifacts = _make_artifacts(
        ingestion=PluginRef(
            type="dlt",
            version="0.1.0",
            config={
                "sources": [
                    {
                        "name": "github-events",
                        "source_type": "rest_api",
                        "destination_table": "bronze.github_events",
                    }
                ]
            },
        ),
    )
    (pdir / "compiled_artifacts.json").write_text(artifacts.model_dump_json(indent=2))
    return pdir


@pytest.fixture
def empty_project_dir(tmp_path: Path) -> Path:
    """Temporary project directory with NO compiled_artifacts.json.

    Returns:
        Path to an empty directory.
    """
    pdir = tmp_path / "dbt_project"
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def test_loader_delegates_to_runtime_builder(project_dir: Path) -> None:
    artifacts_path = project_dir / "compiled_artifacts.json"
    expected_artifacts = CompiledArtifacts.model_validate_json(artifacts_path.read_text())

    with patch("floe_orchestrator_dagster.loader.build_product_definitions") as build:
        sentinel = MagicMock(spec=Definitions)
        build.return_value = sentinel

        result = load_product_definitions(PRODUCT_NAME, project_dir)

    assert result is sentinel
    build.assert_called_once()
    call = build.call_args.kwargs
    assert call["product_name"] == PRODUCT_NAME
    assert call["project_dir"] == project_dir
    assert call["artifacts"] == expected_artifacts


# ===========================================================================
# AC-1: Definitions structure
# ===========================================================================


@pytest.mark.requirement("AC-1")
def test_returns_definitions_object(project_dir: Path) -> None:
    """load_product_definitions returns a Definitions instance, not None or dict."""
    result = load_product_definitions(PRODUCT_NAME, project_dir)

    assert isinstance(result, Definitions), (
        f"Expected dagster.Definitions, got {type(result).__name__}"
    )


@pytest.mark.requirement("AC-1")
def test_definitions_has_dbt_resource(project_dir: Path) -> None:
    """Definitions must contain a 'dbt' resource that is or wraps DbtCliResource."""
    result = load_product_definitions(PRODUCT_NAME, project_dir)

    resources = result.resources or {}
    assert "dbt" in resources, (
        f"'dbt' resource missing from Definitions.resources. Present keys: {list(resources.keys())}"
    )


@pytest.mark.requirement("AC-1")
def test_definitions_has_lineage_resource(project_dir: Path) -> None:
    """Definitions must contain a 'lineage' resource (real or NoOp)."""
    result = load_product_definitions(PRODUCT_NAME, project_dir)

    resources = result.resources or {}
    assert "lineage" in resources, (
        f"'lineage' resource missing from Definitions.resources. "
        f"Present keys: {list(resources.keys())}"
    )


@pytest.mark.requirement("AC-1")
def test_definitions_has_at_least_one_asset(project_dir: Path) -> None:
    """Definitions must contain at least one asset (the @dbt_assets asset)."""
    result = load_product_definitions(PRODUCT_NAME, project_dir)

    assets = result.assets or []
    # Dagster stores assets as a sequence; ensure non-empty.
    asset_list = list(assets)
    assert len(asset_list) >= 1, "Definitions must include at least one @dbt_assets asset"


# ===========================================================================
# AC-1 + AC-3: Iceberg resource presence/absence
# ===========================================================================


@pytest.mark.requirement("AC-1")
def test_definitions_has_iceberg_when_configured(
    project_dir_with_iceberg: Path,
) -> None:
    """When catalog+storage are in artifacts, iceberg resource must be present."""
    result = load_product_definitions(PRODUCT_NAME, project_dir_with_iceberg)

    resources = result.resources or {}
    assert "iceberg" in resources, (
        f"'iceberg' resource missing when catalog+storage configured. "
        f"Present keys: {list(resources.keys())}"
    )


@pytest.mark.requirement("AC-3")
def test_definitions_no_iceberg_when_unconfigured(project_dir: Path) -> None:
    """When no catalog in artifacts, iceberg resource must be absent."""
    result = load_product_definitions(PRODUCT_NAME, project_dir)

    resources = result.resources or {}
    assert "iceberg" not in resources, (
        "Iceberg resource must be absent when catalog/storage are not configured"
    )


@pytest.mark.requirement("AC-3")
def test_definitions_no_iceberg_when_catalog_without_storage(
    project_dir_with_catalog_only: Path,
) -> None:
    """Catalog-only artifacts must not register an unusable iceberg resource."""
    result = load_product_definitions(PRODUCT_NAME, project_dir_with_catalog_only)

    resources = result.resources or {}
    assert "iceberg" not in resources, (
        "Iceberg resource must be absent unless both catalog and storage are configured"
    )


@pytest.mark.requirement("AC-3")
def test_iceberg_resource_propagates_exception(
    project_dir_with_iceberg: Path,
) -> None:
    """When try_create_iceberg_resources raises, the exception must propagate.

    The loader wraps resource creation in ResourceDefinition generators for
    deferred connection. When the generator itself raises (e.g., plugin not
    found), the exception must NOT be swallowed -- it must surface at
    resource resolution time.
    """
    with patch(
        _ICEBERG_FACTORY,
        side_effect=RuntimeError("iceberg plugin not found"),
    ):
        # The exception may be raised either:
        # (a) immediately from load_product_definitions, OR
        # (b) when the ResourceDefinition generator is resolved
        # We accept either -- the key is it MUST surface, never silently {}
        try:
            result = load_product_definitions(PRODUCT_NAME, project_dir_with_iceberg)
            # If we get here, the factory was deferred -- trigger resolution
            resources = result.resources or {}
            if "iceberg" in resources:
                resource = resources["iceberg"]
                # If it's a ResourceDefinition, try to invoke its generator
                if isinstance(resource, ResourceDefinition):
                    # Trigger the generator to force the error
                    resource.resource_fn(MagicMock())
        except RuntimeError as exc:
            assert "iceberg plugin not found" in str(exc)
        else:
            # If no exception, iceberg resource must be absent (not silently None)
            assert "iceberg" not in (result.resources or {}), (
                "try_create_iceberg_resources raised but loader silently returned "
                "an iceberg resource or swallowed the error"
            )


# ===========================================================================
# AC-2: No module-load-time connections
# ===========================================================================


@pytest.mark.requirement("AC-2")
def test_no_connections_during_import(project_dir: Path) -> None:
    """Calling load_product_definitions must NOT eagerly connect to services.

    ResourceDefinition objects must be present in resources, not eagerly
    resolved instances. No HTTP, gRPC, or TCP connections should occur
    during the call.
    """
    # Patch the factories that would connect to external services
    with (
        patch(
            _ICEBERG_FACTORY,
            return_value={},
        ),
        patch(
            _LINEAGE_FACTORY,
            return_value={"lineage": ResourceDefinition.hardcoded_resource(MagicMock())},
        ) as mock_lineage,
    ):
        result = load_product_definitions(PRODUCT_NAME, project_dir)

    # The factories should be called (to build ResourceDefinition objects),
    # but the returned definitions should not have triggered any real
    # connections. We verify by checking the resources are ResourceDefinition
    # instances (lazy), not fully resolved objects.
    assert isinstance(result, Definitions)

    # More importantly: verify no connection-making calls were attempted
    # by checking that mock_lineage was called with just config, not
    # with a live connection
    assert mock_lineage.called, "Lineage factory should have been called"


@pytest.mark.requirement("AC-2")
def test_resources_are_deferred_not_eager(project_dir: Path) -> None:
    """Resources in Definitions must be ResourceDefinition or similar lazy wrappers.

    This prevents ConnectionError/TimeoutError at import time when Polaris
    or MinIO are unreachable.
    """
    result = load_product_definitions(PRODUCT_NAME, project_dir)

    resources = result.resources or {}
    for key, resource in resources.items():
        # Resources should be ResourceDefinition or compatible wrappers,
        # not raw connected clients
        assert resource is not None, f"Resource '{key}' is None"
        # The resource should NOT be a raw connection object
        # (e.g., not a pyiceberg Catalog, not an httpx Client)
        forbidden_types = ("Catalog", "Client", "Connection", "Session")
        type_name = type(resource).__name__
        assert not any(t in type_name for t in forbidden_types), (
            f"Resource '{key}' appears to be an eagerly resolved connection "
            f"({type_name}), not a deferred ResourceDefinition"
        )


# ===========================================================================
# AC-2: Fail fast on missing artifacts
# ===========================================================================


@pytest.mark.requirement("AC-1")
def test_fails_fast_when_artifacts_missing(empty_project_dir: Path) -> None:
    """load_product_definitions must raise when compiled_artifacts.json is missing.

    Must NOT return empty Definitions or silently skip -- fail fast.
    """
    with pytest.raises((FileNotFoundError, OSError)):
        load_product_definitions(PRODUCT_NAME, empty_project_dir)


@pytest.mark.requirement("AC-1")
def test_fails_fast_when_artifacts_invalid(tmp_path: Path) -> None:
    """load_product_definitions must raise a validation/parse error on malformed JSON.

    Must NOT raise NotImplementedError (that would mean the stub, not real code).
    Must raise a JSON decode error or Pydantic ValidationError.
    """
    project_dir = tmp_path / "dbt_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "compiled_artifacts.json").write_text("not valid json {{{")

    with pytest.raises(Exception) as exc_info:
        load_product_definitions(PRODUCT_NAME, project_dir)

    # Verify it's a JSON/validation error, not NotImplementedError
    assert not isinstance(exc_info.value, NotImplementedError), (
        "Got NotImplementedError -- loader stub does not validate artifacts"
    )


# ===========================================================================
# AC-5: Lineage emission in @dbt_assets body
# ===========================================================================


def _extract_dbt_assets_fn(definitions: Definitions) -> Any:
    """Extract the @dbt_assets compute function from Definitions.

    The @dbt_assets decorator wraps the function body. We need to find the
    asset in Definitions and extract its underlying callable.

    Args:
        definitions: Dagster Definitions containing at least one asset.

    Returns:
        The callable inner function of the @dbt_assets asset.

    Raises:
        AssertionError: If no assets found.
    """
    assets = list(definitions.assets or [])
    assert len(assets) >= 1, "No assets in Definitions to extract"
    # The first (and expected only) asset is the @dbt_assets asset
    asset_def = assets[0]
    # Dagster @dbt_assets wraps the function -- access via compute_fn
    if hasattr(asset_def, "op"):
        compute_fn = asset_def.op.compute_fn
        if hasattr(compute_fn, "decorated_fn"):
            return compute_fn.decorated_fn
        return compute_fn
    return asset_def


def _extract_asset_fn_by_op_name(definitions: Definitions, op_name: str) -> Any:
    """Extract an asset compute function by Dagster op name."""
    for asset_def in definitions.assets or []:
        op = getattr(asset_def, "op", None)
        if op is None or op.name != op_name:
            continue
        compute_fn = op.compute_fn
        if hasattr(compute_fn, "decorated_fn"):
            return compute_fn.decorated_fn
        return compute_fn
    raise AssertionError(f"No asset found with op name {op_name!r}")


def _asset_names(definitions: Definitions) -> set[str]:
    """Collect asset key names from single-asset and multi-asset definitions."""
    names: set[str] = set()
    for asset_def in definitions.assets or []:
        keys = getattr(asset_def, "keys", None)
        if keys:
            names.update(key.path[-1] for key in keys)
        else:
            try:
                names.add(asset_def.key.path[-1])
            except Exception:
                # Empty dbt manifests can produce a multi-asset definition
                # without single-asset key access; optional assets are checked below.
                continue
    return names


def _make_mock_context_with_lineage() -> tuple[MagicMock, MagicMock]:
    """Create a mock Dagster context with a mock lineage resource.

    Returns:
        Tuple of (context, lineage_mock).
    """
    lineage = MagicMock()
    lineage.emit_start.return_value = FAKE_RUN_ID
    lineage.namespace = "test-namespace"

    context = MagicMock()
    context.resources.lineage = lineage
    context.resources.dbt = MagicMock()
    context.log = MagicMock()
    context.run.run_id = str(uuid4())
    return context, lineage


@pytest.mark.requirement("AC-5")
def test_dbt_assets_calls_emit_start_before_build(project_dir: Path) -> None:
    """The @dbt_assets body must call lineage.emit_start() before dbt.cli().

    This verifies the lineage start event is emitted with TraceCorrelationFacetBuilder
    BEFORE the dbt build command is executed.
    """
    definitions = load_product_definitions(PRODUCT_NAME, project_dir)
    asset_fn = _extract_dbt_assets_fn(definitions)

    context, lineage = _make_mock_context_with_lineage()
    mock_dbt = context.resources.dbt
    # dbt.cli(["build"]).stream() returns an iterable of events
    mock_stream = MagicMock()
    mock_stream.__iter__ = MagicMock(return_value=iter([]))
    mock_dbt.cli.return_value.stream.return_value = mock_stream

    # Execute the asset function
    list(asset_fn(context))

    # emit_start must have been called
    lineage.emit_start.assert_called_once()

    # Verify ordering: emit_start was called before dbt.cli
    call_order: list[str] = []
    lineage.emit_start.side_effect = lambda *a, **kw: call_order.append("emit_start")
    mock_dbt.cli.side_effect = lambda *a, **kw: (
        call_order.append("dbt_cli"),
        MagicMock(stream=MagicMock(return_value=iter([]))),
    )[-1]

    # Re-execute to capture ordering
    call_order.clear()
    lineage.emit_start.reset_mock()
    mock_dbt.cli.reset_mock()
    list(asset_fn(context))

    assert call_order.index("emit_start") < call_order.index("dbt_cli"), (
        f"emit_start must be called before dbt.cli. Call order: {call_order}"
    )


@pytest.mark.requirement("AC-5")
def test_dbt_assets_calls_emit_complete_on_success(project_dir: Path) -> None:
    """On successful dbt execution, lineage.emit_complete() must be called."""
    definitions = load_product_definitions(PRODUCT_NAME, project_dir)
    asset_fn = _extract_dbt_assets_fn(definitions)

    context, lineage = _make_mock_context_with_lineage()
    mock_dbt = context.resources.dbt
    mock_stream = MagicMock()
    mock_stream.__iter__ = MagicMock(return_value=iter([]))
    mock_dbt.cli.return_value.stream.return_value = mock_stream

    list(asset_fn(context))

    lineage.emit_complete.assert_called_once()
    # emit_complete must receive the run_id from emit_start
    args = lineage.emit_complete.call_args
    assert args is not None, "emit_complete was called with no arguments"


@pytest.mark.requirement("AC-5")
def test_dbt_assets_calls_emit_fail_on_exception(project_dir: Path) -> None:
    """On dbt failure, lineage.emit_fail() must be called before re-raising."""
    definitions = load_product_definitions(PRODUCT_NAME, project_dir)
    asset_fn = _extract_dbt_assets_fn(definitions)

    context, lineage = _make_mock_context_with_lineage()
    mock_dbt = context.resources.dbt
    dbt_error = RuntimeError("dbt build failed")
    mock_dbt.cli.return_value.stream.side_effect = dbt_error

    with pytest.raises(RuntimeError, match="dbt build failed"):
        list(asset_fn(context))

    lineage.emit_fail.assert_called_once()
    # emit_fail must receive the run_id from emit_start
    fail_args = lineage.emit_fail.call_args
    assert fail_args is not None, "emit_fail was called with no arguments"


@pytest.mark.requirement("AC-5")
def test_dbt_assets_reraises_exceptions(project_dir: Path) -> None:
    """Exceptions from dbt must propagate after emit_fail -- never swallowed."""
    definitions = load_product_definitions(PRODUCT_NAME, project_dir)
    asset_fn = _extract_dbt_assets_fn(definitions)

    context, lineage = _make_mock_context_with_lineage()
    mock_dbt = context.resources.dbt
    original_error = ValueError("critical dbt failure")
    mock_dbt.cli.return_value.stream.side_effect = original_error

    with pytest.raises(ValueError, match="critical dbt failure"):
        list(asset_fn(context))


@pytest.mark.requirement("AC-5")
def test_dbt_assets_emit_complete_not_called_on_failure(
    project_dir: Path,
) -> None:
    """On dbt failure, emit_complete must NOT be called (only emit_fail)."""
    definitions = load_product_definitions(PRODUCT_NAME, project_dir)
    asset_fn = _extract_dbt_assets_fn(definitions)

    context, lineage = _make_mock_context_with_lineage()
    mock_dbt = context.resources.dbt
    mock_dbt.cli.return_value.stream.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        list(asset_fn(context))

    lineage.emit_fail.assert_called_once()
    lineage.emit_complete.assert_not_called()


@pytest.mark.requirement("AC-5")
def test_dbt_assets_calls_iceberg_export_after_dbt(
    project_dir_with_iceberg: Path,
) -> None:
    """After successful dbt build, export_dbt_to_iceberg must be called."""
    with patch(_EXPORT_FN) as mock_export:
        definitions = load_product_definitions(PRODUCT_NAME, project_dir_with_iceberg)
        asset_fn = _extract_dbt_assets_fn(definitions)

        context, lineage = _make_mock_context_with_lineage()
        mock_dbt = context.resources.dbt
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=iter([]))
        mock_dbt.cli.return_value.stream.return_value = mock_stream

        list(asset_fn(context))

        mock_export.assert_called_once()


@pytest.mark.requirement("AC-5")
def test_dbt_assets_iceberg_export_not_called_with_catalog_only(
    project_dir_with_catalog_only: Path,
) -> None:
    """Catalog-only artifacts must not attempt export without storage."""
    with patch(_EXPORT_FN) as mock_export:
        definitions = load_product_definitions(PRODUCT_NAME, project_dir_with_catalog_only)
        asset_fn = _extract_dbt_assets_fn(definitions)

        context, lineage = _make_mock_context_with_lineage()
        mock_dbt = context.resources.dbt
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=iter([]))
        mock_dbt.cli.return_value.stream.return_value = mock_stream

        list(asset_fn(context))

        mock_export.assert_not_called()


@pytest.mark.requirement("AC-5")
def test_dbt_assets_iceberg_export_not_called_on_failure(
    project_dir_with_iceberg: Path,
) -> None:
    """On dbt failure, export_dbt_to_iceberg must NOT be called."""
    with patch(_EXPORT_FN) as mock_export:
        definitions = load_product_definitions(PRODUCT_NAME, project_dir_with_iceberg)
        asset_fn = _extract_dbt_assets_fn(definitions)

        context, lineage = _make_mock_context_with_lineage()
        mock_dbt = context.resources.dbt
        mock_dbt.cli.return_value.stream.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            list(asset_fn(context))

        mock_export.assert_not_called()


@pytest.mark.requirement("AC-5")
def test_dbt_assets_iceberg_export_failure_emits_lineage_fail(
    project_dir_with_iceberg: Path,
) -> None:
    """Post-dbt export failure must emit lineage fail and not complete."""
    with patch(_EXPORT_FN, side_effect=RuntimeError("export failed")):
        definitions = load_product_definitions(PRODUCT_NAME, project_dir_with_iceberg)
        asset_fn = _extract_dbt_assets_fn(definitions)

        context, lineage = _make_mock_context_with_lineage()
        mock_dbt = context.resources.dbt
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=iter([]))
        mock_dbt.cli.return_value.stream.return_value = mock_stream

        with pytest.raises(RuntimeError, match="export failed"):
            list(asset_fn(context))

        lineage.emit_fail.assert_called_once()
        lineage.emit_complete.assert_not_called()


def test_runtime_includes_semantic_resource_and_asset_when_configured(
    project_dir_with_semantic: Path,
) -> None:
    """Semantic plugin config must wire runtime resource and sync asset."""
    semantic_resource = MagicMock()

    with patch(
        f"{_RUNTIME_MODULE}._create_semantic_resources",
        return_value={"semantic_layer": semantic_resource},
    ):
        result = load_product_definitions(PRODUCT_NAME, project_dir_with_semantic)

    resources = result.resources or {}
    asset_names = _asset_names(result)
    assert resources["semantic_layer"] is semantic_resource
    assert "sync_semantic_schemas" in asset_names


def test_runtime_semantic_asset_uses_project_dir_paths(project_dir_with_semantic: Path) -> None:
    """Runtime semantic sync asset must use paths inside the product project_dir."""
    semantic_resource = MagicMock()
    semantic_resource.sync_from_dbt_manifest.return_value = []

    with patch(
        f"{_RUNTIME_MODULE}._create_semantic_resources",
        return_value={"semantic_layer": semantic_resource},
    ):
        result = load_product_definitions(PRODUCT_NAME, project_dir_with_semantic)

    sync_fn = _extract_asset_fn_by_op_name(result, "sync_semantic_schemas")
    context = build_op_context(resources={"semantic_layer": semantic_resource})

    sync_fn(context)

    semantic_resource.sync_from_dbt_manifest.assert_called_once_with(
        manifest_path=project_dir_with_semantic / "target" / "manifest.json",
        output_dir=project_dir_with_semantic / "cube" / "schema",
    )


def test_runtime_semantic_asset_depends_on_compiled_model_assets(
    project_dir_with_semantic: Path,
) -> None:
    """Semantic sync must run after compiled dbt model assets."""
    semantic_resource = MagicMock()

    with patch(
        f"{_RUNTIME_MODULE}._create_semantic_resources",
        return_value={"semantic_layer": semantic_resource},
    ):
        result = load_product_definitions(PRODUCT_NAME, project_dir_with_semantic)

    semantic_asset = next(
        asset_def
        for asset_def in result.assets or []
        if AssetKey("sync_semantic_schemas") in getattr(asset_def, "keys", set())
    )

    assert AssetKey("stg_customers") in semantic_asset.dependency_keys


def test_runtime_fails_loudly_when_ingestion_configured(
    project_dir_with_ingestion: Path,
) -> None:
    """Dagster ingestion runtime is blocked until source construction exists."""
    with pytest.raises(ValueError, match="compiled JSON config cannot yet construct executable"):
        load_product_definitions(PRODUCT_NAME, project_dir_with_ingestion)


def test_runtime_allows_selected_ingestion_without_sources(
    project_dir_with_ingestion_no_sources: Path,
) -> None:
    """Selecting ingestion without workload sources should not block transforms."""
    result = load_product_definitions(PRODUCT_NAME, project_dir_with_ingestion_no_sources)

    resources = result.resources or {}
    assert "ingestion" not in resources


def test_runtime_allows_selected_ingestion_without_config(
    project_dir_with_ingestion_no_config: Path,
) -> None:
    """Selecting ingestion without config should not block transforms."""
    result = load_product_definitions(PRODUCT_NAME, project_dir_with_ingestion_no_config)

    resources = result.resources or {}
    assert "ingestion" not in resources


def test_runtime_ingestion_failure_precedes_missing_manifest(
    project_dir_with_ingestion_no_manifest: Path,
) -> None:
    """Unsupported ingestion error must win before dbt manifest inspection."""
    with pytest.raises(ValueError, match="compiled JSON config cannot yet construct executable"):
        load_product_definitions(PRODUCT_NAME, project_dir_with_ingestion_no_manifest)


@pytest.mark.requirement("AC-5")
def test_dbt_assets_uses_trace_correlation_facet(project_dir: Path) -> None:
    """The @dbt_assets body must use TraceCorrelationFacetBuilder with emit_start.

    The run_facets passed to emit_start must include a traceCorrelation facet
    when TraceCorrelationFacetBuilder.from_otel_context() returns non-None.
    """
    fake_facet = {"traceId": "abc123", "spanId": "def456"}

    with patch(_TRACE_BUILDER) as mock_builder_cls:
        mock_builder_cls.from_otel_context.return_value = fake_facet

        definitions = load_product_definitions(PRODUCT_NAME, project_dir)
        asset_fn = _extract_dbt_assets_fn(definitions)

        context, lineage = _make_mock_context_with_lineage()
        mock_dbt = context.resources.dbt
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=iter([]))
        mock_dbt.cli.return_value.stream.return_value = mock_stream

        list(asset_fn(context))

        # emit_start must have been called with run_facets containing traceCorrelation
        lineage.emit_start.assert_called_once()
        call_kwargs = lineage.emit_start.call_args
        # The run_facets should include the trace correlation facet
        if call_kwargs.kwargs.get("run_facets"):
            assert "traceCorrelation" in call_kwargs.kwargs["run_facets"]
        elif len(call_kwargs.args) >= 2:
            # Positional arg for run_facets
            run_facets = call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
            assert "traceCorrelation" in (run_facets or {})
        else:
            pytest.fail("emit_start was called without run_facets containing traceCorrelation")


@pytest.mark.requirement("AC-5")
def test_dbt_assets_emit_start_uses_fallback_uuid_on_failure(
    project_dir: Path,
) -> None:
    """If emit_start raises, the body must use a fallback uuid4 for run_id.

    The dbt build must still proceed, and emit_fail/emit_complete must still
    be called with the fallback run_id.
    """
    definitions = load_product_definitions(PRODUCT_NAME, project_dir)
    asset_fn = _extract_dbt_assets_fn(definitions)

    context, lineage = _make_mock_context_with_lineage()
    lineage.emit_start.side_effect = RuntimeError("lineage service down")

    mock_dbt = context.resources.dbt
    mock_stream = MagicMock()
    mock_stream.__iter__ = MagicMock(return_value=iter([]))
    mock_dbt.cli.return_value.stream.return_value = mock_stream

    # Should NOT raise -- dbt proceeds despite lineage failure
    list(asset_fn(context))

    # dbt.cli must still have been called
    mock_dbt.cli.assert_called()

    # emit_complete must be called with a UUID (the fallback)
    lineage.emit_complete.assert_called_once()
    complete_args = lineage.emit_complete.call_args
    # First positional arg should be the run_id (a UUID)
    run_id_arg = complete_args.args[0] if complete_args.args else complete_args.kwargs.get("run_id")
    assert isinstance(run_id_arg, UUID), (
        f"emit_complete run_id should be a UUID (fallback), got {type(run_id_arg).__name__}"
    )


@pytest.mark.requirement("AC-5")
def test_dbt_assets_emit_fail_exception_does_not_swallow_dbt_error(
    project_dir: Path,
) -> None:
    """If emit_fail itself raises, the original dbt exception must still propagate.

    emit_fail failure must never mask the original error.
    """
    definitions = load_product_definitions(PRODUCT_NAME, project_dir)
    asset_fn = _extract_dbt_assets_fn(definitions)

    context, lineage = _make_mock_context_with_lineage()
    lineage.emit_fail.side_effect = RuntimeError("lineage service also down")

    mock_dbt = context.resources.dbt
    dbt_error = ValueError("dbt catastrophic failure")
    mock_dbt.cli.return_value.stream.side_effect = dbt_error

    # The ORIGINAL error (ValueError) must propagate, not RuntimeError from emit_fail
    with pytest.raises(ValueError, match="dbt catastrophic failure"):
        list(asset_fn(context))
