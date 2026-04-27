"""Unit tests for Iceberg export extraction (AC-4).

Tests verify that export_dbt_to_iceberg():
- Accepts context, product_name, project_dir, and artifacts parameters
- Derives duckdb_path from compiled dbt profile config
- Derives product_namespace from product_name (safe_name conversion)
- Does NOT re-read compiled_artifacts.json from disk
- Raises for missing DuckDB output when catalog+storage export is configured
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
    ResolvedGovernance,
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
    dbt_profiles: dict[str, object] | None = None,
) -> CompiledArtifacts:
    """Build a minimal valid CompiledArtifacts with optional catalog/storage.

    Args:
        catalog: Optional catalog PluginRef.
        storage: Optional storage PluginRef.
        dbt_profiles: Optional compiled dbt profiles content.

    Returns:
        A valid CompiledArtifacts instance.
    """
    profiles = dbt_profiles or {
        PRODUCT_NAME: {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "duckdb",
                    "path": EXPECTED_DUCKDB_PATH,
                }
            },
        }
    }
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
        dbt_profiles=profiles,
    )


def _make_context() -> MagicMock:
    """Create a mock Dagster context with a log attribute.

    Returns:
        MagicMock with log.info, log.warning, log.debug configured.
    """
    ctx = MagicMock()
    ctx.log = MagicMock()
    return ctx


def _configure_mock_duckdb_table(
    mock_conn: MagicMock,
    table_name: str = "customers",
) -> None:
    """Configure a DuckDB mock with one non-empty exportable table."""
    mock_conn.execute.return_value.fetchall.return_value = [("main", table_name)]
    mock_conn.execute.return_value.fetch_arrow_table.return_value = pa.table({"id": [1]})


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
def artifacts_with_catalog_none_config() -> CompiledArtifacts:
    """CompiledArtifacts with configured catalog/storage refs and config=None."""
    return _make_artifacts(
        catalog=PluginRef(type="polaris", version="0.1.0", config=None),
        storage=PluginRef(type="s3", version="1.0.0", config=None),
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
    def test_export_resolves_duckdb_path_from_compiled_dbt_profile(
        self,
        context: MagicMock,
        project_dir: Path,
    ) -> None:
        """DuckDB path must come from compiled dbt profile config, not convention."""
        custom_duckdb_path = "/var/floe/custom-output.duckdb"
        artifacts = _make_artifacts(
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
            dbt_profiles={
                PRODUCT_NAME: {
                    "target": "custom",
                    "outputs": {
                        "custom": {
                            "type": "duckdb",
                            "path": custom_duckdb_path,
                        }
                    },
                }
            },
        )
        mock_conn = MagicMock()
        _configure_mock_duckdb_table(mock_conn)

        registry = MagicMock()
        catalog_plugin = MagicMock()
        registry.get.return_value = catalog_plugin
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
                artifacts=artifacts,
            )

        mock_duckdb_connect.assert_called_once()
        actual_path = mock_duckdb_connect.call_args[0][0]
        assert actual_path == custom_duckdb_path

    @pytest.mark.requirement("AC-4")
    def test_export_resolves_relative_duckdb_profile_path_under_project_dir(
        self,
        context: MagicMock,
        project_dir: Path,
    ) -> None:
        """Relative DuckDB profile paths must resolve against the dbt project dir."""
        relative_path = "target/custom.duckdb"
        artifacts = _make_artifacts(
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
            dbt_profiles={
                PRODUCT_NAME: {
                    "target": "dev",
                    "outputs": {
                        "dev": {
                            "type": "duckdb",
                            "path": relative_path,
                        }
                    },
                }
            },
        )
        mock_conn = MagicMock()
        _configure_mock_duckdb_table(mock_conn)

        registry = MagicMock()
        catalog_plugin = MagicMock()
        registry.get.return_value = catalog_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn) as mock_duckdb_connect,
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts,
            )

        mock_duckdb_connect.assert_called_once_with(
            str((project_dir / relative_path).resolve()),
            read_only=True,
        )

    @pytest.mark.requirement("AC-4")
    def test_export_rejects_memory_duckdb_profile_for_configured_iceberg_export(
        self,
        context: MagicMock,
        project_dir: Path,
    ) -> None:
        """Iceberg export requires persisted DuckDB output, not an in-memory profile."""
        artifacts = _make_artifacts(
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
            dbt_profiles={
                PRODUCT_NAME: {
                    "target": "dev",
                    "outputs": {
                        "dev": {
                            "type": "duckdb",
                            "path": ":memory:",
                        }
                    },
                }
            },
        )
        registry = MagicMock()
        registry.get.return_value = MagicMock()
        registry.configure.return_value = {}

        with (
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
            pytest.raises(RuntimeError, match="file-backed DuckDB profile path"),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts,
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
        _configure_mock_duckdb_table(mock_conn)
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
        _configure_mock_duckdb_table(mock_conn)

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
    def test_configured_export_validates_plugins_before_missing_duckdb_failure(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Configured export validates catalog/storage before failing on missing DuckDB."""
        from floe_core.plugin_types import PluginType

        registry = MagicMock()
        catalog_plugin = MagicMock()
        storage_plugin = MagicMock()

        def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> MagicMock:
            if plugin_type is PluginType.CATALOG:
                return catalog_plugin
            return storage_plugin

        registry.get.side_effect = get_side_effect
        registry.configure.return_value = {}

        real_import = builtins.__import__

        def fail_optional_export_imports(name: str, *args: object, **kwargs: object) -> object:
            if name == "duckdb" or name.startswith("pyiceberg"):
                raise AssertionError(f"optional export dependency imported: {name}")
            return real_import(name, *args, **kwargs)

        with (
            patch.object(Path, "exists", return_value=False),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
            patch("builtins.__import__", side_effect=fail_optional_export_imports),
            pytest.raises(RuntimeError, match=EXPECTED_DUCKDB_PATH),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        registry.configure.assert_any_call(
            PluginType.CATALOG,
            "polaris",
            {"uri": "http://polaris:8181"},
        )
        registry.configure.assert_any_call(
            PluginType.STORAGE,
            "s3",
            {"endpoint": "http://minio:9000", "access-key-id": "test"},
        )
        catalog_plugin.connect.assert_not_called()

    @pytest.mark.requirement("AC-4")
    def test_export_fails_when_catalog_configured_but_duckdb_file_missing(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Configured Iceberg export must fail loudly when DuckDB output is absent."""
        registry = MagicMock()
        catalog_plugin = MagicMock()
        storage_plugin = MagicMock()

        from floe_core.plugin_types import PluginType

        def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> MagicMock:
            if plugin_type is PluginType.CATALOG:
                return catalog_plugin
            return storage_plugin

        registry.get.side_effect = get_side_effect
        registry.configure.return_value = {}

        with (
            patch.object(Path, "exists", return_value=False),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
            pytest.raises(RuntimeError, match="DuckDB output file is missing"),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        catalog_plugin.connect.assert_not_called()

    @pytest.mark.requirement("AC-4")
    def test_export_configures_none_configs_as_empty_dict(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog_none_config: CompiledArtifacts,
    ) -> None:
        """Configured catalog/storage refs with config=None are validated as {}."""
        from floe_core.plugin_types import PluginType

        registry = MagicMock()
        catalog_plugin = MagicMock()
        storage_plugin = MagicMock()

        def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> MagicMock:
            if plugin_type is PluginType.CATALOG:
                return catalog_plugin
            return storage_plugin

        registry.get.side_effect = get_side_effect
        registry.configure.return_value = {}

        with (
            patch.object(Path, "exists", return_value=False),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
            pytest.raises(RuntimeError, match=EXPECTED_DUCKDB_PATH),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog_none_config,
            )

        registry.configure.assert_any_call(PluginType.CATALOG, "polaris", {})
        registry.configure.assert_any_call(PluginType.STORAGE, "s3", {})
        catalog_plugin.connect.assert_not_called()

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
        _configure_mock_duckdb_table(mock_conn)
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
    def test_export_fails_when_catalog_lacks_write_methods(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Configured export requires a write-capable Iceberg catalog."""

        class ReadOnlyCatalog:
            def list_namespaces(self) -> list[tuple[str, ...]]:
                return []

            def list_tables(self, namespace: str) -> list[str]:
                return []

            def load_table(self, identifier: str) -> object:
                return object()

        mock_conn = MagicMock()
        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = ReadOnlyCatalog()
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn) as mock_duckdb_connect,
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
            pytest.raises(RuntimeError, match="write-capable Iceberg catalog"),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        mock_duckdb_connect.assert_not_called()

    @pytest.mark.requirement("AC-4")
    def test_export_namespace_non_idempotent_error_raises(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Non-idempotent namespace creation errors must fail configured export."""
        mock_conn = MagicMock()
        mock_catalog = MagicMock()
        mock_catalog.create_namespace.side_effect = RuntimeError("permission denied")

        registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.connect.return_value = mock_catalog
        registry.get.return_value = mock_plugin
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn) as mock_duckdb_connect,
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
            pytest.raises(RuntimeError, match="permission denied"),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        mock_catalog.create_namespace.assert_called_once_with(SAFE_NAME)
        mock_duckdb_connect.assert_not_called()

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
    def test_export_returns_written_table_count(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Configured export result must prove which Iceberg tables were written."""
        arrow_table = pa.table({"id": [1, 2, 3]})
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("main", "customers"),
        ]
        mock_conn.execute.return_value.fetch_arrow_table.return_value = arrow_table

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
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
        ):
            result = export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        assert result.tables_written == 1
        assert result.table_names == [f"{SAFE_NAME}.customers"]

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
    def test_export_overwrite_uses_endpoint_preserving_catalog_plugin_loader(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Existing table overwrite must use plugin endpoint-preserving load hook."""
        from floe_core.plugin_types import PluginType

        arrow_table = pa.table({"id": [1], "value": [10]})
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("main", "orders"),
        ]
        mock_conn.execute.return_value.fetch_arrow_table.return_value = arrow_table

        mock_catalog = MagicMock()
        mock_catalog.load_table.side_effect = AssertionError(
            "overwrite must not bypass endpoint-preserving plugin load"
        )
        mock_existing_table = MagicMock()

        class EndpointPreservingCatalogPlugin:
            def __init__(self) -> None:
                self.connect = MagicMock(return_value=mock_catalog)
                self.load_table_with_client_endpoint = MagicMock(return_value=mock_existing_table)

        registry = MagicMock()
        catalog_plugin = EndpointPreservingCatalogPlugin()
        storage_plugin = MagicMock()

        def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> object:
            if plugin_type is PluginType.CATALOG:
                return catalog_plugin
            return storage_plugin

        registry.get.side_effect = get_side_effect
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        catalog_plugin.load_table_with_client_endpoint.assert_called_once_with(
            f"{SAFE_NAME}.orders"
        )
        mock_existing_table.overwrite.assert_called_once_with(arrow_table)
        mock_catalog.create_table.assert_not_called()

    @pytest.mark.requirement("AC-4")
    def test_export_repairs_stale_iceberg_registration_when_configured(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Repair mode drops stale table registration and recreates output table."""
        arrow_table = pa.table({"id": [1], "value": [10]})
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [("main", "orders")]
        mock_conn.execute.return_value.fetch_arrow_table.return_value = arrow_table

        stale_error = RuntimeError(
            "NotFoundException: Location does not exist: "
            "s3://floe-iceberg/customer_360/orders/metadata/00001.metadata.json"
        )
        mock_catalog = MagicMock()
        mock_catalog.load_table.side_effect = stale_error
        recreated_table = MagicMock()
        mock_catalog.create_table.return_value = recreated_table

        registry = MagicMock()
        catalog_plugin = MagicMock()
        storage_plugin = MagicMock()
        catalog_plugin.connect.return_value = mock_catalog
        storage_plugin.get_pyiceberg_catalog_config.return_value = {
            "s3.endpoint": "http://minio:9000"
        }

        def get_side_effect(plugin_type: object, _plugin_name: str) -> MagicMock:
            if str(plugin_type).endswith("CATALOG"):
                return catalog_plugin
            return storage_plugin

        registry.get.side_effect = get_side_effect
        registry.configure.return_value = {}
        artifacts = artifacts_with_catalog.model_copy(
            update={
                "governance": ResolvedGovernance(
                    stale_table_recovery_mode="repair",
                )
            }
        )

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts,
            )

        catalog_plugin.drop_table.assert_called_once_with(
            f"{SAFE_NAME}.orders",
            purge=False,
        )
        mock_catalog.create_table.assert_called_once_with(
            f"{SAFE_NAME}.orders",
            schema=arrow_table.schema,
        )
        recreated_table.append.assert_called_once_with(arrow_table)

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
        """Configured export must fail when all candidate tables are empty."""
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
            pytest.raises(RuntimeError, match="Configured Iceberg export wrote no tables"),
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
        _configure_mock_duckdb_table(mock_conn)

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
        from floe_core.plugin_types import PluginType

        registry.configure.assert_any_call(
            PluginType.CATALOG,
            "polaris",
            {"uri": specific_uri},
        )
        catalog_call = next(
            call for call in registry.configure.call_args_list if call.args[0] is PluginType.CATALOG
        )
        actual_config = catalog_call.args[2]
        assert actual_config.get("uri") == specific_uri, (
            f"Expected catalog config URI '{specific_uri}', got '{actual_config}'. "
            "Function must read catalog config from artifacts parameter."
        )

    @pytest.mark.requirement("AC-4")
    def test_export_configures_catalog_and_storage_before_connect(
        self,
        context: MagicMock,
        project_dir: Path,
    ) -> None:
        """Catalog and storage configs MUST be validated before catalog connect."""
        from floe_core.plugin_types import PluginType

        artifacts = _make_artifacts(
            catalog=PluginRef(type="polaris", version="0.1.0", config={}),
            storage=PluginRef(type="s3", version="1.0.0", config={}),
        )

        mock_conn = MagicMock()
        _configure_mock_duckdb_table(mock_conn)

        registry = MagicMock()
        catalog_plugin = MagicMock()
        storage_plugin = MagicMock()

        def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> MagicMock:
            if plugin_type is PluginType.CATALOG:
                return catalog_plugin
            return storage_plugin

        def connect_side_effect(*_args: object, **_kwargs: object) -> MagicMock:
            registry.configure.assert_any_call(PluginType.CATALOG, "polaris", {})
            registry.configure.assert_any_call(PluginType.STORAGE, "s3", {})
            return MagicMock()

        registry.get.side_effect = get_side_effect
        registry.configure.return_value = {}
        catalog_plugin.connect.side_effect = connect_side_effect

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts,
            )

        assert registry.configure.call_count == 2
        catalog_plugin.connect.assert_called_once()

    @pytest.mark.requirement("AC-4")
    def test_export_passes_storage_catalog_config_to_catalog_connect(
        self,
        context: MagicMock,
        project_dir: Path,
    ) -> None:
        """Export must connect catalog with config produced by StoragePlugin."""
        from floe_core.plugin_types import PluginType

        artifacts = _make_artifacts(
            catalog=PluginRef(type="polaris", version="0.1.0", config={}),
            storage=PluginRef(
                type="s3",
                version="1.0.0",
                config={"endpoint": "http://minio:9000", "path_style_access": True},
            ),
        )
        catalog_config = {
            "s3.endpoint": "http://minio:9000",
            "s3.path-style-access": "true",
        }

        mock_conn = MagicMock()
        _configure_mock_duckdb_table(mock_conn)

        registry = MagicMock()
        catalog_plugin = MagicMock()
        storage_plugin = MagicMock()
        mock_catalog = MagicMock()
        catalog_plugin.connect.return_value = mock_catalog
        storage_plugin.get_pyiceberg_catalog_config.return_value = catalog_config

        def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> MagicMock:
            if plugin_type is PluginType.CATALOG:
                return catalog_plugin
            return storage_plugin

        registry.get.side_effect = get_side_effect
        registry.configure.return_value = {}

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts,
            )

        storage_plugin.get_pyiceberg_catalog_config.assert_called_once_with()
        catalog_plugin.connect.assert_called_once_with(config=catalog_config)

    @pytest.mark.requirement("AC-4")
    @pytest.mark.parametrize(
        ("failing_plugin_type", "expected_message"),
        [("catalog", "invalid catalog config"), ("storage", "invalid storage config")],
    )
    def test_export_configure_validation_exception_propagates(
        self,
        context: MagicMock,
        project_dir: Path,
        failing_plugin_type: str,
        expected_message: str,
    ) -> None:
        """Configured catalog/storage validation failures MUST propagate."""
        from floe_core.plugin_types import PluginType

        artifacts = _make_artifacts(
            catalog=PluginRef(type="polaris", version="0.1.0", config={}),
            storage=PluginRef(type="s3", version="1.0.0", config={}),
        )

        registry = MagicMock()
        catalog_plugin = MagicMock()
        storage_plugin = MagicMock()

        def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> MagicMock:
            if plugin_type is PluginType.CATALOG:
                return catalog_plugin
            return storage_plugin

        def configure_side_effect(
            plugin_type: PluginType,
            _plugin_name: str,
            _config: dict[str, object],
        ) -> dict[str, object]:
            if plugin_type.name.lower() == failing_plugin_type:
                raise ValueError(expected_message)
            return {}

        registry.get.side_effect = get_side_effect
        registry.configure.side_effect = configure_side_effect

        with (
            patch("duckdb.connect") as mock_duckdb_connect,
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
            pytest.raises(ValueError, match=expected_message),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts,
            )

        catalog_plugin.connect.assert_not_called()
        mock_duckdb_connect.assert_not_called()

    @pytest.mark.requirement("AC-4")
    @pytest.mark.parametrize(
        ("none_plugin_type", "expected_message"),
        [
            ("catalog", "Catalog plugin config for polaris"),
            ("storage", "Storage plugin config for s3"),
        ],
    )
    def test_export_configure_returning_none_raises_runtime_error(
        self,
        context: MagicMock,
        project_dir: Path,
        none_plugin_type: str,
        expected_message: str,
    ) -> None:
        """Configured catalog/storage validation returning None MUST fail loudly."""
        from floe_core.plugin_types import PluginType

        artifacts = _make_artifacts(
            catalog=PluginRef(type="polaris", version="0.1.0", config={}),
            storage=PluginRef(type="s3", version="1.0.0", config={}),
        )

        registry = MagicMock()
        catalog_plugin = MagicMock()
        storage_plugin = MagicMock()

        def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> MagicMock:
            if plugin_type is PluginType.CATALOG:
                return catalog_plugin
            return storage_plugin

        def configure_side_effect(
            plugin_type: PluginType,
            _plugin_name: str,
            _config: dict[str, object],
        ) -> dict[str, object] | None:
            if plugin_type.name.lower() == none_plugin_type:
                return None
            return {}

        registry.get.side_effect = get_side_effect
        registry.configure.side_effect = configure_side_effect

        with (
            patch("duckdb.connect") as mock_duckdb_connect,
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
            pytest.raises(RuntimeError, match=expected_message),
        ):
            export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts,
            )

        catalog_plugin.connect.assert_not_called()
        mock_duckdb_connect.assert_not_called()

    @pytest.mark.requirement("AC-4")
    def test_export_closes_duckdb_connection_on_success(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """DuckDB connection MUST be closed after export, even on success."""
        mock_conn = MagicMock()
        _configure_mock_duckdb_table(mock_conn)

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
        _configure_mock_duckdb_table(mock_conn)

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
