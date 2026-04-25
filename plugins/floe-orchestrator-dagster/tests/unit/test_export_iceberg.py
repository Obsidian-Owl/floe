"""Unit tests for Iceberg export extraction (AC-4).

Tests verify that export_dbt_to_iceberg():
- Accepts context, product_name, project_dir, and artifacts parameters
- Derives duckdb_path from product_name (safe_name conversion)
- Derives product_namespace from product_name (safe_name conversion)
- Does NOT re-read compiled_artifacts.json from disk
- Handles missing DuckDB file gracefully
- Handles missing catalog plugin gracefully
- Creates namespace in Iceberg catalog
- Writes non-empty DuckDB tables to Iceberg
- Skips unsafe SQL identifiers
- Skips empty tables

Test type rationale: Unit test -- pure function behavior with external
dependencies (duckdb, pyiceberg, plugin_registry) mocked. No boundary
crossing; all assertions verify behavioral outcomes.
"""

from __future__ import annotations

import builtins
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow as pa
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

from floe_orchestrator_dagster.export.iceberg import export_dbt_to_iceberg

# ---------------------------------------------------------------------------
# Shared helpers and constants
# ---------------------------------------------------------------------------

PRODUCT_NAME = "customer-360"
SAFE_NAME = "customer_360"
EXPECTED_DUCKDB_PATH = f"/tmp/{SAFE_NAME}.duckdb"


def _make_artifacts(
    catalog: PluginRef | None = None,
    storage: PluginRef | None = None,
) -> CompiledArtifacts:
    """Build a minimal valid CompiledArtifacts with optional catalog/storage.

    Args:
        catalog: Optional catalog PluginRef.
        storage: Optional storage PluginRef.

    Returns:
        A valid CompiledArtifacts instance.
    """
    return CompiledArtifacts(
        version="0.5.0",
        metadata=CompilationMetadata(
            compiled_at=datetime.now(timezone.utc),
            floe_version="0.5.0",
            source_hash="sha256:abc123def456",
            product_name=PRODUCT_NAME,
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
            catalog=catalog,
            storage=storage,
        ),
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name="stg_customers", compute="duckdb")],
            default_compute="duckdb",
        ),
    )


