"""Extract per-model OpenLineage events from dbt artifacts.

This module reads dbt manifest.json and run_results.json from a project's
target/ directory and converts them into a flat list of LineageEvent pairs
(START + COMPLETE/FAIL) for each executed model.

Each model event pair:
- Carries a ParentRunFacet linking it to the parent Dagster run.
- Uses timing data from run_results.json for event_time.
- Includes inputs/outputs resolved via DbtLineageExtractor.

See Also:
    - floe_core.lineage.extractors.dbt: DbtLineageExtractor
    - floe_core.lineage.facets: ParentRunFacetBuilder
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from floe_core.lineage.extractors.dbt import DbtLineageExtractor
from floe_core.lineage.facets import ColumnLineageFacetBuilder, ParentRunFacetBuilder
from floe_core.lineage.types import LineageDataset, LineageEvent, LineageJob, LineageRun, RunState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MANIFEST_FILENAME = "manifest.json"
_RUN_RESULTS_FILENAME = "run_results.json"
_TARGET_DIRNAME = "target"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_iso_datetime(ts: str) -> datetime:
    """Parse an ISO 8601 datetime string to a timezone-aware datetime.

    Args:
        ts: ISO 8601 string, e.g. "2026-03-18T10:00:00Z".

    Returns:
        A timezone-aware datetime in UTC.
    """
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _load_json(path: Path, artifact_name: str) -> dict[str, Any] | None:
    """Load and parse a JSON file, returning None on any error.

    Logs a WARNING when the file is missing or malformed.

    Args:
        path: Absolute path to the JSON file.
        artifact_name: Human-readable name used in warning messages.

    Returns:
        Parsed dict, or None on failure.
    """
    if not path.exists():
        logger.warning(
            "dbt artifact missing: %s not found at %s",
            artifact_name,
            str(path),
        )
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text())
        return data
    except json.JSONDecodeError:
        logger.warning(
            "dbt artifact malformed JSON: %s at %s",
            artifact_name,
            str(path),
        )
        return None


def _enrich_outputs_with_column_lineage(
    outputs: list[LineageDataset],
    node: dict[str, Any],
    inputs: list[LineageDataset],
    namespace: str,
) -> list[LineageDataset]:
    """Ensure output datasets carry a columnLineage facet when the model has columns.

    The DbtLineageExtractor only adds columnLineage when both model columns
    and upstream columns are present. This helper ensures the facet is always
    added when the model node declares columns, using any upstream dataset
    columns collected from the input datasets' schema facets as context.

    Args:
        outputs: Output datasets as returned by the extractor.
        node: dbt manifest node dict for the model.
        inputs: Input datasets resolved by the extractor.
        namespace: OpenLineage namespace for upstream column references.

    Returns:
        New list of output datasets, with columnLineage added when columns
        are present and the extractor did not already add it.
    """
    model_columns: dict[str, Any] = node.get("columns", {})
    if not model_columns:
        return outputs

    enriched: list[LineageDataset] = []
    for dataset in outputs:
        if "columnLineage" not in dataset.facets:
            # Build upstream column refs from input dataset schema facets
            upstream_columns: list[dict[str, Any]] = []
            for inp in inputs:
                schema_facet = inp.facets.get("schema", {})
                for field in schema_facet.get("fields", []):
                    upstream_columns.append(
                        {
                            "namespace": namespace,
                            "name": inp.name,
                            "field": field["name"],
                        }
                    )

            col_lineage_facet = ColumnLineageFacetBuilder.from_dbt_columns(
                model_columns, upstream_columns
            )
            updated_facets = {**dataset.facets, "columnLineage": col_lineage_facet}
            dataset = LineageDataset(
                namespace=dataset.namespace,
                name=dataset.name,
                facets=updated_facets,
            )
        enriched.append(dataset)
    return enriched


def _resolve_timing(
    timing: list[dict[str, str]],
) -> tuple[datetime, datetime]:
    """Resolve start and end event times from a run_results timing list.

    Uses timing[0].started_at as the START time and timing[-1].completed_at
    as the COMPLETE/FAIL time. Falls back to UTC now when the list is empty.

    Args:
        timing: List of timing dicts from run_results, each with
            "started_at" and "completed_at" keys.

    Returns:
        Tuple of (start_time, end_time) as timezone-aware datetimes.
    """
    fallback = datetime.now(timezone.utc)
    if not timing:
        return (fallback, fallback)
    start_time = _parse_iso_datetime(timing[0]["started_at"])
    end_time = _parse_iso_datetime(timing[-1]["completed_at"])
    return (start_time, end_time)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_dbt_model_lineage(
    project_dir: Path,
    parent_run_id: UUID,
    parent_job_name: str,
    namespace: str,
) -> list[LineageEvent]:
    """Extract per-model lineage events from dbt artifacts.

    Reads ``target/manifest.json`` and ``target/run_results.json`` from
    *project_dir* and returns one START event and one COMPLETE or FAIL event
    for each model result found in run_results.

    Returns an empty list (without raising) when artifacts are missing or
    cannot be parsed.

    Args:
        project_dir: Root directory of the dbt project. The function looks
            for artifacts under ``project_dir/target/``.
        parent_run_id: UUID of the parent Dagster run, included in each
            model event via ParentRunFacet.
        parent_job_name: Name of the parent Dagster job, included in each
            model event via ParentRunFacet.
        namespace: OpenLineage namespace for all datasets and jobs.

    Returns:
        Flat list of LineageEvent objects: one START + one COMPLETE/FAIL per
        model. Models that are not in the manifest are silently skipped.
        Non-model results (e.g., test.*) are always skipped.
    """
    target_dir = project_dir / _TARGET_DIRNAME

    manifest = _load_json(target_dir / _MANIFEST_FILENAME, _MANIFEST_FILENAME)
    if manifest is None:
        return []

    run_results = _load_json(target_dir / _RUN_RESULTS_FILENAME, _RUN_RESULTS_FILENAME)
    if run_results is None:
        return []

    extractor = DbtLineageExtractor(manifest, default_namespace=namespace)
    parent_facet = ParentRunFacetBuilder.from_parent(
        parent_run_id=parent_run_id,
        parent_job_name=parent_job_name,
        parent_job_namespace=namespace,
    )

    events: list[LineageEvent] = []

    for result in run_results.get("results", []):
        unique_id: str = result.get("unique_id", "")
        if not unique_id.startswith("model."):
            continue

        inputs, outputs = extractor.extract_model(unique_id)

        # Enrich outputs with columnLineage facet when model declares columns
        # and the extractor did not add the facet (happens when upstream has no columns).
        node = manifest.get("nodes", {}).get(unique_id, {})
        outputs = _enrich_outputs_with_column_lineage(outputs, node, inputs, namespace)

        model_run_id = uuid4()
        run = LineageRun(run_id=model_run_id, facets={"parentRun": parent_facet})
        job = LineageJob(namespace=namespace, name=unique_id)

        timing: list[dict[str, str]] = result.get("timing", [])
        start_time, end_time = _resolve_timing(timing)

        # START event
        events.append(
            LineageEvent(
                event_type=RunState.START,
                event_time=start_time,
                run=run,
                job=job,
                inputs=inputs,
                outputs=outputs,
            )
        )

        # COMPLETE or FAIL event
        status: str = result.get("status", "")
        end_state = RunState.FAIL if status == "error" else RunState.COMPLETE
        events.append(
            LineageEvent(
                event_type=end_state,
                event_time=end_time,
                run=run,
                job=job,
                inputs=inputs,
                outputs=outputs,
            )
        )

    return events
