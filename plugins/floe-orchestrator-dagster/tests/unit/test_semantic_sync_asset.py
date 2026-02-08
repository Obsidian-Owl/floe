"""Unit tests for sync_semantic_schemas Dagster asset.

Tests the asset execution logic including config extraction, OTel tracing
fallback, and plugin delegation.

Requirements:
    T049: sync_semantic_schemas asset
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dagster import build_op_context


@pytest.mark.requirement("T049")
def test_sync_delegates_to_semantic_plugin() -> None:
    """Test asset delegates sync to semantic_layer plugin."""
    from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

    # Mock the semantic layer plugin
    mock_plugin = MagicMock()
    mock_plugin.sync_from_dbt_manifest.return_value = [
        Path("cube/schema/orders.yaml"),
        Path("cube/schema/customers.yaml"),
    ]

    # Create context using Dagster's build_op_context
    context = build_op_context(
        op_config=None, resources={"semantic_layer": mock_plugin}
    )

    # Call the asset - pass resource as second argument for testing
    result = sync_semantic_schemas(context, mock_plugin)

    assert result == ["cube/schema/orders.yaml", "cube/schema/customers.yaml"]
    mock_plugin.sync_from_dbt_manifest.assert_called_once()


@pytest.mark.requirement("T049")
def test_sync_uses_default_paths_when_no_config() -> None:
    """Test asset uses default manifest_path and output_dir when no config."""
    from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

    mock_plugin = MagicMock()
    mock_plugin.sync_from_dbt_manifest.return_value = []

    context = build_op_context(
        op_config=None, resources={"semantic_layer": mock_plugin}
    )

    sync_semantic_schemas(context, mock_plugin)

    call_args = mock_plugin.sync_from_dbt_manifest.call_args
    assert call_args.kwargs["manifest_path"] == Path("target/manifest.json")
    assert call_args.kwargs["output_dir"] == Path("cube/schema")


@pytest.mark.requirement("T049")
def test_sync_uses_config_paths_when_provided() -> None:
    """Test asset uses paths from op_config when provided."""
    from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

    mock_plugin = MagicMock()
    mock_plugin.sync_from_dbt_manifest.return_value = []

    op_config = {
        "manifest_path": "/custom/manifest.json",
        "output_dir": "/custom/output",
    }

    context = build_op_context(
        op_config=op_config, resources={"semantic_layer": mock_plugin}
    )

    sync_semantic_schemas(context, mock_plugin)

    call_args = mock_plugin.sync_from_dbt_manifest.call_args
    assert call_args.kwargs["manifest_path"] == Path("/custom/manifest.json")
    assert call_args.kwargs["output_dir"] == Path("/custom/output")


@pytest.mark.requirement("T049")
def test_sync_propagates_file_not_found_error() -> None:
    """Test asset propagates FileNotFoundError from plugin."""
    from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

    mock_plugin = MagicMock()
    mock_plugin.sync_from_dbt_manifest.side_effect = FileNotFoundError(
        "manifest.json not found"
    )

    context = build_op_context(
        op_config=None, resources={"semantic_layer": mock_plugin}
    )

    with pytest.raises(FileNotFoundError, match="manifest.json not found"):
        sync_semantic_schemas(context, mock_plugin)


@pytest.mark.requirement("T049")
def test_sync_returns_empty_list_when_no_models() -> None:
    """Test asset returns empty list when plugin generates no files."""
    from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

    mock_plugin = MagicMock()
    mock_plugin.sync_from_dbt_manifest.return_value = []

    context = build_op_context(
        op_config=None, resources={"semantic_layer": mock_plugin}
    )

    result = sync_semantic_schemas(context, mock_plugin)

    assert result == []


@pytest.mark.requirement("T049")
def test_sync_converts_path_objects_to_strings() -> None:
    """Test asset converts Path objects to strings in return value."""
    from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

    mock_plugin = MagicMock()
    mock_plugin.sync_from_dbt_manifest.return_value = [
        Path("cube/schema/orders.yaml"),
        Path("cube/schema/customers.yaml"),
        Path("cube/schema/products.yaml"),
    ]

    context = build_op_context(
        op_config=None, resources={"semantic_layer": mock_plugin}
    )

    result = sync_semantic_schemas(context, mock_plugin)

    # All results should be strings, not Path objects
    assert all(isinstance(path, str) for path in result)
    assert result == [
        "cube/schema/orders.yaml",
        "cube/schema/customers.yaml",
        "cube/schema/products.yaml",
    ]


@pytest.mark.requirement("T049")
def test_sync_with_otel_tracing() -> None:
    """Test asset creates OTel span via core tracer factory."""
    from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

    mock_plugin = MagicMock()
    mock_plugin.sync_from_dbt_manifest.return_value = [
        Path("cube/schema/orders.yaml"),
    ]

    # Mock the core tracer factory
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
    mock_tracer.start_as_current_span.return_value.__exit__.return_value = None

    with patch(
        "floe_orchestrator_dagster.assets.semantic_sync._get_tracer"
    ) as mock_get_tracer:
        mock_get_tracer.return_value = mock_tracer

        context = build_op_context(
            op_config=None, resources={"semantic_layer": mock_plugin}
        )

        result = sync_semantic_schemas(context, mock_plugin)

    # Verify tracer factory was called with orchestrator tracer name
    mock_get_tracer.assert_called_once_with("floe.orchestrator.semantic")

    # Verify span was created with standard attributes
    mock_tracer.start_as_current_span.assert_called_once_with(
        "floe.orchestrator.sync_semantic_schemas",
        attributes={
            "semantic.manifest_path": "target/manifest.json",
            "semantic.output_dir": "cube/schema",
        },
    )

    # Verify generated file count attribute was set
    mock_span.set_attribute.assert_any_call("semantic.generated_file_count", 1)

    assert result == ["cube/schema/orders.yaml"]


@pytest.mark.requirement("T049")
def test_sync_logs_info_messages(caplog: pytest.LogCaptureFixture) -> None:
    """Test asset logs informational messages."""
    import logging

    from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

    mock_plugin = MagicMock()
    mock_plugin.sync_from_dbt_manifest.return_value = [
        Path("cube/schema/orders.yaml"),
    ]

    with caplog.at_level(logging.INFO):
        context = build_op_context(
            op_config=None, resources={"semantic_layer": mock_plugin}
        )
        sync_semantic_schemas(context, mock_plugin)

    # Verify structured logger
    assert any(
        "Semantic schema sync completed" in record.message for record in caplog.records
    )


@pytest.mark.requirement("T049")
def test_sync_handles_partial_config() -> None:
    """Test asset handles partial config with only one key provided."""
    from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas

    mock_plugin = MagicMock()
    mock_plugin.sync_from_dbt_manifest.return_value = []

    # Config with only manifest_path
    op_config = {"manifest_path": "/custom/manifest.json"}
    context = build_op_context(
        op_config=op_config, resources={"semantic_layer": mock_plugin}
    )

    sync_semantic_schemas(context, mock_plugin)

    call_args = mock_plugin.sync_from_dbt_manifest.call_args
    assert call_args.kwargs["manifest_path"] == Path("/custom/manifest.json")
    assert call_args.kwargs["output_dir"] == Path("cube/schema")  # Default

    # Reset and try with only output_dir
    mock_plugin.reset_mock()
    op_config = {"output_dir": "/custom/output"}
    context = build_op_context(
        op_config=op_config, resources={"semantic_layer": mock_plugin}
    )

    sync_semantic_schemas(context, mock_plugin)

    call_args = mock_plugin.sync_from_dbt_manifest.call_args
    assert call_args.kwargs["manifest_path"] == Path("target/manifest.json")  # Default
    assert call_args.kwargs["output_dir"] == Path("/custom/output")