def _make_context() -> MagicMock:
    """Create a mock Dagster context with a log attribute.

    Returns:
        MagicMock with log.info, log.warning, log.debug configured.
    """
    ctx = MagicMock()
    ctx.log = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def context() -> MagicMock:
    """Dagster-like context with mock logger."""
    return _make_context()


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Temporary project directory."""
    return tmp_path / "dbt_project"


@pytest.fixture
def artifacts_with_catalog() -> CompiledArtifacts:
    """CompiledArtifacts with catalog and storage plugins configured."""
    return _make_artifacts(
        catalog=PluginRef(
            type="polaris",
            version="0.1.0",
            config={"uri": "http://polaris:8181"},
        ),
        storage=PluginRef(
            type="s3",
            version="1.0.0",
            config={"endpoint": "http://minio:9000", "access-key-id": "test"},
        ),
    )


@pytest.fixture
def artifacts_no_catalog() -> CompiledArtifacts:
    """CompiledArtifacts with no catalog plugin."""
    return _make_artifacts(catalog=None, storage=None)


@pytest.fixture
def artifacts_catalog_only() -> CompiledArtifacts:
    """CompiledArtifacts with catalog but no storage plugin."""
    return _make_artifacts(
        catalog=PluginRef(
            type="polaris",
            version="0.1.0",
            config={"uri": "http://polaris:8181"},
        ),
        storage=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExportDbtToIceberg:
    """Tests for export_dbt_to_iceberg function (AC-4)."""

    @pytest.mark.requirement("AC-4")
    def test_export_derives_duckdb_path_from_product_name(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """DuckDB path MUST be /tmp/{safe_name}.duckdb where safe_name
        replaces hyphens with underscores in product_name.

        A sloppy implementation might hardcode the path or ignore
        product_name. We verify the exact path is used by intercepting
        the Path.exists() check or duckdb.connect() call.
        """
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []

        with (
            patch("duckdb.connect", return_value=mock_conn) as mock_duckdb_connect,
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=MagicMock(),
            ),
        ):
            # Set up registry mock chain
            registry = MagicMock()
            catalog_plugin = MagicMock()
            catalog_instance = MagicMock()
            catalog_instance.create_namespace = MagicMock()
            registry.get.return_value = catalog_plugin
            registry.configure.return_value = {}

            with patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ):
                export_dbt_to_iceberg(
                    context=context,
                    product_name=PRODUCT_NAME,
                    project_dir=project_dir,
                    artifacts=artifacts_with_catalog,
                )

            # Assert duckdb.connect was called with the correctly derived path
            mock_duckdb_connect.assert_called_once()
            actual_path = mock_duckdb_connect.call_args[0][0]
            assert actual_path == EXPECTED_DUCKDB_PATH, (
                f"Expected DuckDB path '{EXPECTED_DUCKDB_PATH}', got '{actual_path}'. "
                "Function must derive path from product_name with hyphen-to-underscore."
            )

    @pytest.mark.requirement("AC-4")
    def test_export_derives_namespace_from_product_name(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Iceberg namespace MUST be derived from product_name as safe_name
        (hyphens replaced with underscores).

        A sloppy implementation might hardcode 'customer_360' or read it
        from somewhere else. We test with a DIFFERENT product_name to
        catch hardcoding.
        """
        different_name = "my-analytics-pipeline"
        expected_namespace = "my_analytics_pipeline"

        artifacts = _make_artifacts(
            catalog=PluginRef(
                type="polaris",
                version="0.1.0",
                config={"uri": "http://polaris:8181"},
            ),
            storage=PluginRef(
                type="s3",
                version="1.0.0",
                config={"endpoint": "http://minio:9000"},
            ),
        )

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_catalog = MagicMock()

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = mock_catalog
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=different_name,
                project_dir=project_dir,
                artifacts=artifacts,
            )

        # Assert namespace was created with the correctly derived name
        mock_catalog.create_namespace.assert_called()
        ns_arg = mock_catalog.create_namespace.call_args[0][0]
        assert ns_arg == expected_namespace, (
            f"Expected namespace '{expected_namespace}', got '{ns_arg}'. "
            "Namespace must be derived from product_name, not hardcoded."
        )

    @pytest.mark.requirement("AC-4")
    def test_export_does_not_read_artifacts_from_disk(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Function MUST use the artifacts parameter, NOT re-read from disk.

        We mock Path.read_text and json.loads/model_validate_json to ensure
        compiled_artifacts.json is never read. If the function reads from
        disk, the mock will record it.
        """
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_catalog = MagicMock()
        mock_plugin.connect.return_value = mock_catalog
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
            patch.object(
                Path,
                "read_text",
                side_effect=AssertionError("MUST NOT read compiled_artifacts.json from disk"),
            ),
            patch.object(
                CompiledArtifacts,
                "model_validate_json",
                side_effect=AssertionError(
                    "MUST NOT call model_validate_json — use the artifacts param"
                ),
            ),
        ):
            # Should succeed using the passed-in artifacts object
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

    @pytest.mark.requirement("AC-4")
    def test_export_skips_when_duckdb_missing(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """When DuckDB file does not exist, function MUST return without
        error and log a warning. It must NOT attempt duckdb.connect().
        """
        with (
            patch.object(Path, "exists", return_value=False),
            patch("duckdb.connect") as mock_connect,
        ):
            # Should not raise
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        # Must NOT attempt to connect to DuckDB
        mock_connect.assert_not_called()

        # Must log a warning about missing DuckDB
        context.log.warning.assert_called()
        warning_msg = str(context.log.warning.call_args)
        assert "duckdb" in warning_msg.lower() or "DuckDB" in warning_msg, (
            "Warning message must mention DuckDB file not found"
        )

    @pytest.mark.requirement("AC-4")
    def test_export_skips_when_no_catalog_configured(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_no_catalog: CompiledArtifacts,
    ) -> None:
        """When artifacts.plugins.catalog is None, function MUST return
        without error and without attempting any Iceberg operations.
        """
        with (
            patch.object(Path, "exists", return_value=True),
            patch("duckdb.connect") as mock_connect,
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_no_catalog,
            )

        # Must NOT connect to DuckDB (no point if no catalog)
        mock_connect.assert_not_called()

    @pytest.mark.requirement("AC-4")
    def test_export_skips_when_catalog_configured_without_storage(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_catalog_only: CompiledArtifacts,
    ) -> None:
        """Catalog-only artifacts MUST skip before optional export dependencies load."""
        real_import = builtins.__import__

        def fail_optional_export_imports(name: str, *args: object, **kwargs: object) -> object:
            if name == "duckdb" or name.startswith("pyiceberg"):
                raise AssertionError(f"optional export dependency imported: {name}")
            return real_import(name, *args, **kwargs)

        with (
            patch.object(Path, "exists", return_value=True) as mock_exists,
            patch("floe_core.plugin_registry.get_registry") as mock_get_registry,
            patch("builtins.__import__", side_effect=fail_optional_export_imports),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_catalog_only,
            )

        mock_exists.assert_not_called()
        mock_get_registry.assert_not_called()
        context.log.info.assert_called()

    @pytest.mark.requirement("AC-4")
    def test_export_creates_namespace(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Function MUST call create_namespace with the derived safe_name."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_catalog = MagicMock()

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = mock_catalog
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        mock_plugin.assert_not_called()
        mock_catalog.create_namespace.assert_called_once_with(SAFE_NAME)

    @pytest.mark.requirement("AC-4")
    def test_export_writes_to_iceberg(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Function MUST write non-empty DuckDB tables to Iceberg.

        For existing tables: overwrite.
        For new tables: create_table + append.
        We test both paths.
        """
        from pyiceberg.exceptions import NoSuchTableError

        # Simulate DuckDB with one table
        arrow_table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("main", "customers"),
        ]
        # Second execute call (SELECT * FROM ...) returns arrow table
        mock_conn.execute.return_value.fetch_arrow_table.return_value = arrow_table

        # Simulate NoSuchTableError on first load (new table)
        mock_catalog = MagicMock()
        mock_iceberg_table = MagicMock()
        mock_catalog.load_table.side_effect = NoSuchTableError("not found")
        mock_catalog.create_table.return_value = mock_iceberg_table

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = mock_catalog
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        # Verify create_table was called with correct identifier
        mock_catalog.create_table.assert_called_once()
        table_id = mock_catalog.create_table.call_args[0][0]
        assert table_id == f"{SAFE_NAME}.customers", (
            f"Expected Iceberg table ID '{SAFE_NAME}.customers', got '{table_id}'"
        )

        # Verify data was appended to the new table
        mock_iceberg_table.append.assert_called_once()
        appended_data = mock_iceberg_table.append.call_args[0][0]
        assert appended_data.num_rows == 3, (
            f"Expected 3 rows appended, got {appended_data.num_rows}"
        )

    @pytest.mark.requirement("AC-4")
    def test_export_overwrites_existing_iceberg_table(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """When Iceberg table already exists, function MUST overwrite it."""
        arrow_table = pa.table({"id": [1, 2], "value": [10, 20]})
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("main", "orders"),
        ]
        mock_conn.execute.return_value.fetch_arrow_table.return_value = arrow_table

        # Simulate existing table (load_table succeeds)
        mock_catalog = MagicMock()
        mock_existing_table = MagicMock()
        mock_catalog.load_table.return_value = mock_existing_table

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = mock_catalog
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        # Verify overwrite was called, NOT create_table
        mock_existing_table.overwrite.assert_called_once()
        overwritten_data = mock_existing_table.overwrite.call_args[0][0]
        assert overwritten_data.num_rows == 2, (
            f"Expected 2 rows overwritten, got {overwritten_data.num_rows}"
        )
        mock_catalog.create_table.assert_not_called()

    @pytest.mark.requirement("AC-4")
    def test_export_skips_unsafe_identifiers(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Tables with unsafe SQL identifiers (special chars, SQL injection
        attempts) MUST be skipped with a warning log.
        """
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("main", "safe_table"),
            ("main", "unsafe;DROP TABLE"),
            ("main", "also-unsafe!"),
            ("Robert'); DROP TABLE students;--", "xkcd"),
        ]
        # Only safe_table should be processed
        arrow_table = pa.table({"id": [1]})
        mock_conn.execute.return_value.fetch_arrow_table.return_value = arrow_table

        mock_catalog = MagicMock()
        mock_iceberg_table = MagicMock()
        mock_catalog.load_table.return_value = mock_iceberg_table

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = mock_catalog
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        # Only the safe table should have been loaded/written
        # Exactly one table should be processed (safe_table)
        load_calls = mock_catalog.load_table.call_args_list
        assert len(load_calls) == 1, (
            f"Expected exactly 1 load_table call (safe_table only), got {len(load_calls)}"
        )
        assert f"{SAFE_NAME}.safe_table" in str(load_calls[0])

        # Warning should have been logged for unsafe identifiers
        assert context.log.warning.call_count >= 3, (
            f"Expected at least 3 warnings for unsafe identifiers, "
            f"got {context.log.warning.call_count}"
        )

    @pytest.mark.requirement("AC-4")
    def test_export_skips_empty_tables(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Tables with 0 rows MUST be skipped -- no Iceberg write should occur."""
        empty_table = pa.table({"id": pa.array([], type=pa.int64())})
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("main", "empty_table"),
        ]
        mock_conn.execute.return_value.fetch_arrow_table.return_value = empty_table

        mock_catalog = MagicMock()

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = mock_catalog
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        # No Iceberg writes should have occurred
        mock_catalog.load_table.assert_not_called()
        mock_catalog.create_table.assert_not_called()

    @pytest.mark.requirement("AC-4")
    def test_export_uses_catalog_config_from_artifacts_not_from_disk(
        self,
        context: MagicMock,
        project_dir: Path,
    ) -> None:
        """Catalog config MUST come from the artifacts parameter.

        We pass artifacts with a specific catalog URI and verify that
        exact config is used for registry.configure(), proving it reads
        from the object, not from disk.
        """
        specific_uri = "http://my-specific-polaris:9999"
        artifacts = _make_artifacts(
            catalog=PluginRef(
                type="polaris",
                version="0.1.0",
                config={"uri": specific_uri},
            ),
            storage=PluginRef(
                type="s3",
                version="1.0.0",
                config={"endpoint": "http://minio:9000"},
            ),
        )

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = MagicMock()
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts,
            )

        # Verify the specific URI from artifacts was passed to configure
        registry.configure.assert_called_once()
        config_arg = registry.configure.call_args
        # The config dict passed must contain our specific URI
        actual_config = (
            config_arg[0][2] if len(config_arg[0]) > 2 else config_arg[1].get("config", {})
        )
        assert actual_config.get("uri") == specific_uri, (
            f"Expected catalog config URI '{specific_uri}', got '{actual_config}'. "
            "Function must read catalog config from artifacts parameter."
        )

    @pytest.mark.requirement("AC-4")
    def test_export_closes_duckdb_connection_on_success(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """DuckDB connection MUST be closed after export, even on success."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = MagicMock()
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        mock_conn.close.assert_called_once()

    @pytest.mark.requirement("AC-4")
    def test_export_closes_duckdb_connection_on_error(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """DuckDB connection MUST be closed even if an error occurs during export."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = RuntimeError("query failed")

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = MagicMock()
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            with pytest.raises(RuntimeError, match="query failed"):
                export_dbt_to_iceberg(
                    context=context,
                    product_name=PRODUCT_NAME,
                    project_dir=project_dir,
                    artifacts=artifacts_with_catalog,
                )

        mock_conn.close.assert_called_once()

    @pytest.mark.requirement("AC-4")
    def test_export_reads_duckdb_in_readonly_mode(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """DuckDB MUST be opened in read-only mode to prevent accidental writes."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = MagicMock()
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn) as mock_duckdb_connect,
            patch.object(Path, "exists", return_value=True),
            patch(
                "floe_core.plugin_registry.get_registry",
                return_value=registry,
            ),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        mock_duckdb_connect.assert_called_once()
        call_kwargs = mock_duckdb_connect.call_args
        # read_only should be True (positional arg 2 or keyword)
        if len(call_kwargs[0]) > 1:
            assert call_kwargs[0][1] is True, "DuckDB must be opened read_only=True"
        else:
            assert call_kwargs[1].get("read_only") is True, (
                "DuckDB must be opened with read_only=True"
            )
