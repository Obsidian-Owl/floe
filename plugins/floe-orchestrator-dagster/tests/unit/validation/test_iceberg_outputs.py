"""Tests for deployed Iceberg output validation helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call

import pytest
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

import floe_orchestrator_dagster.validation.iceberg_outputs as iceberg_outputs
from floe_orchestrator_dagster.validation.iceberg_outputs import _parse_recovery_mode


def _make_artifacts(*, model_names: list[str] | None = None) -> CompiledArtifacts:
    """Build compiled artifacts with configured catalog and storage plugins."""
    return CompiledArtifacts(
        version="0.5.0",
        metadata=CompilationMetadata(
            compiled_at=datetime.now(timezone.utc),
            floe_version="0.5.0",
            source_hash="sha256:abc123def456",
            product_name="customer-360",
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
            catalog=PluginRef(type="polaris", version="0.1.0", config={"uri": "memory://"}),
            storage=PluginRef(type="s3", version="1.0.0", config={"endpoint": "memory://"}),
        ),
        transforms=ResolvedTransforms(
            models=[
                ResolvedModel(name=model_name, compute="duckdb")
                for model_name in (model_names or ["mart_customer_360"])
            ],
            default_compute="duckdb",
        ),
    )


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_parse_recovery_mode_defaults_to_strict() -> None:
    """Validation is strict unless caller opts into materialization repair."""
    assert _parse_recovery_mode(None) == "strict"
    assert _parse_recovery_mode("") == "strict"


@pytest.mark.parametrize("value", ["strict", "repair"])
@pytest.mark.requirement("ALPHA-ICEBERG")
def test_parse_recovery_mode_accepts_supported_modes(value: str) -> None:
    """Supported modes are explicit and stable."""
    assert _parse_recovery_mode(value) == value


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_parse_recovery_mode_rejects_unknown_value() -> None:
    """Unknown recovery modes fail before catalog mutation."""
    with pytest.raises(ValueError, match="Unsupported Iceberg validation recovery mode"):
        _parse_recovery_mode("reset")


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_reset_iceberg_outputs_drops_expected_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset mode drops expected output registrations before validation."""
    artifacts = _make_artifacts(model_names=["mart_customer_360", "int_customer_orders"])
    catalog = MagicMock()
    monkeypatch.setattr(iceberg_outputs, "_connect_catalog_from_artifacts", lambda _: catalog)

    dropped = iceberg_outputs.reset_iceberg_outputs(artifacts)

    assert dropped == ["customer_360.mart_customer_360", "customer_360.int_customer_orders"]
    assert catalog.drop_table.call_args_list == [
        call("customer_360.mart_customer_360", purge_requested=False),
        call("customer_360.int_customer_orders", purge_requested=False),
    ]


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_reset_iceberg_outputs_tolerates_missing_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reset mode is safe to rerun when an expected table is already absent."""
    artifacts = _make_artifacts(model_names=["mart_customer_360", "int_customer_orders"])
    catalog = MagicMock()
    catalog.drop_table.side_effect = [None, RuntimeError("Table not found")]
    monkeypatch.setattr(iceberg_outputs, "_connect_catalog_from_artifacts", lambda _: catalog)

    dropped = iceberg_outputs.reset_iceberg_outputs(artifacts)

    assert dropped == ["customer_360.mart_customer_360"]


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_main_reset_only_drops_without_validating_and_prints_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI reset mode reports diagnostics without deleting post-run validation inputs."""
    artifacts_path = tmp_path / "compiled_artifacts.json"
    artifacts_path.write_text("{}")
    artifacts = _make_artifacts()
    calls: list[tuple[str, Any]] = []

    def model_validate_json(_payload: str) -> CompiledArtifacts:
        calls.append(("load", None))
        return artifacts

    def reset_outputs(
        *,
        artifacts: CompiledArtifacts,
        expected_tables: list[str] | None,
    ) -> list[str]:
        calls.append(("reset", (artifacts, expected_tables)))
        return ["customer_360.mart_customer_360"]

    def validate_outputs(
        *,
        artifacts: CompiledArtifacts,
        expected_tables: list[str] | None,
    ) -> iceberg_outputs.IcebergOutputValidationResult:
        calls.append(("validate", (artifacts, expected_tables)))
        return iceberg_outputs.IcebergOutputValidationResult(
            expected_table_names=["customer_360.mart_customer_360"],
            table_names=["customer_360.mart_customer_360"],
        )

    monkeypatch.setattr(
        iceberg_outputs.CompiledArtifacts,
        "model_validate_json",
        model_validate_json,
    )
    monkeypatch.setattr(iceberg_outputs, "reset_iceberg_outputs", reset_outputs)
    monkeypatch.setattr(iceberg_outputs, "validate_iceberg_outputs", validate_outputs)

    assert (
        iceberg_outputs._main(
            [
                "--artifacts-path",
                str(artifacts_path),
                "--expected-table",
                "mart_customer_360",
                "--reset-only",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert [name for name, _value in calls] == ["load", "reset"]
    assert payload["action"] == "reset"
    assert payload["recovery_mode"] == "reset"
    assert payload["dropped_tables"] == ["customer_360.mart_customer_360"]
    assert payload["tables_validated"] == 0
