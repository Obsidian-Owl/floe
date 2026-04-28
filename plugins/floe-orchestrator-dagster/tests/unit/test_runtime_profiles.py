"""Tests for Dagster runtime dbt profile preparation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from floe_core.schemas.compiled_artifacts import CompiledArtifacts


@pytest.mark.requirement("ALPHA-HARDENING")
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


@pytest.mark.requirement("ALPHA-HARDENING")
def test_prepare_compiled_profiles_dir_creates_duckdb_parent_directories(
    tmp_path: Path,
    valid_compiled_artifacts: dict[str, Any],
) -> None:
    """Runtime dbt must create directories needed by manifest-driven DuckDB paths."""
    from floe_orchestrator_dagster.runtime import prepare_compiled_profiles_dir

    project_dir = tmp_path / "customer-360"
    project_dir.mkdir()
    duckdb_path = tmp_path / "runtime-data" / "customer_360.duckdb"

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
                    "path": str(duckdb_path),
                }
            },
        }
    }
    artifacts = CompiledArtifacts.model_validate(artifact_payload)

    assert not duckdb_path.parent.exists()

    prepare_compiled_profiles_dir(
        artifacts=artifacts,
        project_dir=project_dir,
    )

    assert duckdb_path.parent.is_dir()


@pytest.mark.requirement("ALPHA-HARDENING")
def test_prepare_compiled_profiles_dir_resolves_relative_duckdb_paths_under_project_dir(
    tmp_path: Path,
    valid_compiled_artifacts: dict[str, Any],
) -> None:
    """Relative DuckDB paths in compiled profiles are relative to the dbt project."""
    from floe_orchestrator_dagster.runtime import prepare_compiled_profiles_dir

    project_dir = tmp_path / "customer-360"
    project_dir.mkdir()

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
                    "path": "runtime-data/customer_360.duckdb",
                }
            },
        }
    }
    artifacts = CompiledArtifacts.model_validate(artifact_payload)

    prepare_compiled_profiles_dir(
        artifacts=artifacts,
        project_dir=project_dir,
    )

    assert (project_dir / "runtime-data").is_dir()


@pytest.mark.requirement("ALPHA-HARDENING")
def test_prepare_compiled_profiles_dir_aliases_compile_time_dbt_project_name(
    tmp_path: Path,
    valid_compiled_artifacts: dict[str, Any],
) -> None:
    """Runtime alias must match compile-time dbt project/profile normalization."""
    from floe_orchestrator_dagster.runtime import prepare_compiled_profiles_dir

    project_dir = tmp_path / "customer-360-"
    project_dir.mkdir()

    artifact_payload = dict(valid_compiled_artifacts)
    artifact_payload["metadata"] = {
        **artifact_payload["metadata"],
        "product_name": "customer-360-",
    }
    artifact_payload["dbt_profiles"] = {
        "customer-360-": {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "duckdb",
                    "path": str(tmp_path / "customer_360.duckdb"),
                }
            },
        }
    }
    artifacts = CompiledArtifacts.model_validate(artifact_payload)

    profiles_dir = prepare_compiled_profiles_dir(
        artifacts=artifacts,
        project_dir=project_dir,
    )

    generated = yaml.safe_load((profiles_dir / "profiles.yml").read_text(encoding="utf-8"))
    assert "customer_360" in generated
