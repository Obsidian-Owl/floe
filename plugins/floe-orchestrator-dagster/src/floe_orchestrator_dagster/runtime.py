"""Shared Dagster runtime builder for floe data products."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from dagster import AssetKey, Definitions, ResourceDefinition
from dagster_dbt import DbtCliResource, dbt_assets
from floe_core.lineage.facets import TraceCorrelationFacetBuilder
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

from floe_orchestrator_dagster.export.iceberg import export_dbt_to_iceberg
from floe_orchestrator_dagster.resources.iceberg import try_create_iceberg_resources
from floe_orchestrator_dagster.resources.lineage import try_create_lineage_resource

_PROJECT_DIR_REQUIRED_MESSAGE = (
    "Dagster runtime definitions require project_dir so dbt manifest, profiles.yml, "
    "and compiled_artifacts.json are resolved from one product directory; use the "
    "generated definitions.py loader/shim path for runtime definitions."
)


def _has_iceberg_config(artifacts: CompiledArtifacts) -> bool:
    """Return True when both catalog and storage plugins are configured."""
    plugins = artifacts.plugins
    return bool(plugins and plugins.catalog and plugins.storage)


def _create_semantic_resources(plugins: Any | None) -> dict[str, Any]:
    """Create semantic resources through the configured semantic factory."""
    from floe_orchestrator_dagster.resources.semantic import (
        try_create_semantic_resources,
    )

    return try_create_semantic_resources(plugins)


def _create_ingestion_resources(plugins: Any | None) -> dict[str, Any]:
    """Create ingestion resources through the configured ingestion factory."""
    from floe_orchestrator_dagster.resources.ingestion import (
        try_create_ingestion_resources,
    )

    return try_create_ingestion_resources(plugins)


def build_product_definitions(
    *,
    product_name: str,
    artifacts: CompiledArtifacts,
    project_dir: Path | None,
) -> Definitions:
    """Build Dagster definitions for a compiled floe product.

    Args:
        product_name: Name of the data product.
        artifacts: Validated compiled artifacts for the data product.
        project_dir: dbt project directory containing target/manifest.json.

    Returns:
        Dagster Definitions with dbt assets and runtime resources.

    Raises:
        ValueError: If project_dir is not supplied.
    """
    if project_dir is None:
        raise ValueError(_PROJECT_DIR_REQUIRED_MESSAGE)

    manifest_path = project_dir / "target" / "manifest.json"

    @dbt_assets(
        manifest=manifest_path,
        name=f"{product_name.replace('-', '_')}_dbt_assets",
        required_resource_keys={"dbt", "lineage"},
    )
    def _dbt_assets_fn(context) -> object:  # type: ignore[misc]
        """Run dbt build with lineage emission."""
        dbt = context.resources.dbt  # type: ignore[union-attr]
        lineage = context.resources.lineage  # type: ignore[union-attr]
        run_id: UUID | None = None

        run_facets: dict[str, object] = {}
        try:
            trace_facet = TraceCorrelationFacetBuilder.from_otel_context()
            if trace_facet is not None:
                run_facets["traceCorrelation"] = trace_facet
        except Exception as _trace_exc:
            context.log.debug("Trace facet creation failed: %s", _trace_exc)
        try:
            run_id = lineage.emit_start(product_name, run_facets=run_facets or None)
        except Exception:
            run_id = uuid4()

        try:
            yield from dbt.cli(["build"], context=context).stream()
        except Exception as exc:
            try:
                lineage.emit_fail(run_id, product_name, error_message=type(exc).__name__)
            except Exception as _fail_exc:
                context.log.debug("emit_fail failed: %s", _fail_exc)
            raise

        if _has_iceberg_config(artifacts):
            export_dbt_to_iceberg(context, product_name, project_dir, artifacts)

        try:
            lineage.emit_complete(run_id, product_name)
        except Exception as _complete_exc:
            context.log.debug("emit_complete failed: %s", _complete_exc)

    project_dir_str = str(project_dir)
    plugins = artifacts.plugins

    def _dbt_resource_fn(_init_context: Any) -> Any:
        return DbtCliResource(
            project_dir=project_dir_str,
            profiles_dir=project_dir_str,
        )

    resources: dict[str, object] = {
        "dbt": ResourceDefinition(resource_fn=_dbt_resource_fn),
        **try_create_lineage_resource(plugins),
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

    if plugins and plugins.ingestion:
        ingestion_resources = _create_ingestion_resources(plugins)
        resources.update(ingestion_resources)
        if "ingestion" in ingestion_resources:
            from floe_orchestrator_dagster.assets.ingestion import (
                create_ingestion_assets,
            )

            assets.extend(create_ingestion_assets(plugins.ingestion))

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
