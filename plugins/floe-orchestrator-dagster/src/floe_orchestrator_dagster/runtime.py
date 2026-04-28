"""Shared Dagster runtime builder for floe data products."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import yaml
from dagster import AssetKey, Definitions, ResourceDefinition
from dagster_dbt import DbtCliResource, dbt_assets
from floe_core.lineage.facets import TraceCorrelationFacetBuilder
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

from floe_orchestrator_dagster.capabilities import CapabilityPolicy
from floe_orchestrator_dagster.export.iceberg import export_dbt_to_iceberg
from floe_orchestrator_dagster.lineage_extraction import extract_dbt_model_lineage
from floe_orchestrator_dagster.resources.iceberg import try_create_iceberg_resources
from floe_orchestrator_dagster.resources.lineage import try_create_lineage_resource

_PROJECT_DIR_REQUIRED_MESSAGE = (
    "Dagster runtime definitions require project_dir so dbt manifest, profiles.yml, "
    "and compiled_artifacts.json are resolved from one product directory; use the "
    "generated definitions.py loader/shim path for runtime definitions."
)
_INGESTION_RUNTIME_DISABLED_MESSAGE = (
    "Dagster ingestion runtime is not enabled because compiled JSON config cannot yet "
    "construct executable dlt source objects; implement a source-construction layer "
    "before enabling ingestion assets."
)


def _has_iceberg_config(artifacts: CompiledArtifacts) -> bool:
    """Return True when both catalog and storage plugins are configured."""
    plugins = artifacts.plugins
    return bool(plugins and plugins.catalog and plugins.storage)


def _has_ingestion_workloads(plugins: Any | None) -> bool:
    """Return True when configured ingestion contains any workload config."""
    ingestion = getattr(plugins, "ingestion", None)
    config = getattr(ingestion, "config", None)
    if config is None:
        return False
    if not isinstance(config, dict):
        return True
    if not config:
        return False
    keys = set(config)
    if keys != {"sources"}:
        return True
    sources = config["sources"]
    if not isinstance(sources, list):
        return True
    return len(sources) > 0


def _lineage_namespace(artifacts: CompiledArtifacts) -> str | None:
    """Return the compiled lineage namespace when artifacts provide one."""
    observability = getattr(artifacts, "observability", None)
    namespace = getattr(observability, "lineage_namespace", None)
    return str(namespace) if namespace else None


def _safe_product_name(product_name: str) -> str:
    """Return the dbt-safe product/profile name used by demo projects."""
    return product_name.replace("-", "_")


def _prepare_duckdb_output_directories(
    profile_payload: dict[str, Any],
    *,
    project_dir: Path,
) -> None:
    """Create parent directories required by file-backed DuckDB profile outputs."""
    for profile in profile_payload.values():
        if not isinstance(profile, dict):
            continue
        outputs = profile.get("outputs")
        if not isinstance(outputs, dict):
            continue
        for output in outputs.values():
            if not isinstance(output, dict):
                continue
            if output.get("type") != "duckdb":
                continue
            raw_path = output.get("path")
            if not isinstance(raw_path, str) or not raw_path or raw_path == ":memory:":
                continue
            duckdb_path = Path(raw_path)
            if not duckdb_path.is_absolute():
                duckdb_path = project_dir / duckdb_path
            duckdb_path.parent.mkdir(parents=True, exist_ok=True)


def prepare_compiled_profiles_dir(
    *,
    artifacts: CompiledArtifacts,
    project_dir: Path,
) -> Path:
    """Write compiled dbt profiles to an isolated runtime directory.

    Dagster runtime must use the compiled artifact contract, not a checked-in
    ``profiles.yml`` that can drift from manifest-driven plugin config.
    """
    profiles = artifacts.dbt_profiles
    if not isinstance(profiles, dict) or not profiles:
        return project_dir

    product_name = getattr(getattr(artifacts, "metadata", None), "product_name", None)
    profile_payload = dict(profiles)
    if isinstance(product_name, str):
        safe_name = _safe_product_name(product_name)
        if product_name in profile_payload and safe_name not in profile_payload:
            profile_payload[safe_name] = profile_payload[product_name]

    _prepare_duckdb_output_directories(profile_payload, project_dir=project_dir)

    project_hash = hashlib.sha256(str(project_dir.resolve()).encode("utf-8")).hexdigest()[:12]
    profiles_dir = (
        Path(tempfile.gettempdir()) / "floe-dbt-profiles" / f"{project_dir.name}-{project_hash}"
    )
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / "profiles.yml").write_text(
        yaml.safe_dump(profile_payload, sort_keys=False),
        encoding="utf-8",
    )
    return profiles_dir


def _create_semantic_resources(plugins: Any | None) -> dict[str, Any]:
    """Create semantic resources through the configured semantic factory."""
    from floe_orchestrator_dagster.resources.semantic import (
        try_create_semantic_resources,
    )

    return try_create_semantic_resources(plugins)


def _dagster_run_id(context: Any) -> UUID | None:
    """Return the Dagster run id as a UUID when available."""
    try:
        return UUID(str(context.run.run_id))
    except Exception:
        return None


def build_product_definitions(
    *,
    product_name: str,
    artifacts: CompiledArtifacts,
    project_dir: Path | None,
    capability_policy: CapabilityPolicy | None = None,
) -> Definitions:
    """Build Dagster definitions for a compiled floe product.

    Args:
        product_name: Name of the data product.
        artifacts: Validated compiled artifacts for the data product.
        project_dir: dbt project directory containing target/manifest.json.
        capability_policy: Optional policy controlling whether optional
            capabilities such as lineage are best-effort or strict. Defaults
            to the platform default policy when omitted.

    Returns:
        Dagster Definitions with dbt assets and runtime resources.

    Raises:
        ValueError: If project_dir is not supplied.
    """
    if project_dir is None:
        raise ValueError(_PROJECT_DIR_REQUIRED_MESSAGE)

    policy = capability_policy or CapabilityPolicy.default()
    policy.validate_required_plugins(artifacts.plugins)

    plugins = artifacts.plugins
    if _has_ingestion_workloads(plugins):
        raise ValueError(_INGESTION_RUNTIME_DISABLED_MESSAGE)

    manifest_path = project_dir / "target" / "manifest.json"

    @dbt_assets(
        manifest=manifest_path,
        name=f"{product_name.replace('-', '_')}_dbt_assets",
        required_resource_keys={"dbt", "lineage"},
    )
    # Dagster's @dbt_assets decorator wraps this callable dynamically, and the
    # concrete context type is not stable enough for strict annotation here.
    def _dbt_assets_fn(context) -> object:  # type: ignore[no-untyped-def]
        """Run dbt build with lineage emission."""
        dbt = context.resources.dbt
        lineage = context.resources.lineage
        run_id: UUID | None = None

        run_facets: dict[str, object] = {}
        try:
            trace_facet = TraceCorrelationFacetBuilder.from_otel_context()
            if trace_facet is not None:
                run_facets["traceCorrelation"] = trace_facet
        except Exception as _trace_exc:
            context.log.warning("Trace facet creation failed: %s", _trace_exc)
        try:
            dagster_run_id = _dagster_run_id(context)
            run_id = lineage.emit_start(
                product_name,
                run_id=dagster_run_id,
                run_facets=run_facets or None,
            )
        except Exception as _start_exc:
            if policy.require_lineage:
                raise
            context.log.warning("emit_start failed; using fallback run id: %s", _start_exc)
            run_id = uuid4()

        try:
            yield from dbt.cli(["build"], context=context).stream()
            if _has_iceberg_config(artifacts):
                export_result = export_dbt_to_iceberg(
                    context,
                    product_name,
                    project_dir,
                    artifacts,
                )
                if export_result.tables_written == 0:
                    raise RuntimeError(
                        f"Configured Iceberg export wrote no tables for product {product_name}"
                    )
            try:
                model_events = extract_dbt_model_lineage(
                    project_dir,
                    run_id,
                    product_name,
                    lineage.namespace,
                )
                for event in model_events:
                    lineage.emit_event(event)
            except Exception as _model_lineage_exc:
                if policy.require_lineage:
                    raise
                context.log.warning(
                    "runtime model lineage emission failed: %s",
                    _model_lineage_exc,
                )
        except Exception as exc:
            try:
                lineage.emit_fail(run_id, product_name, error_message=type(exc).__name__)
                lineage.flush()
            except Exception as _fail_exc:
                if policy.require_lineage:
                    raise
                context.log.warning("emit_fail failed: %s", _fail_exc)
            raise

        try:
            lineage.emit_complete(run_id, product_name)
            lineage.flush()
        except Exception as _complete_exc:
            if policy.require_lineage:
                raise
            context.log.warning("emit_complete failed: %s", _complete_exc)

    def _dbt_resource_fn(_init_context: Any) -> Any:
        profiles_dir = prepare_compiled_profiles_dir(
            artifacts=artifacts,
            project_dir=project_dir,
        )
        return DbtCliResource(
            project_dir=str(project_dir),
            profiles_dir=str(profiles_dir),
        )

    resources: dict[str, object] = {
        "dbt": ResourceDefinition(resource_fn=_dbt_resource_fn),
        **try_create_lineage_resource(
            plugins,
            strict=policy.require_lineage,
            default_namespace=_lineage_namespace(artifacts),
        ),
    }
    assets: list[Any] = [_dbt_assets_fn]

    if plugins and plugins.semantic:
        semantic_resources = _create_semantic_resources(plugins)
        resources.update(semantic_resources)
        if "semantic_layer" in semantic_resources:
            from floe_orchestrator_dagster.assets.semantic_sync import (
                create_sync_semantic_schemas_asset,
            )

            assets.append(
                create_sync_semantic_schemas_asset(
                    manifest_path=project_dir / "target" / "manifest.json",
                    output_dir=project_dir / "cube" / "schema",
                    deps=[
                        AssetKey(model.name)
                        for model in getattr(getattr(artifacts, "transforms", None), "models", [])
                    ],
                )
            )

    if _has_iceberg_config(artifacts):

        def _iceberg_resource_fn(_init_context: Any) -> Any:
            result = try_create_iceberg_resources(
                plugins,
                governance=getattr(artifacts, "governance", None),
            )
            return result.get("iceberg")

        resources["iceberg"] = ResourceDefinition(resource_fn=_iceberg_resource_fn)

    return Definitions(
        assets=assets,
        resources=resources,
    )
