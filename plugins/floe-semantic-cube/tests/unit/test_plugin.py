"""Unit tests for CubeSemanticPlugin.

Tests cover: ABC inheritance, metadata properties, config schema,
API endpoints, Helm values, security context, datasource config,
health check, and lifecycle methods.

Requirements Covered:
    - FR-003: CubeSemanticPlugin implements SemanticLayerPlugin ABC
    - FR-006: Plugin metadata properties
    - FR-008: Error handling
    - FR-009: Health check
    - FR-032: Security context with namespace/roles
    - FR-033: Admin bypass in security context
    - FR-034: API endpoint configuration
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from floe_core.plugin_metadata import HealthState, HealthStatus, PluginMetadata
from floe_core.plugins.semantic import SemanticLayerPlugin
from floe_core.schemas.compiled_artifacts import (
    CredentialRef,
    SemanticApiBinding,
    SemanticDatasourceBinding,
    SemanticDeploymentBinding,
    SemanticServiceEndpointBinding,
)

import floe_semantic_cube.plugin as cube_plugin_module
from floe_semantic_cube.config import CubeSemanticConfig
from floe_semantic_cube.errors import CubeSemanticError
from floe_semantic_cube.plugin import CubeSemanticPlugin


@pytest.fixture
def config() -> CubeSemanticConfig:
    """Create a test CubeSemanticConfig."""
    return CubeSemanticConfig(
        server_url="http://localhost:4000",
        api_secret="test-secret",
        database_name="test_analytics",
    )


@pytest.fixture
def plugin(config: CubeSemanticConfig) -> CubeSemanticPlugin:
    """Create a CubeSemanticPlugin instance for testing."""
    return CubeSemanticPlugin(config=config)


class TestCubeSemanticPluginInheritance:
    """Tests for ABC compliance."""

    @pytest.mark.requirement("FR-003")
    def test_inherits_semantic_layer_plugin(self) -> None:
        """Test that CubeSemanticPlugin is a SemanticLayerPlugin."""
        assert issubclass(CubeSemanticPlugin, SemanticLayerPlugin)

    @pytest.mark.requirement("FR-003")
    def test_inherits_plugin_metadata(self) -> None:
        """Test that CubeSemanticPlugin inherits PluginMetadata."""
        assert issubclass(CubeSemanticPlugin, PluginMetadata)

    @pytest.mark.requirement("FR-003")
    def test_is_instantiable(self, plugin: CubeSemanticPlugin) -> None:
        """Test that CubeSemanticPlugin can be instantiated."""
        assert isinstance(plugin, CubeSemanticPlugin)
        assert isinstance(plugin, SemanticLayerPlugin)


class TestCubeSemanticPluginMetadata:
    """Tests for plugin metadata properties."""

    @pytest.mark.requirement("FR-006")
    def test_name(self, plugin: CubeSemanticPlugin) -> None:
        """Test plugin name is 'cube'."""
        assert plugin.name == "cube"

    @pytest.mark.requirement("FR-006")
    def test_version(self, plugin: CubeSemanticPlugin) -> None:
        """Test plugin version is '0.1.0'."""
        assert plugin.version == "0.1.0"

    @pytest.mark.requirement("FR-006")
    def test_floe_api_version(self, plugin: CubeSemanticPlugin) -> None:
        """Test floe API version is '1.0'."""
        assert plugin.floe_api_version == "1.0"

    @pytest.mark.requirement("FR-006")
    def test_description(self, plugin: CubeSemanticPlugin) -> None:
        """Test plugin has a description."""
        assert plugin.description is not None
        assert len(plugin.description) > 0
        assert "cube" in plugin.description.lower() or "semantic" in plugin.description.lower()


class TestCubeSemanticPluginConfigSchema:
    """Tests for get_config_schema()."""

    @pytest.mark.requirement("FR-003")
    def test_get_config_schema_returns_config_class(self, plugin: CubeSemanticPlugin) -> None:
        """Test that get_config_schema returns CubeSemanticConfig."""
        schema = plugin.get_config_schema()
        assert schema is CubeSemanticConfig


class TestCubeSemanticPluginApiEndpoints:
    """Tests for get_api_endpoints()."""

    @pytest.mark.requirement("FR-034")
    def test_api_endpoints_dict_structure(self, plugin: CubeSemanticPlugin) -> None:
        """Test that get_api_endpoints returns a dict with expected keys."""
        endpoints = plugin.get_api_endpoints()
        assert isinstance(endpoints, dict)
        assert "rest" in endpoints
        assert "graphql" in endpoints
        assert "sql_http" in endpoints
        assert "health" in endpoints

    @pytest.mark.requirement("FR-034")
    def test_api_endpoints_contain_server_url(self, plugin: CubeSemanticPlugin) -> None:
        """Test that endpoint URLs contain the configured server URL."""
        endpoints = plugin.get_api_endpoints()
        for endpoint_url in endpoints.values():
            assert endpoint_url.startswith("http://localhost:4000")

    @pytest.mark.requirement("FR-034")
    def test_api_endpoints_with_custom_url(self) -> None:
        """Test endpoints with a custom server URL."""
        config = CubeSemanticConfig(
            server_url="https://cube.prod.example.com",
            api_secret="secret",
        )
        p = CubeSemanticPlugin(config=config)
        endpoints = p.get_api_endpoints()
        assert endpoints["rest"].startswith("https://cube.prod.example.com")

    @pytest.mark.requirement("FR-034")
    def test_api_endpoints_use_ready_and_live_health_paths(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test endpoint metadata exposes Cube ready and live health endpoints."""
        endpoints = plugin.get_api_endpoints()

        assert endpoints["health_ready"] == "http://localhost:4000/readyz"
        assert endpoints["health_live"] == "http://localhost:4000/livez"

    @pytest.mark.requirement("FR-034")
    def test_api_endpoints_replace_legacy_sql_path(self, plugin: CubeSemanticPlugin) -> None:
        """Test legacy endpoint metadata no longer advertises /cubejs-api/sql."""
        endpoints = plugin.get_api_endpoints()

        assert endpoints["sql_http"] == "http://localhost:4000/cubejs-api/v1/cubesql"
        assert "/cubejs-api/sql" not in endpoints.values()


