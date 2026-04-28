"""Tests for Dagster runtime dbt profile preparation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from floe_core.schemas.compiled_artifacts import CompiledArtifacts


def test_prepare_compiled_profiles_dir_uses_compiled_artifacts_without_overwriting_project(
    tmp_path: Path,
    valid_compiled_artifacts: dict[str, Any],
) -> None:
    """Runtime dbt must use compiled profile config rather than stale project profiles."""
    from floe_orchestrator_dagster.runtime import prepare_compiled_profiles_dir

    project_dir = tmp_path / "customer-360"
    project_dir.mkdir()
    checked_in_profile = project_dir / "profiles.yml"
    checked_in_profile.write_text(
        "\n".join(
            [
                "customer_360:",
                "  target: dev",
                "  outputs:",
                "    dev:",
                "      type: duckdb",
                "      path: /tmp/stale.duckdb",
                "",
            ]
        ),
        encoding="utf-8",
    )

    artifact_payload = dict(valid_compiled_artifacts)
    artifact_payload["metadata"] = {
        **artifact_payload["metadata"],
        "product_name": "customer-360",
    }
    artifact_payload["dbt_profiles"] = {
        "customer_360": {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "duckdb",
                    "path": "/tmp/floe/customer_360.duckdb",
                }
            },
        }
    }
    artifacts = CompiledArtifacts.model_validate(artifact_payload)

    profiles_dir = prepare_compiled_profiles_dir(
        artifacts=artifacts,
        project_dir=project_dir,
    )

    assert profiles_dir != project_dir
    assert checked_in_profile.read_text(encoding="utf-8").find("/tmp/stale.duckdb") != -1
    generated = yaml.safe_load((profiles_dir / "profiles.yml").read_text(encoding="utf-8"))
    assert generated["customer_360"]["outputs"]["dev"]["path"] == ("/tmp/floe/customer_360.duckdb")
