"""Runtime loader for Dagster product definitions.

Reads compiled artifacts and wires dbt assets, lineage, and Iceberg
resources into a single ``dagster.Definitions`` object.

Requirements:
    AC-1: Returns Definitions with dbt_assets, DbtCliResource, lineage, iceberg
    AC-2: No module-load-time connections
    AC-3: Iceberg resource absent when unconfigured, exception propagated when factory raises
    AC-5: dbt_assets body emits lineage start/fail/complete around dbt.cli().stream()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from dagster import Definitions, ResourceDefinition
from dagster_dbt import DbtCliResource, dbt_assets
from floe_core.lineage.facets import TraceCorrelationFacetBuilder
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

from floe_orchestrator_dagster.export.iceberg import export_dbt_to_iceberg
from floe_orchestrator_dagster.resources.iceberg import try_create_iceberg_resources
from floe_orchestrator_dagster.resources.lineage import try_create_lineage_resource


def load_product_definitions(
    product_name: str,
    project_dir: Path,
) -> Definitions:
    """Load a product's Dagster definitions from compiled artifacts.

    Reads compiled_artifacts.json from project_dir, validates it with
    CompiledArtifacts, creates @dbt_assets with lineage emission, wires
    DbtCliResource, lineage resource, and optionally Iceberg resources.

    Args:
        product_name: Name of the data product.
        project_dir: Path to the dbt project directory containing
            compiled_artifacts.json and target/manifest.json.

    Returns:
        Dagster Definitions with all wired resources and assets.

    Raises:
        FileNotFoundError: If compiled_artifacts.json is missing.
        ValidationError: If compiled_artifacts.json is invalid JSON or fails
            Pydantic validation.
    """
    artifacts_path = project_dir / "compiled_artifacts.json"
    raw_text = artifacts_path.read_text()
    artifacts = CompiledArtifacts.model_validate_json(raw_text)

    manifest_path = project_dir / "target" / "manifest.json"

    @dbt_assets(
        manifest=manifest_path,
        name=f"{product_name.replace('-', '_')}_dbt_assets",
        required_resource_keys={"dbt", "lineage"},
    )
    def _dbt_assets_fn(context) -> object:  # type: ignore[misc]
        """Run dbt build with lineage emission.

        Accesses dbt via context.resources.dbt and lineage via
        context.resources.lineage. Emits OpenLineage start event before dbt,
        fail event on error (then re-raises), complete event on success,
        and optionally exports to Iceberg after a successful dbt run.

        Args:
            context: Dagster AssetExecutionContext.

        Yields:
            dbt event stream items from dbt.cli().stream().
        """
        dbt = context.resources.dbt  # type: ignore[union-attr]
        lineage = context.resources.lineage  # type: ignore[union-attr]
        run_id: UUID | None = None

        # 1. Emit START with trace correlation — never blocks dbt
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
            run_id = uuid4()  # fallback so downstream calls have a valid ID

        # 2. Run dbt — on throw: emit FAIL, re-raise
        try:
            yield from dbt.cli(["build"], context=context).stream()
        except Exception as exc:
            try:
                lineage.emit_fail(run_id, product_name, error_message=type(exc).__name__)
            except Exception as _fail_exc:
                context.log.debug("emit_fail failed: %s", _fail_exc)
            raise

        # 3. Export to Iceberg (only if catalog configured and dbt succeeded)
        if artifacts.plugins and artifacts.plugins.catalog:
            export_dbt_to_iceberg(context, product_name, project_dir, artifacts)

        # 4. Emit COMPLETE
        try:
            lineage.emit_complete(run_id, product_name)
        except Exception as _complete_exc:
            context.log.debug("emit_complete failed: %s", _complete_exc)

    _project_dir_str = str(project_dir)
    _plugins = artifacts.plugins

    def _dbt_resource_fn(_init_context: Any) -> Any:
        return DbtCliResource(
            project_dir=_project_dir_str,
            profiles_dir=_project_dir_str,
        )

    resources: dict[str, object] = {
        "dbt": ResourceDefinition(resource_fn=_dbt_resource_fn),
        **try_create_lineage_resource(_plugins),
    }

    # Conditionally add iceberg resource — deferred to avoid eager connections.
    # Only add when catalog is configured; let try_create_iceberg_resources
    # decide if storage is also present.
    if _plugins and _plugins.catalog:

        def _iceberg_resource_fn(_init_context: Any) -> Any:
            result = try_create_iceberg_resources(_plugins)
            return result.get("iceberg")

        resources["iceberg"] = ResourceDefinition(resource_fn=_iceberg_resource_fn)

    return Definitions(
        assets=[_dbt_assets_fn],
        resources=resources,
    )