class TestCubeSemanticPluginProviderNeutralRuntime:
    """Tests for SemanticDeploymentBinding runtime rendering."""

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-001")
    def test_get_api_endpoint_families_returns_logical_floe_families(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test Cube declares provider-neutral semantic API family support."""
        assert plugin.get_api_endpoint_families() == [
            "metadata",
            "query",
            "sql_http",
            "sql_wire",
            "graphql",
            "health",
        ]

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-002")
    def test_render_runtime_config_maps_duckdb_s3_binding_to_cube_env(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test DuckDB/S3-compatible binding renders Cube env without compute plugin."""
        binding = _semantic_binding()

        runtime_config = plugin.render_runtime_config(binding)

        assert runtime_config["provider"] == "cube"
        assert runtime_config["env"] == {
            "CUBEJS_DB_TYPE": "duckdb",
            "CUBEJS_DB_DUCKDB_DATABASE_PATH": "/data/analytics.duckdb",
            "CUBEJS_DB_DUCKDB_S3_ENDPOINT": "http://minio:9000",
            "CUBEJS_DB_DUCKDB_S3_REGION": "us-east-1",
            "CUBEJS_DB_DUCKDB_S3_URL_STYLE": "path",
            "CUBEJS_SCHEMA_PATH": "/cube/schema",
            "CUBEJS_PG_SQL_PORT": "15432",
        }
        assert runtime_config["credential_refs"] == {
            "s3_access_key_id": {
                "source": "kubernetes-secret",
                "name": "cube-datasource",
                "key": "AWS_ACCESS_KEY_ID",
            },
            "s3_secret_access_key": {
                "source": "kubernetes-secret",
                "name": "cube-datasource",
                "key": "AWS_SECRET_ACCESS_KEY",
            },
            "sql_user": {
                "source": "kubernetes-secret",
                "name": "cube-sql",
                "key": "username",
            },
            "sql_password": {
                "source": "kubernetes-secret",
                "name": "cube-sql",
                "key": "password",
            },
        }
        assert runtime_config["datasources"][0]["name"] == "default"
        assert runtime_config["apis"]["metadata"]["path"] == "/cubejs-api/v1/meta"
        assert runtime_config["apis"]["query"]["path"] == "/cubejs-api/v1/load"
        assert runtime_config["apis"]["sql_http"]["path"] == "/cubejs-api/v1/cubesql"
        assert runtime_config["apis"]["sql_wire"]["env"] == {
            "port": "CUBEJS_PG_SQL_PORT",
            "user": "CUBEJS_SQL_USER",
            "password": "CUBEJS_SQL_PASSWORD",  # pragma: allowlist secret
        }
        assert runtime_config["secret_env_refs"] == {
            "CUBEJS_DB_DUCKDB_S3_ACCESS_KEY_ID": {
                "source": "kubernetes-secret",
                "name": "cube-datasource",
                "key": "AWS_ACCESS_KEY_ID",
            },
            "CUBEJS_DB_DUCKDB_S3_SECRET_ACCESS_KEY": {
                "source": "kubernetes-secret",
                "name": "cube-datasource",
                "key": "AWS_SECRET_ACCESS_KEY",
            },
            "CUBEJS_SQL_USER": {
                "source": "kubernetes-secret",
                "name": "cube-sql",
                "key": "username",
            },
            "CUBEJS_SQL_PASSWORD": {
                "source": "kubernetes-secret",
                "name": "cube-sql",
                "key": "password",
            },
        }
        assert runtime_config["apis"]["graphql"]["path"] == "/cubejs-api/graphql"
        assert runtime_config["apis"]["health"]["ready_path"] == "/readyz"
        assert runtime_config["apis"]["health"]["live_path"] == "/livez"

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-003")
    def test_render_runtime_config_rejects_non_cube_provider(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test runtime rendering rejects unsupported semantic providers."""
        binding = _semantic_binding(provider="dbt-semantic-layer")

        with pytest.raises(CubeSemanticError, match="Unsupported semantic provider"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-004")
    def test_render_runtime_config_rejects_unsupported_datasource_driver(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test runtime rendering rejects datasource drivers Cube adapter cannot map."""
        binding = _semantic_binding(
            datasources=[
                SemanticDatasourceBinding(name="default", driver="spark", config={}),
            ]
        )

        with pytest.raises(CubeSemanticError, match="Unsupported Cube datasource driver"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-005")
    def test_render_runtime_config_rejects_multiple_datasources(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test adapter rejects multiple datasources until explicitly supported."""
        binding = _semantic_binding(
            datasources=[
                _duckdb_datasource(),
                _duckdb_datasource(name="analytics"),
            ],
        )

        with pytest.raises(CubeSemanticError, match="exactly one datasource"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-006")
    def test_render_runtime_config_rejects_missing_datasource(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test Cube runtime rendering requires one datasource binding."""
        binding = _semantic_binding(datasources=[])

        with pytest.raises(CubeSemanticError, match="exactly one datasource"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-007")
    def test_render_runtime_config_rejects_duplicate_service_endpoint_names(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test duplicate service endpoint names fail instead of being collapsed."""
        base_binding = _semantic_binding()
        binding = SemanticDeploymentBinding.model_construct(
            provider="cube",
            datasources=base_binding.datasources,
            service_endpoints=[
                SemanticServiceEndpointBinding(name="cube-api", url="http://cube:4000"),
                SemanticServiceEndpointBinding(name="cube-api", url="http://shadow:4000"),
                SemanticServiceEndpointBinding(name="cube-sql", url="cube-sql:15432"),
            ],
            apis=base_binding.apis,
            artifacts=[],
            publication=None,
            access_policies=[],
            config=base_binding.config,
            env_refs={},
            credential_refs={},
        )

        with pytest.raises(CubeSemanticError, match="duplicate service endpoint names"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-018")
    def test_render_runtime_config_rejects_credential_bearing_service_endpoint_url(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test service endpoint URLs are revalidated before runtime rendering."""
        binding = _semantic_binding(
            service_endpoints=[
                SemanticServiceEndpointBinding.model_construct(
                    name="cube-api",
                    url="http://user:pass@cube:4000",  # pragma: allowlist secret
                    api_families=["metadata", "query", "sql_http", "graphql", "health"],
                    config={},
                    env_refs={},
                    credential_refs={},
                ),
                SemanticServiceEndpointBinding(
                    name="cube-sql",
                    url="cube-sql:15432",
                    api_families=["sql_wire"],
                ),
            ]
        )

        with pytest.raises(CubeSemanticError, match="service_endpoints.cube-api.url"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-020")
    @pytest.mark.parametrize(
        "url",
        [
            "https://cube:4000?api_key=raw-secret-value",
            "https://cube:4000#token=raw-secret-value",
        ],
    )
    def test_render_runtime_config_rejects_secret_endpoint_url_parameters(
        self, plugin: CubeSemanticPlugin, url: str
    ) -> None:
        """Test service endpoint URL query and fragment credentials fail fast."""
        binding = _semantic_binding(
            service_endpoints=[
                SemanticServiceEndpointBinding.model_construct(
                    name="cube-api",
                    url=url,  # pragma: allowlist secret
                    api_families=["metadata", "query", "sql_http", "graphql", "health"],
                    config={},
                    env_refs={},
                    credential_refs={},
                ),
                SemanticServiceEndpointBinding(
                    name="cube-sql",
                    url="cube-sql:15432",
                    api_families=["sql_wire"],
                ),
            ]
        )

        with pytest.raises(CubeSemanticError, match="service_endpoints.cube-api.url"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-008")
    def test_render_runtime_config_requires_endpoint_for_each_api(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test API bindings must reference a declared service endpoint."""
        # Bypass schema-level reference validation to verify the adapter keeps
        # its own fail-fast check for malformed bindings from non-Pydantic callers.
        binding = SemanticDeploymentBinding.model_construct(
            provider="cube",
            datasources=[_duckdb_datasource()],
            service_endpoints=[
                SemanticServiceEndpointBinding(name="cube-api", url="http://cube:4000")
            ],
            apis=[
                SemanticApiBinding(family="metadata", endpoint_name="missing"),
            ],
        )

        with pytest.raises(CubeSemanticError, match="unknown service endpoint"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-009")
    def test_render_runtime_config_requires_sql_refs_when_sql_wire_enabled(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test SQL wire API requires port env and credential references."""
        binding = _semantic_binding(
            apis=[
                SemanticApiBinding(
                    family="sql_wire",
                    endpoint_name="cube-sql",
                    protocol="postgres-wire",
                    config={"port": 15432},
                )
            ]
        )

        with pytest.raises(CubeSemanticError, match="sql_wire requires credential_refs"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-019")
    @pytest.mark.parametrize("port", [[], 0, 70000])
    def test_render_runtime_config_rejects_invalid_sql_wire_port(
        self, plugin: CubeSemanticPlugin, port: object
    ) -> None:
        """Test SQL wire port rendering fails fast for non-TCP-port values."""
        binding = _semantic_binding(
            apis=[
                SemanticApiBinding.model_construct(
                    family="sql_wire",
                    endpoint_name="cube-sql",
                    path=None,
                    protocol="postgres-wire",
                    config={"port": port},
                    env_refs={},
                    credential_refs={
                        "user": _credential_ref("username", name="cube-sql"),
                        "password": _credential_ref("password", name="cube-sql"),
                    },
                )
            ]
        )

        with pytest.raises(CubeSemanticError, match="apis.sql_wire.config.port"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-017")
    def test_render_runtime_config_rejects_malformed_credential_refs(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test malformed credential ref values fail with CubeRuntimeConfigError."""
        binding = _semantic_binding(
            apis=[
                SemanticApiBinding.model_construct(
                    family="sql_wire",
                    endpoint_name="cube-sql",
                    path=None,
                    protocol="postgres-wire",
                    config={"port": 15432},
                    env_refs={},
                    credential_refs={
                        "user": "not-a-credential-ref",
                        "password": _credential_ref("password", name="cube-sql"),
                    },
                )
            ]
        )

        with pytest.raises(CubeSemanticError, match="credential_refs.user"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-010")
    def test_render_runtime_config_rejects_raw_secret_like_values(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test adapter rejects raw credential-looking runtime values."""
        binding = _semantic_binding().model_copy(
            update={
                "config": {
                    "schema_path": "/cube/schema",
                    "api_key_ref": "raw-secret-value",  # pragma: allowlist secret
                }
            }
        )

        with pytest.raises(CubeSemanticError, match="raw credential"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-011")
    def test_render_runtime_config_allows_non_secret_marker_substrings(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test ordinary config strings do not trip broad secret-word checks."""
        datasource = SemanticDatasourceBinding.model_construct(
            name="default",
            driver="duckdb",
            endpoint_url=None,
            config={
                "database_path": "/data/token_store/analytics.duckdb",
                "s3_endpoint": "http://minio:9000",
                "s3_region": "us-east-1",
                "s3_url_style": "path",
            },
            env_refs={},
            credential_refs={
                "s3_access_key_id": _credential_ref("AWS_ACCESS_KEY_ID"),
                "s3_secret_access_key": _credential_ref("AWS_SECRET_ACCESS_KEY"),
            },
        )
        binding = _semantic_binding().model_copy(
            update={
                "datasources": [datasource],
                "config": {
                    "schema_path": "/cube/schema",
                    "password_policy": "require_uppercase",  # pragma: allowlist secret
                    "auth_mode": "bearer_delegation",
                },
            }
        )

        runtime_config = plugin.render_runtime_config(binding)

        assert (
            runtime_config["env"]["CUBEJS_DB_DUCKDB_DATABASE_PATH"]
            == "/data/token_store/analytics.duckdb"
        )

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-012")
    def test_render_runtime_config_skips_null_optional_s3_env_values(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test optional S3 env values are omitted when explicitly null."""
        binding = _semantic_binding(
            datasources=[
                _duckdb_datasource(
                    config={
                        "database_path": "/data/analytics.duckdb",
                        "s3_endpoint": None,
                        "s3_region": None,
                        "s3_url_style": None,
                    }
                )
            ]
        )

        runtime_config = plugin.render_runtime_config(binding)

        assert runtime_config["env"] == {
            "CUBEJS_DB_TYPE": "duckdb",
            "CUBEJS_DB_DUCKDB_DATABASE_PATH": "/data/analytics.duckdb",
            "CUBEJS_SCHEMA_PATH": "/cube/schema",
            "CUBEJS_PG_SQL_PORT": "15432",
        }

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-013")
    def test_render_runtime_config_rejects_duplicate_api_families(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test duplicate API families fail instead of rendering inconsistent config."""
        binding = _semantic_binding(
            apis=[
                SemanticApiBinding(family="metadata", endpoint_name="cube-api"),
                SemanticApiBinding(family="metadata", endpoint_name="cube-api"),
            ]
        )

        with pytest.raises(CubeSemanticError, match="duplicate semantic API family"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-014")
    def test_render_runtime_config_rejects_api_family_without_cube_path_mapping(
        self, plugin: CubeSemanticPlugin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test API allowlist/path-map drift produces a CubeRuntimeConfigError."""
        monkeypatch.setattr(
            cube_plugin_module,
            "_API_FAMILIES",
            [*cube_plugin_module._API_FAMILIES, "diagnostics"],
        )
        binding = _semantic_binding(
            apis=[
                SemanticApiBinding(family="diagnostics", endpoint_name="cube-api"),
            ]
        )

        with pytest.raises(CubeSemanticError, match="No Cube API path mapping"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-015")
    def test_render_runtime_config_rejects_unsupported_binding_fragments(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test adapter rejects binding fragments it cannot render yet."""
        binding = _semantic_binding().model_copy(
            update={
                "artifacts": [
                    {
                        "name": "semantic-models",
                        "mount_path": "/cube/schema",
                        "format": "cube-yaml",
                    }
                ]
            }
        )

        with pytest.raises(CubeSemanticError, match="unsupported semantic binding fragments"):
            plugin.render_runtime_config(binding)

    @pytest.mark.requirement("SEMANTIC-CUBE-ADAPTER-016")
    @pytest.mark.parametrize(
        ("binding_factory", "expected_fragment"),
        [
            (
                lambda: _semantic_binding(
                    datasources=[
                        _duckdb_datasource(endpoint_url="http://duckdb.internal"),
                    ],
                ),
                "datasources.default.endpoint_url",
            ),
            (
                lambda: _semantic_binding(
                    datasources=[
                        _duckdb_datasource(env_refs={"schema_path": "CUBEJS_SCHEMA_PATH"}),
                    ],
                ),
                "datasources.default.env_refs",
            ),
            (
                lambda: _semantic_binding(
                    service_endpoint_config={"routing_mode": "internal"},
                ),
                "service_endpoints.cube-api.config",
            ),
            (
                lambda: _semantic_binding(
                    service_endpoint_env_refs={"api_token": "CUBEJS_API_SECRET"},
                ),
                "service_endpoints.cube-api.env_refs",
            ),
            (
                lambda: _semantic_binding(
                    service_endpoint_credential_refs={
                        "api_token": _credential_ref("token", name="cube-api"),
                    },
                ),
                "service_endpoints.cube-api.credential_refs",
            ),
            (
                lambda: _semantic_binding(
                    apis=[
                        SemanticApiBinding(
                            family="query",
                            endpoint_name="cube-api",
                            path="/custom-query",
                        ),
                    ],
                ),
                "apis.query.path",
            ),
            (
                lambda: _semantic_binding(
                    apis=[
                        SemanticApiBinding(
                            family="query",
                            endpoint_name="cube-api",
                            env_refs={"api_token": "CUBEJS_API_SECRET"},
                        ),
                    ],
                ),
                "apis.query.env_refs",
            ),
            (
                lambda: _semantic_binding(
                    apis=[
                        SemanticApiBinding(
                            family="query",
                            endpoint_name="cube-api",
                            credential_refs={
                                "api_token": _credential_ref("token", name="cube-api"),
                            },
                        ),
                    ],
                ),
                "apis.query.credential_refs",
            ),
        ],
    )
    def test_render_runtime_config_rejects_unsupported_nested_binding_shapes(
        self,
        plugin: CubeSemanticPlugin,
        binding_factory: Callable[[], SemanticDeploymentBinding],
        expected_fragment: str,
    ) -> None:
        """Test adapter rejects nested binding fields it cannot render yet."""
        with pytest.raises(CubeSemanticError, match=expected_fragment):
            plugin.render_runtime_config(binding_factory())


class TestCubeSemanticPluginHelmValues:
    """Tests for get_helm_values_override()."""

    @pytest.mark.requirement("FR-003")
    def test_helm_values_is_dict(self, plugin: CubeSemanticPlugin) -> None:
        """Test that get_helm_values_override returns a dict."""
        values = plugin.get_helm_values_override()
        assert isinstance(values, dict)

    @pytest.mark.requirement("FR-003")
    def test_helm_values_has_cube_key(self, plugin: CubeSemanticPlugin) -> None:
        """Test that Helm values contain 'cube' key."""
        values = plugin.get_helm_values_override()
        assert "cube" in values

    @pytest.mark.requirement("FR-003")
    def test_helm_values_cube_enabled(self, plugin: CubeSemanticPlugin) -> None:
        """Test that Cube is enabled in Helm values."""
        values = plugin.get_helm_values_override()
        assert values["cube"]["enabled"] is True

    @pytest.mark.requirement("FR-003")
    def test_helm_values_database_name(self, plugin: CubeSemanticPlugin) -> None:
        """Test that database name is set in Helm values."""
        values = plugin.get_helm_values_override()
        env = values["cube"]["api"]["env"]
        assert env["CUBEJS_DB_NAME"] == "test_analytics"


class TestCubeSemanticPluginSecurityContext:
    """Tests for get_security_context()."""

    @pytest.mark.requirement("FR-032")
    def test_security_context_basic(self, plugin: CubeSemanticPlugin) -> None:
        """Test security context with basic namespace and roles."""
        context = plugin.get_security_context(
            namespace="tenant_acme",
            roles=["analyst", "viewer"],
        )
        assert context["tenant_id"] == "tenant_acme"
        assert context["allowed_roles"] == ["analyst", "viewer"]

    @pytest.mark.requirement("FR-033")
    def test_security_context_admin_bypass(self, plugin: CubeSemanticPlugin) -> None:
        """Test that admin role enables RLS bypass."""
        context = plugin.get_security_context(
            namespace="tenant_acme",
            roles=["admin"],
        )
        assert context["bypass_rls"] is True

    @pytest.mark.requirement("FR-033")
    def test_security_context_no_admin_no_bypass(self, plugin: CubeSemanticPlugin) -> None:
        """Test that non-admin roles do not get RLS bypass."""
        context = plugin.get_security_context(
            namespace="tenant_acme",
            roles=["analyst"],
        )
        assert "bypass_rls" not in context

    @pytest.mark.requirement("FR-032")
    def test_security_context_empty_namespace(self, plugin: CubeSemanticPlugin) -> None:
        """Test security context with empty namespace."""
        context = plugin.get_security_context(namespace="", roles=["viewer"])
        assert context["tenant_id"] == ""

    @pytest.mark.requirement("FR-032")
    def test_security_context_special_characters(self, plugin: CubeSemanticPlugin) -> None:
        """Test security context with special characters in namespace."""
        context = plugin.get_security_context(
            namespace="tenant-with_special.chars",
            roles=["viewer"],
        )
        assert context["tenant_id"] == "tenant-with_special.chars"

    @pytest.mark.requirement("FR-032")
    def test_security_context_long_namespace(self, plugin: CubeSemanticPlugin) -> None:
        """Test security context with very long namespace."""
        long_ns = "a" * 500
        context = plugin.get_security_context(namespace=long_ns, roles=["viewer"])
        assert context["tenant_id"] == long_ns

    @pytest.mark.requirement("FR-032")
    def test_security_context_empty_roles(self, plugin: CubeSemanticPlugin) -> None:
        """Test security context with empty roles list."""
        context = plugin.get_security_context(namespace="tenant_x", roles=[])
        assert context["allowed_roles"] == []


class TestCubeSemanticPluginHealthCheck:
    """Tests for health_check()."""

    @pytest.mark.requirement("FR-009")
    def test_health_check_returns_health_status(self, plugin: CubeSemanticPlugin) -> None:
        """Test that health_check returns a HealthStatus."""
        status = plugin.health_check()
        assert isinstance(status, HealthStatus)

    @pytest.mark.requirement("FR-009")
    def test_health_check_default_unhealthy(self, plugin: CubeSemanticPlugin) -> None:
        """Test that health check returns UNHEALTHY when not connected."""
        status = plugin.health_check()
        assert status.state == HealthState.UNHEALTHY


class TestCubeSemanticPluginLifecycle:
    """Tests for startup()/shutdown() lifecycle."""

    @pytest.mark.requirement("FR-008")
    def test_startup_does_not_raise(self, plugin: CubeSemanticPlugin) -> None:
        """Test that startup() completes without error."""
        plugin.startup()

    @pytest.mark.requirement("FR-008")
    def test_shutdown_does_not_raise(self, plugin: CubeSemanticPlugin) -> None:
        """Test that shutdown() completes without error."""
        plugin.shutdown()

    @pytest.mark.requirement("FR-008")
    def test_startup_shutdown_lifecycle(self, plugin: CubeSemanticPlugin) -> None:
        """Test full startup/shutdown lifecycle."""
        plugin.startup()
        plugin.shutdown()


def _credential_ref(key: str, *, name: str = "cube-datasource") -> CredentialRef:
    """Create a Kubernetes Secret credential reference."""
    return CredentialRef(source="kubernetes-secret", name=name, key=key)


def _duckdb_datasource(
    *,
    name: str = "default",
    database_path: str = "/data/analytics.duckdb",
    endpoint_url: str | None = None,
    env_refs: dict[str, str] | None = None,
    config: dict[str, object] | None = None,
) -> SemanticDatasourceBinding:
    """Create a DuckDB datasource binding with S3-compatible projection."""
    return SemanticDatasourceBinding(
        name=name,
        driver="duckdb",
        endpoint_url=endpoint_url,
        config=config
        if config is not None
        else {
            "database_path": database_path,
            "s3_endpoint": "http://minio:9000",
            "s3_region": "us-east-1",
            "s3_url_style": "path",
        },
        env_refs=env_refs or {},
        credential_refs={
            "s3_access_key_id": _credential_ref("AWS_ACCESS_KEY_ID"),
            "s3_secret_access_key": _credential_ref("AWS_SECRET_ACCESS_KEY"),
        },
    )


def _semantic_binding(
    *,
    provider: str = "cube",
    datasources: list[SemanticDatasourceBinding] | None = None,
    service_endpoints: list[SemanticServiceEndpointBinding] | None = None,
    apis: list[SemanticApiBinding] | None = None,
    config: dict[str, object] | None = None,
    service_endpoint_config: dict[str, object] | None = None,
    service_endpoint_env_refs: dict[str, str] | None = None,
    service_endpoint_credential_refs: dict[str, CredentialRef] | None = None,
) -> SemanticDeploymentBinding:
    """Create a semantic deployment binding for Cube runtime tests."""
    return SemanticDeploymentBinding(
        provider=provider,
        datasources=datasources if datasources is not None else [_duckdb_datasource()],
        service_endpoints=service_endpoints
        if service_endpoints is not None
        else [
            SemanticServiceEndpointBinding(
                name="cube-api",
                url="http://cube:4000",
                config=service_endpoint_config or {},
                env_refs=service_endpoint_env_refs or {},
                credential_refs=service_endpoint_credential_refs or {},
            ),
            SemanticServiceEndpointBinding(name="cube-sql", url="cube-sql:15432"),
        ],
        apis=apis
        if apis is not None
        else [
            SemanticApiBinding(family="metadata", endpoint_name="cube-api"),
            SemanticApiBinding(family="query", endpoint_name="cube-api"),
            SemanticApiBinding(family="sql_http", endpoint_name="cube-api"),
            SemanticApiBinding(
                family="sql_wire",
                endpoint_name="cube-sql",
                protocol="postgres-wire",
                config={"port": 15432},
                credential_refs={
                    "user": _credential_ref("username", name="cube-sql"),
                    "password": _credential_ref("password", name="cube-sql"),
                },
            ),
            SemanticApiBinding(family="graphql", endpoint_name="cube-api"),
            SemanticApiBinding(family="health", endpoint_name="cube-api"),
        ],
        config={"schema_path": "/cube/schema", **(config or {})},
    )
