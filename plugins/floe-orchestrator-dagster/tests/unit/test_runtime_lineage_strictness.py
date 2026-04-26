"""Runtime strict lineage policy tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from dagster import Definitions, ResourceDefinition, build_op_context
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

from floe_orchestrator_dagster.capabilities import CapabilityPolicy
from floe_orchestrator_dagster.runtime import build_product_definitions

PRODUCT_NAME = "customer-360"
_RUNTIME_MODULE = "floe_orchestrator_dagster.runtime"
_LINEAGE_FACTORY = f"{_RUNTIME_MODULE}.try_create_lineage_resource"
_EXPORT_FN = f"{_RUNTIME_MODULE}.export_dbt_to_iceberg"
_EXTRACT_LINEAGE_FN = f"{_RUNTIME_MODULE}.extract_dbt_model_lineage"


def _write_manifest(project_dir: Path) -> None:
    """Write the minimal dbt manifest path required by the runtime builder."""
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
    (target_dir / "manifest.json").write_text(json.dumps(manifest))


def _extract_dbt_assets_fn(definitions: Definitions) -> Callable[[Any], Any]:
    """Return the decorated dbt asset function from runtime definitions."""
    assets = list(definitions.assets or [])
    assert assets, "Runtime definitions must include a dbt asset"
    compute_fn = assets[0].op.compute_fn
    return compute_fn.decorated_fn if hasattr(compute_fn, "decorated_fn") else compute_fn


def _with_required_capabilities(artifacts_dict: dict[str, Any]) -> CompiledArtifacts:
    """Add alpha-required plugins to a CompiledArtifacts fixture dict."""
    data = artifacts_dict.copy()
    data["plugins"] = {
        **data["plugins"],
        "catalog": {"type": "polaris", "version": "0.1.0", "config": {}},
        "storage": {"type": "s3", "version": "1.0.0", "config": {}},
        "lineage_backend": {
            "type": "marquez",
            "version": "0.1.0",
            "config": {"url": "http://marquez:5000"},
        },
    }
    return CompiledArtifacts.model_validate(data)


def test_runtime_default_policy_passes_lineage_strict_false(
    tmp_path: Path,
    valid_compiled_artifacts: dict[str, Any],
) -> None:
    """Default runtime policy must keep lineage emission best-effort."""
    _write_manifest(tmp_path)
    artifacts = _with_required_capabilities(valid_compiled_artifacts)

    with patch(
        _LINEAGE_FACTORY,
        return_value={"lineage": ResourceDefinition.hardcoded_resource(MagicMock())},
    ) as mock_lineage:
        build_product_definitions(
            product_name=PRODUCT_NAME,
            artifacts=artifacts,
            project_dir=tmp_path,
        )

    mock_lineage.assert_called_once_with(
        artifacts.plugins,
        strict=False,
        default_namespace=artifacts.observability.lineage_namespace,
    )


def test_runtime_strict_complete_emission_failure_raises_after_iceberg_success(
    tmp_path: Path,
    valid_compiled_artifacts: dict[str, Any],
) -> None:
    """Alpha runtime must propagate terminal lineage failures after export succeeds."""
    _write_manifest(tmp_path)
    artifacts = _with_required_capabilities(valid_compiled_artifacts)
    lineage = MagicMock()
    lineage.emit_start.return_value = uuid4()
    lineage.emit_complete.side_effect = RuntimeError("marquez unavailable")

    dbt_result = MagicMock()
    dbt_result.stream.return_value = []
    dbt = MagicMock()
    dbt.cli.return_value = dbt_result
    export_result = MagicMock(tables_written=1)

    with (
        patch(
            _LINEAGE_FACTORY,
            return_value={"lineage": ResourceDefinition.hardcoded_resource(lineage)},
        ),
        patch(_EXPORT_FN, return_value=export_result) as mock_export,
    ):
        definitions = build_product_definitions(
            product_name=PRODUCT_NAME,
            artifacts=artifacts,
            project_dir=tmp_path,
            capability_policy=CapabilityPolicy.alpha(),
        )
        asset_fn = _extract_dbt_assets_fn(definitions)
        context = build_op_context(resources={"dbt": dbt, "lineage": lineage})

        with pytest.raises(RuntimeError, match="marquez unavailable"):
            list(asset_fn(context))

    dbt.cli.assert_called_once()
    mock_export.assert_called_once()
    lineage.emit_complete.assert_called_once()


def test_runtime_emits_per_model_lineage_after_iceberg_export_with_parent_run(
    tmp_path: Path,
    valid_compiled_artifacts: dict[str, Any],
) -> None:
    """Runtime path must emit dbt model lineage linked to the Dagster run."""
    _write_manifest(tmp_path)
    artifacts = _with_required_capabilities(valid_compiled_artifacts)
    dagster_run_id = uuid4()

    lineage = MagicMock()
    lineage.namespace = artifacts.observability.lineage_namespace
    lineage.emit_start.return_value = dagster_run_id
    extracted_event = MagicMock(name="lineage_event")

    dbt_result = MagicMock()
    dbt_result.stream.return_value = []
    dbt = MagicMock()
    dbt.cli.return_value = dbt_result
    export_result = MagicMock(tables_written=1)
    call_order: list[str] = []

    def _export_side_effect(*_args: Any, **_kwargs: Any) -> Any:
        call_order.append("export")
        return export_result

    def _extract_side_effect(*_args: Any, **_kwargs: Any) -> list[Any]:
        call_order.append("extract")
        return [extracted_event]

    with (
        patch(
            _LINEAGE_FACTORY,
            return_value={"lineage": ResourceDefinition.hardcoded_resource(lineage)},
        ),
        patch(_EXPORT_FN, side_effect=_export_side_effect) as mock_export,
        patch(_EXTRACT_LINEAGE_FN, side_effect=_extract_side_effect) as mock_extract,
    ):
        definitions = build_product_definitions(
            product_name=PRODUCT_NAME,
            artifacts=artifacts,
            project_dir=tmp_path,
            capability_policy=CapabilityPolicy.alpha(),
        )
        asset_fn = _extract_dbt_assets_fn(definitions)
        context = MagicMock()
        context.resources.dbt = dbt
        context.resources.lineage = lineage
        context.run.run_id = str(dagster_run_id)

        list(asset_fn(context))

    lineage.emit_start.assert_called_once()
    _, emit_start_kwargs = lineage.emit_start.call_args
    assert emit_start_kwargs["run_id"] == dagster_run_id
    mock_export.assert_called_once()
    mock_extract.assert_called_once_with(
        tmp_path,
        dagster_run_id,
        PRODUCT_NAME,
        artifacts.observability.lineage_namespace,
    )
    lineage.emit_event.assert_called_once_with(extracted_event)
    lineage.flush.assert_called_once()
    assert call_order == ["export", "extract"]
