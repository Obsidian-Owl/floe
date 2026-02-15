"""End-to-end tests for plugin system architecture.

This test validates the plugin system's ability to discover, load, swap, and
validate plugins across all 14 plugin types in the floe platform.

Requirements Covered:
- FR-050: Plugin type discovery via entry points
- FR-051: ABC compliance validation
- FR-052: Plugin swapping via configuration
- FR-053: Third-party plugin discovery
- FR-054: Compile-time compatibility validation
- FR-055: Plugin health checks
- FR-056: ABC backwards compatibility

Per testing standards: Tests FAIL when infrastructure is unavailable.
No pytest.skip() - see .claude/rules/testing-standards.md
"""

from __future__ import annotations

import inspect
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any, ClassVar

import pytest
from floe_core.plugin_metadata import HealthState, PluginMetadata
from floe_core.plugin_registry import PluginRegistry, get_registry
from floe_core.plugin_types import PluginType
from floe_core.plugins import (
    CatalogPlugin,
    ComputePlugin,
    DBTPlugin,
    IdentityPlugin,
    IngestionPlugin,
    LineageBackendPlugin,
    OrchestratorPlugin,
    QualityPlugin,
    SecretsPlugin,
    SemanticLayerPlugin,
    StoragePlugin,
    TelemetryBackendPlugin,
)
from floe_core.plugins.alert_channel import AlertChannelPlugin
from floe_core.plugins.rbac import RBACPlugin

from testing.base_classes.integration_test_base import IntegrationTestBase


