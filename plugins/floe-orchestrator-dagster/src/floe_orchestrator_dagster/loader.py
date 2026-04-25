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

from dagster import Definitions
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

from floe_orchestrator_dagster.runtime import build_product_definitions


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
    artifacts = CompiledArtifacts.model_validate_json(artifacts_path.read_text())
    return build_product_definitions(
        product_name=product_name,
        artifacts=artifacts,
        project_dir=project_dir,
    )