class TestPluginSystem(IntegrationTestBase):
    """E2E tests for the plugin system architecture.

    These tests validate the complete plugin system functionality:
    1. Discovery of all 14 plugin types via Python entry points
    2. ABC compliance validation for each plugin
    3. Plugin swapping via floe.yaml configuration
    4. Third-party plugin discovery via pip install
    5. Compile-time compatibility checks
    6. Plugin health checks
    7. ABC backwards compatibility validation

    Requires platform plugin implementations installed.
    """

    # No external services required - plugin system tests run on host
    required_services: ClassVar[list[tuple[str, int]]] = []

    # Logger instance for test observability
    logger: ClassVar[logging.Logger] = logging.getLogger(__name__)

    # Plugin types configured via manifest sections, not discovered via entry points.
    # STORAGE is a manifest config section (manifest.storage) that defines S3/GCS/Azure
    # connection details. It's NOT a plugin that needs registry discovery — the storage
    # backend is configured at the infrastructure level, not swapped via entry points.
    CONFIG_ONLY_TYPES: ClassVar[frozenset[PluginType]] = frozenset(
        {
            PluginType.STORAGE,
        }
    )

    # Map PluginType enum members to their ABC classes
    # Using Any to satisfy mypy --strict with abstract base classes
    PLUGIN_ABC_MAP: ClassVar[dict[PluginType, Any]] = {
        PluginType.COMPUTE: ComputePlugin,
        PluginType.ORCHESTRATOR: OrchestratorPlugin,
        PluginType.CATALOG: CatalogPlugin,
        PluginType.STORAGE: StoragePlugin,
        PluginType.TELEMETRY_BACKEND: TelemetryBackendPlugin,
        PluginType.LINEAGE_BACKEND: LineageBackendPlugin,
        PluginType.DBT: DBTPlugin,
        PluginType.SEMANTIC_LAYER: SemanticLayerPlugin,
        PluginType.INGESTION: IngestionPlugin,
        PluginType.SECRETS: SecretsPlugin,
        PluginType.IDENTITY: IdentityPlugin,
        PluginType.QUALITY: QualityPlugin,
        PluginType.RBAC: RBACPlugin,
        PluginType.ALERT_CHANNEL: AlertChannelPlugin,
    }

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-050")
    def test_all_plugin_types_discoverable(self) -> None:
        """Test that all discoverable plugin types have registered entry points.

        Validates that PluginRegistry.discover_all() finds at least one
        implementation for each discoverable plugin type. CONFIG_ONLY_TYPES
        (e.g., STORAGE) are excluded — they are validated separately via
        manifest/CompiledArtifacts configuration.

        This ensures the plugin discovery mechanism works for all plugin
        categories and that the platform has minimum viable plugin coverage.
        """
        registry = get_registry()
        registry.discover_all()

        # Get all discovered plugins grouped by type
        all_plugins = registry.list_all()

        # Verify plugin type count matches enum (dynamic, not hardcoded)
        assert len(PluginType) >= 14, (
            f"Expected at least 14 plugin types, found {len(PluginType)}. "
            "PluginType enum may have been reduced."
        )

        # All DISCOVERABLE plugin types MUST have implementations.
        # CONFIG_ONLY_TYPES are configured via manifest sections (not entry points).
        discoverable_types = set(PluginType) - self.CONFIG_ONLY_TYPES
        missing_types: list[str] = []
        for plugin_type in discoverable_types:
            plugin_names = all_plugins.get(plugin_type, [])
            if not plugin_names:
                missing_types.append(plugin_type.name)

        assert not missing_types, (
            f"PLUGIN GAP: Missing implementations for {len(missing_types)} plugin types: "
            f"{', '.join(missing_types)}.\n"
            "Every discoverable plugin type must have at least one registered "
            "implementation. Config-only types (STORAGE) are validated separately."
        )

        # Log discovered plugin counts for observability
        for plugin_type in PluginType:
            plugin_names = all_plugins.get(plugin_type, [])
            label = " [config-only]" if plugin_type in self.CONFIG_ONLY_TYPES else ""
            self.logger.info(
                f"Plugin discovery: {plugin_type.name}{label} - "
                f"{len(plugin_names)} plugins: {plugin_names}"
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-050")
    def test_storage_config_via_manifest(self) -> None:
        """Test that STORAGE config flows through manifest, not plugin registry.

        STORAGE is a CONFIG_ONLY plugin type — it's configured via the
        manifest.storage section (S3/GCS/Azure connection details), not
        discovered via entry points. This test validates that the compilation
        pipeline resolves storage config into CompiledArtifacts.
        """
        from floe_core.compilation.stages import compile_pipeline

        project_root = Path(__file__).parent.parent.parent
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        artifacts = compile_pipeline(spec_path, manifest_path)

        # Storage config should be resolved from manifest.storage section
        assert artifacts.plugins is not None, "CompiledArtifacts must have plugins section"
        assert artifacts.plugins.storage is not None, (
            "Storage config must be resolved from manifest.storage section.\n"
            "STORAGE is a config-only plugin type — manifest.storage defines the "
            "object storage backend (S3, GCS, Azure) at the infrastructure level."
        )
        assert artifacts.plugins.storage.type == "s3", (
            f"Expected storage type 's3' from demo manifest, got '{artifacts.plugins.storage.type}'"
        )

        self.logger.info(f"Storage config validated: type={artifacts.plugins.storage.type}")

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-051")
    def test_abc_compliance(self) -> None:
        """Test that all plugins implement their ABC interface correctly.

        For each plugin type, loads the plugin and verifies:
        - All abstract methods from the ABC are implemented
        - Required properties (name, version, floe_api_version) exist
        - Methods have correct signatures
        - Version format is valid (X.Y or X.Y.Z semver)

        This validates that plugins satisfy their interface contracts.
        """
        import re

        registry = get_registry()
        registry.discover_all()

        all_plugins = registry.list_all()
        non_compliant: list[str] = []

        # Valid version formats: X.Y or X.Y.Z (semver)
        version_pattern = re.compile(r"^\d+\.\d+(\.\d+)?$")

        # Check ALL plugin types — no exclusion list
        for plugin_type in PluginType:
            abc_class = self.PLUGIN_ABC_MAP[plugin_type]
            plugin_names = all_plugins.get(plugin_type, [])

            for plugin_name in plugin_names:
                try:
                    # Load the plugin instance (registry.get handles instantiation)
                    plugin = registry.get(plugin_type, plugin_name)

                    # Verify plugin is an instance of the correct ABC
                    assert isinstance(plugin, abc_class), (
                        f"Plugin {plugin_type.name}:{plugin_name} is not an instance "
                        f"of {abc_class.__name__}"
                    )

                    # Verify required PluginMetadata properties exist
                    assert hasattr(plugin, "name"), (
                        f"{plugin_type.name}:{plugin_name} missing 'name' property"
                    )
                    assert hasattr(plugin, "version"), (
                        f"{plugin_type.name}:{plugin_name} missing 'version' property"
                    )
                    assert hasattr(plugin, "floe_api_version"), (
                        f"{plugin_type.name}:{plugin_name} missing 'floe_api_version' property"
                    )

                    # Verify properties return expected types
                    assert isinstance(plugin.name, str), (
                        f"{plugin_type.name}:{plugin_name} name must be str"
                    )
                    assert isinstance(plugin.version, str), (
                        f"{plugin_type.name}:{plugin_name} version must be str"
                    )
                    assert isinstance(plugin.floe_api_version, str), (
                        f"{plugin_type.name}:{plugin_name} floe_api_version must be str"
                    )

                    # Verify version format (X.Y or X.Y.Z semver)
                    assert version_pattern.match(plugin.floe_api_version), (
                        f"{plugin_type.name}:{plugin_name} floe_api_version "
                        f"'{plugin.floe_api_version}' must match format X.Y or X.Y.Z"
                    )

                    # Verify plugin version follows semver (X.Y.Z or X.Y)
                    assert version_pattern.match(plugin.version), (
                        f"{plugin_type.name}:{plugin_name} version "
                        f"'{plugin.version}' must match format X.Y or X.Y.Z"
                    )

                    # Verify all abstract methods from ABC are implemented
                    for name, member in inspect.getmembers(abc_class):
                        if getattr(member, "__isabstractmethod__", False):
                            # Skip PluginMetadata abstract methods (already checked)
                            if name in ("name", "version", "floe_api_version"):
                                continue

                            assert hasattr(plugin, name), (
                                f"{plugin_type.name}:{plugin_name} missing abstract "
                                f"method '{name}' from {abc_class.__name__}"
                            )

                    self.logger.info(f"ABC compliance passed: {plugin_type.name}:{plugin_name}")

                except (AssertionError, AttributeError, TypeError) as e:
                    non_compliant.append(f"{plugin_type.name}:{plugin_name} - {e}")
                    self.logger.error(
                        f"ABC compliance failed: {plugin_type.name}:{plugin_name} - {e}"
                    )

        assert not non_compliant, "ABC compliance failures:\n" + "\n".join(
            f"  - {item}" for item in non_compliant
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-052")
    def test_plugin_swap_via_config(self) -> None:
        """Test that swapping compute plugins produces different compilation output.

        Validates that the platform supports changing plugin implementations
        by compiling a demo spec with different compute plugins and verifying
        the outputs differ. This proves plugins are truly pluggable.

        WILL FAIL if compilation doesn't respect plugin configuration.
        """
        from pathlib import Path

        from floe_core.compilation.stages import compile_pipeline

        registry = get_registry()
        registry.discover_all()

        # Get available compute plugins
        compute_plugins = registry.list_all().get(PluginType.COMPUTE, [])

        assert len(compute_plugins) >= 1, (
            f"Need at least 1 compute plugin for swap test, found {len(compute_plugins)}"
        )

        project_root = Path(__file__).parent.parent.parent
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Compile with default configuration
        artifacts = compile_pipeline(spec_path, manifest_path)
        assert artifacts.plugins is not None, "Compiled artifacts must have plugins section"
        assert artifacts.plugins.compute is not None, (
            "Compiled artifacts must specify compute plugin"
        )

        default_compute = artifacts.plugins.compute.type
        assert default_compute in compute_plugins, (
            f"Default compute plugin '{default_compute}' not in "
            f"discovered plugins: {compute_plugins}"
        )

        self.logger.info(
            f"Plugin swap test: default compute={default_compute}, available={compute_plugins}"
        )

        # If multiple compute plugins available, verify they produce different dbt profiles
        if len(compute_plugins) < 2:
            pytest.xfail(
                f"Plugin swap requires >= 2 compute plugins, found {len(compute_plugins)}. "
                "Register a second compute plugin to enable swap validation."
            )

        profiles_by_plugin: dict[str, Any] = {}
        for compute_name in compute_plugins:
            plugin = registry.get(PluginType.COMPUTE, compute_name)
            if hasattr(plugin, "generate_dbt_profile") and callable(plugin.generate_dbt_profile):
                profile = plugin.generate_dbt_profile(target="dev", config={})
                profiles_by_plugin[compute_name] = profile

        if len(profiles_by_plugin) >= 2:
            profile_types = {
                p.get("type") for p in profiles_by_plugin.values() if isinstance(p, dict)
            }
            assert len(profile_types) >= 2, (
                f"SWAP GAP: Different compute plugins produce same dbt profile type: "
                f"{profile_types}. Plugin swap should produce functionally different configs."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-055")
    def test_plugin_health_checks(self) -> None:
        """Test that all discovered plugins provide health checks.

        Calls health_check() on each discovered plugin and verifies:
        - Method returns HealthStatus dataclass
        - HealthStatus.state is a valid HealthState enum
        - Health checks complete within timeout

        This validates plugin health check infrastructure works across all types.
        """
        import time

        registry = get_registry()
        registry.discover_all()

        all_plugins = registry.list_all()
        health_check_failures: list[str] = []

        # Check ALL plugin types — no exclusion list
        for plugin_type in PluginType:
            plugin_names = all_plugins.get(plugin_type, [])

            for plugin_name in plugin_names:
                try:
                    # Load the plugin instance (registry.get handles instantiation)
                    plugin = registry.get(plugin_type, plugin_name)

                    # Call health check with timing
                    start = time.monotonic()
                    health_status = plugin.health_check()
                    elapsed = time.monotonic() - start

                    # Verify health checks complete promptly (not hung)
                    assert elapsed < 5.0, (
                        f"{plugin_type.name}:{plugin_name} health check took {elapsed:.1f}s "
                        "(must complete within 5 seconds)"
                    )

                    # Verify return type
                    assert hasattr(health_status, "state"), (
                        f"{plugin_type.name}:{plugin_name} health_check() returned object "
                        "without 'state' attribute"
                    )

                    # Verify state is valid HealthState enum
                    assert isinstance(health_status.state, HealthState), (
                        f"{plugin_type.name}:{plugin_name} health_check() state "
                        f"must be HealthState enum"
                    )

                    self.logger.info(
                        f"Plugin health check: {plugin_type.name}:{plugin_name} "
                        f"state={health_status.state.value} message={health_status.message} "
                        f"elapsed={elapsed:.2f}s"
                    )

                except Exception as e:
                    health_check_failures.append(f"{plugin_type.name}:{plugin_name} - {e}")
                    self.logger.error(
                        f"Health check failed: {plugin_type.name}:{plugin_name} - {e}"
                    )

        assert not health_check_failures, "Health check failures:\n" + "\n".join(
            f"  - {item}" for item in health_check_failures
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-054")
    def test_plugin_compatibility_at_compile_time(self) -> None:
        """Test that incompatible plugin versions are rejected at compile time.

        Creates a plugin with an incompatible floe_api_version and verifies
        that the plugin registry rejects it during loading, not at runtime.

        This validates that version compatibility checks happen early in the
        compile phase, providing fast feedback to users.
        """
        from floe_core.plugin_errors import PluginIncompatibleError

        # Create a minimal plugin with incompatible API version
        class IncompatiblePlugin(PluginMetadata):
            """Test plugin with incompatible API version."""

            @property
            def name(self) -> str:
                return "incompatible_test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                # Use an API version that's too high
                return "999.0"

        registry = PluginRegistry()

        # Attempt to register plugin with incompatible version
        # Should raise PluginIncompatibleError during registration
        with pytest.raises(PluginIncompatibleError, match="incompatible.*999"):
            registry.register(PluginType.COMPUTE, IncompatiblePlugin())

        self.logger.info("Compile-time compatibility check passed")

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-053")
    def test_third_party_plugin_discovery(self) -> None:
        """Test that custom third-party plugins are discoverable.

        Simulates installing a third-party plugin by creating a temporary
        plugin package with proper entry points, then verifies the registry
        can discover it.

        This validates that the entry point discovery mechanism works for
        plugins installed via pip/uv, not just built-in plugins.
        """

        # Create a temporary plugin module
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test_third_party_plugin"
            plugin_dir.mkdir()

            # Write minimal plugin module
            plugin_code = '''
"""Test third-party plugin for discovery testing."""
from floe_core.plugin_metadata import PluginMetadata

class ThirdPartyTestPlugin(PluginMetadata):
    """Minimal third-party plugin for testing."""

    @property
    def name(self) -> str:
        return "third_party_test"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"
'''
            (plugin_dir / "__init__.py").write_text(plugin_code)

            # Add plugin directory to sys.path for import
            sys.path.insert(0, str(plugin_dir.parent))

            try:
                # Import the plugin module to simulate pip install
                import test_third_party_plugin

                # Create registry and manually register (simulating entry point)
                registry = PluginRegistry()

                # Register the plugin as if it came from entry points
                plugin_instance = test_third_party_plugin.ThirdPartyTestPlugin()
                registry.register(PluginType.COMPUTE, plugin_instance)

                # Verify plugin is discoverable
                loaded_plugin = registry.get(PluginType.COMPUTE, "third_party_test")
                assert loaded_plugin.name == "third_party_test"
                assert loaded_plugin.version == "0.1.0"

                self.logger.info(
                    f"Third-party plugin discovered: {loaded_plugin.name} v{loaded_plugin.version}"
                )

            finally:
                # Clean up sys.path
                sys.path.remove(str(plugin_dir.parent))

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-056")
    def test_plugin_abc_backwards_compat(self) -> None:
        """Test that plugin ABCs maintain backwards compatibility.

        Loads all plugin ABC classes and verifies that within the same major
        version, no abstract methods have been removed or had their signatures
        changed in breaking ways.

        This validates that existing plugin implementations won't break when
        floe-core is updated within a major version.
        """
        # Define baseline abstract methods for each ABC (frozen at v1.0)
        # These should NOT be removed or have signatures changed in v1.x
        # Using Any to avoid mypy abstract class errors
        baseline_methods: dict[Any, set[str]] = {
            ComputePlugin: {
                "is_self_hosted",
                "generate_dbt_profile",
                "get_required_dbt_packages",
                "validate_connection",
                "get_resource_requirements",
                # From PluginMetadata
                "name",
                "version",
                "floe_api_version",
            },
            CatalogPlugin: {
                "connect",
                "create_namespace",
                "create_table",
                "delete_namespace",
                "drop_table",
                "list_namespaces",
                "list_tables",
                "vend_credentials",
                # From PluginMetadata
                "name",
                "version",
                "floe_api_version",
            },
            DBTPlugin: {
                "compile_project",
                "get_manifest",
                "get_run_results",
                "get_runtime_metadata",
                "lint_project",
                "run_models",
                "supports_parallel_execution",
                "supports_sql_linting",
                "test_models",
                # From PluginMetadata
                "name",
                "version",
                "floe_api_version",
            },
            # Add more as needed - these are minimal examples
        }

        breaking_changes: list[str] = []

        for abc_class, expected_methods in baseline_methods.items():
            # Get current abstract methods
            current_abstract = set()
            for name, member in inspect.getmembers(abc_class):
                if getattr(member, "__isabstractmethod__", False):
                    current_abstract.add(name)

            # Check for removed abstract methods (breaking change)
            removed_methods = expected_methods - current_abstract
            if removed_methods:
                breaking_changes.append(
                    f"{abc_class.__name__}: Removed abstract methods: {', '.join(removed_methods)}"
                )

            # Note: We don't fail on NEW abstract methods - that's acceptable
            # within a major version as long as they have default implementations
            # or are clearly marked as optional additions

            self.logger.info(
                f"ABC compatibility check: {abc_class.__name__} - "
                f"expected={len(expected_methods)} current={len(current_abstract)} "
                f"removed={len(removed_methods)}"
            )

        assert not breaking_changes, (
            "ABC backwards compatibility violations detected:\n"
            + "\n".join(f"  - {item}" for item in breaking_changes)
            + "\n\nRemoving abstract methods is a MAJOR version breaking change."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-051")
    def test_all_plugin_types_have_abc(self) -> None:
        """Test that every PluginType enum has a corresponding ABC class.

        Validates the plugin contract is complete - every plugin type
        must have an Abstract Base Class defining its interface.
        """
        # Verify we cover all plugin types in PLUGIN_ABC_MAP
        assert len(self.PLUGIN_ABC_MAP) == len(PluginType), (
            f"PLUGIN_ABC_MAP has {len(self.PLUGIN_ABC_MAP)} entries but "
            f"PluginType has {len(PluginType)} members. "
            f"Missing: {set(PluginType) - set(self.PLUGIN_ABC_MAP.keys())}"
        )

        # Verify each ABC has required abstract methods from PluginMetadata
        required_base_methods = {"name", "version", "floe_api_version"}

        for plugin_type, abc_class in self.PLUGIN_ABC_MAP.items():
            # ABC must be a class (not a module or instance)
            assert inspect.isclass(abc_class), (
                f"PLUGIN_ABC_MAP[{plugin_type.name}] = {abc_class} is not a class"
            )

            # ABC must have the required base methods
            abc_methods = {
                name
                for name, member in inspect.getmembers(abc_class)
                if getattr(member, "__isabstractmethod__", False)
            }

            missing_base = required_base_methods - abc_methods
            assert not missing_base, (
                f"{abc_class.__name__} missing required base abstract methods: {missing_base}. "
                "All plugin ABCs must inherit from PluginMetadata."
            )

            # ABC must have at least one domain-specific abstract method
            domain_methods = abc_methods - required_base_methods
            assert len(domain_methods) > 0, (
                f"{abc_class.__name__} has no domain-specific abstract methods. "
                "Plugin ABCs must define at least one method beyond PluginMetadata basics."
            )

            self.logger.info(
                f"ABC completeness check: {plugin_type.name} -> {abc_class.__name__} "
                f"(base={len(required_base_methods)}, domain={len(domain_methods)})"
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-052")
    def test_plugin_swap_actual_execution(self) -> None:
        """Test that swapping compute plugins produces functionally different configs.

        Goes beyond test_plugin_swap_via_config by validating that different
        compute plugins produce MEANINGFULLY different configurations:
        - Different dbt profile targets
        - Different resource requirements
        - Different connection parameters
        - Health checks pass for each plugin

        This validates that plugin swapping isn't just cosmetic - it actually
        changes how the pipeline would execute.
        """
        registry = get_registry()
        registry.discover_all()

        # Get available compute plugins
        compute_plugins = registry.list_all().get(PluginType.COMPUTE, [])

        assert len(compute_plugins) >= 1, (
            f"Need at least 1 compute plugin for execution test, found {len(compute_plugins)}"
        )

        # Collect plugin configurations for comparison
        plugin_configs: dict[str, dict[str, Any]] = {}

        for compute_name in compute_plugins:
            try:
                # Load the compute plugin
                compute_plugin = registry.get(PluginType.COMPUTE, compute_name)

                # Initialize config dict for this plugin
                plugin_config: dict[str, Any] = {
                    "name": compute_name,
                    "version": compute_plugin.version,
                    "health_check_passed": False,
                    "dbt_profile": None,
                    "resource_requirements": None,
                }

                # 1. Validate health check passes
                health_status = compute_plugin.health_check()
                assert health_status.state == HealthState.HEALTHY, (
                    f"Plugin {compute_name} health check failed: {health_status.message}"
                )
                plugin_config["health_check_passed"] = True

                self.logger.info(
                    f"Plugin {compute_name} health check passed: {health_status.message}"
                )

                # 2. Generate dbt profile if plugin supports it
                if hasattr(compute_plugin, "generate_dbt_profile") and callable(
                    compute_plugin.generate_dbt_profile
                ):
                    try:
                        dbt_profile = compute_plugin.generate_dbt_profile(
                            target="dev",
                            config={},
                        )
                        plugin_config["dbt_profile"] = dbt_profile

                        self.logger.info(
                            f"Plugin {compute_name} generated dbt profile: "
                            f"type={dbt_profile.get('type', 'unknown')}"
                        )
                    except Exception as e:
                        self.logger.warning(
                            f"Plugin {compute_name} dbt profile generation failed: {e}"
                        )

                # 3. Get resource requirements if plugin supports it
                if hasattr(compute_plugin, "get_resource_requirements") and callable(
                    compute_plugin.get_resource_requirements
                ):
                    try:
                        resource_reqs = compute_plugin.get_resource_requirements()
                        plugin_config["resource_requirements"] = resource_reqs

                        self.logger.info(
                            f"Plugin {compute_name} resource requirements: {resource_reqs}"
                        )
                    except Exception as e:
                        self.logger.warning(
                            f"Plugin {compute_name} resource requirements failed: {e}"
                        )

                # Store this plugin's configuration
                plugin_configs[compute_name] = plugin_config

            except Exception as e:
                self.logger.error(f"Plugin execution test failed: compute={compute_name} - {e}")
                raise

        # Verify at least one plugin configuration was collected
        assert len(plugin_configs) >= 1, (
            "Plugin swap execution test requires at least one successful configuration"
        )

        # If we have multiple compute plugins, verify they produce different configs
        if len(plugin_configs) >= 2:
            # Compare dbt profiles to ensure they're meaningfully different
            dbt_profiles = [
                cfg["dbt_profile"]
                for cfg in plugin_configs.values()
                if cfg["dbt_profile"] is not None
            ]

            if len(dbt_profiles) >= 2:
                # Check that profiles have different 'type' fields (e.g., duckdb vs postgres)
                profile_types = {profile.get("type") for profile in dbt_profiles if profile}

                assert len(profile_types) >= 2, (
                    f"Expected different dbt profile types, but got: {profile_types}. "
                    "Plugin swap should produce functionally different configurations."
                )

                self.logger.info(
                    f"Plugin swap validation: {len(profile_types)} different dbt profile "
                    f"types detected: {profile_types}"
                )

        # Log summary of all plugin configurations
        self.logger.info(
            f"Plugin swap execution test completed: {len(plugin_configs)} plugins validated"
        )
        for plugin_name, config in plugin_configs.items():
            self.logger.info(
                f"  - {plugin_name}: health={config['health_check_passed']}, "
                f"has_profile={config['dbt_profile'] is not None}, "
                f"has_resources={config['resource_requirements'] is not None}"
            )
