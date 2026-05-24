"""CubeSemanticPlugin implementation.

This module provides the concrete implementation of the SemanticLayerPlugin
ABC for Cube. The full implementation is built incrementally across
Phase 4 tasks (T015-T022).

Requirements Covered:
    - FR-003: CubeSemanticPlugin implements SemanticLayerPlugin ABC
    - FR-004: Plugin metadata (name, version, floe_api_version)
    - FR-008: Error handling
    - FR-009: Health check
    - FR-048: OTel span for health check
    - FR-049: Configurable timeout
    - FR-050: Response time measurement
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx
import structlog
from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.semantic import SemanticLayerPlugin
from floe_core.schemas.compiled_artifacts import (
    CredentialRef,
    SemanticApiBinding,
    SemanticDatasourceBinding,
    SemanticDeploymentBinding,
    SemanticServiceEndpointBinding,
)
from floe_core.telemetry.sanitization import sanitize_error_message

from floe_semantic_cube.config import CubeSemanticConfig
from floe_semantic_cube.errors import CubeRuntimeConfigError
from floe_semantic_cube.schema_generator import CubeSchemaGenerator
from floe_semantic_cube.tracing import (
    ATTR_DURATION_MS,
    ATTR_MODEL_COUNT,
    ATTR_SCHEMA_PATH,
    TRACER_NAME,
    get_tracer,
    semantic_span,
)

if TYPE_CHECKING:
    from floe_core.plugins.compute import ComputePlugin

logger = structlog.get_logger(__name__)

# Timeout validation bounds
_MIN_TIMEOUT: float = 0.1
_MAX_TIMEOUT: float = 10.0
_API_FAMILIES: list[str] = [
    "metadata",
    "query",
    "sql_http",
    "sql_wire",
    "graphql",
    "health",
]
_API_PATHS: dict[str, str] = {
    "metadata": "/cubejs-api/v1/meta",
    "query": "/cubejs-api/v1/load",
    "sql_http": "/cubejs-api/v1/cubesql",
    "graphql": "/cubejs-api/graphql",
}
_SECRET_VALUE_MARKERS: tuple[str, ...] = (
    "raw-secret-value",
    "secret-value",
)


class CubeSemanticPlugin(SemanticLayerPlugin):
    """Cube semantic layer plugin implementation.

    Provides Cube integration for the floe platform, including dbt manifest
    to Cube schema generation, datasource configuration delegation,
    security context, and health monitoring.

    Args:
        config: CubeSemanticConfig with connection settings.

    Example:
        >>> from floe_semantic_cube.config import CubeSemanticConfig
        >>> config = CubeSemanticConfig(api_secret="secret")
        >>> plugin = CubeSemanticPlugin(config=config)
        >>> plugin.name
        'cube'
    """

    def __init__(self, config: CubeSemanticConfig) -> None:
        super().__init__()
        self._config = config
        self._client: httpx.Client | None = None
        self._started: bool = False

    @property
    def name(self) -> str:
        """Plugin name identifier."""
        return "cube"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Floe API version this plugin targets."""
        return "1.0"

    @property
    def description(self) -> str:
        """Human-readable plugin description."""
        return "Cube semantic layer plugin for business intelligence APIs"

    @property
    def tracer_name(self) -> str:
        """Return the OpenTelemetry tracer name.

        Returns:
            The tracer name for this plugin's operations.
        """
        return TRACER_NAME

    def get_config_schema(self) -> type:
        """Return the configuration schema class.

        Returns:
            The CubeSemanticConfig Pydantic model class.
        """
        return CubeSemanticConfig

    def sync_from_dbt_manifest(
        self,
        manifest_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """Generate Cube schema files from dbt manifest.

        Creates a CubeSchemaGenerator with filter settings from config,
        then converts dbt model nodes to Cube YAML definitions.

        Args:
            manifest_path: Path to dbt manifest.json file.
            output_dir: Directory to write generated Cube YAML files.

        Returns:
            List of paths to generated schema files.
        """
        tracer = get_tracer()

        with semantic_span(
            tracer,
            "sync_from_dbt_manifest",
            server_url=self._config.server_url,
            schema_path=str(output_dir),
        ) as span:
            generator = CubeSchemaGenerator(
                model_filter_schemas=self._config.model_filter_schemas or None,
                model_filter_tags=self._config.model_filter_tags or None,
            )

            logger.info(
                "sync_from_dbt_manifest_started",
                manifest_path=str(manifest_path),
                output_dir=str(output_dir),
            )

            result = generator.generate(manifest_path, output_dir)
            span.set_attribute(ATTR_MODEL_COUNT, len(result))
            span.set_attribute(ATTR_SCHEMA_PATH, str(output_dir))

            logger.info(
                "sync_from_dbt_manifest_complete",
                files_generated=len(result),
            )

            return result

    def get_security_context(
        self,
        namespace: str,
        roles: list[str],
    ) -> dict[str, Any]:
        """Build Cube security context for multi-tenant isolation.

        Args:
            namespace: Data namespace for tenant isolation.
            roles: User roles for access control.

        Returns:
            Cube-compatible security context dictionary.
        """
        context: dict[str, Any] = {
            "tenant_id": namespace,
            "allowed_roles": roles,
        }
        if "admin" in roles:
            context["bypass_rls"] = True
        return context

    def get_datasource_config(
        self,
        compute_plugin: ComputePlugin,
    ) -> dict[str, Any]:
        """Generate Cube datasource config from compute plugin.

        Uses duck-typing to check for get_cube_datasource_config() on the
        compute plugin. Falls back to a generic config for non-DuckDB computes.

        Args:
            compute_plugin: Active ComputePlugin instance.

        Returns:
            Cube datasource configuration dictionary.
        """
        # Duck-type check for Cube-specific method
        cube_config_method = getattr(compute_plugin, "get_cube_datasource_config", None)
        if callable(cube_config_method):
            result: dict[str, Any] = cube_config_method()
            return result

        # Fallback for compute plugins without Cube-specific config
        return {
            "type": compute_plugin.name,
            "database_name": self._config.database_name,
        }

    def render_runtime_config(
        self,
        binding: SemanticDeploymentBinding,
    ) -> dict[str, Any]:
        """Render Cube runtime configuration from semantic deployment binding.

        The primary path consumes secret-free provider-neutral desired state.
        It does not inspect live compute, catalog, storage, secrets, identity,
        or orchestrator plugin implementations.
        """
        if binding.provider != "cube":
            raise CubeRuntimeConfigError(
                f"Unsupported semantic provider {binding.provider!r}; expected 'cube'"
            )

        _reject_unsupported_binding_fragments(binding)
        _validate_unique_api_families(binding.apis)
        _assert_no_sentinel_secret_markers(binding.config, "semantic.config")
        service_endpoints = _service_endpoints_by_name(binding.service_endpoints)
        datasources = [self._render_datasource(datasource) for datasource in binding.datasources]
        env = self._render_environment(binding, datasources)
        apis = self._render_apis(binding.apis, service_endpoints)
        credential_refs = self._render_credential_refs(binding.datasources, binding.apis)

        return {
            "provider": "cube",
            "env": env,
            "secret_env_refs": _render_secret_environment_refs(binding.datasources, binding.apis),
            "credential_refs": credential_refs,
            "datasources": datasources,
            "service_endpoints": {
                name: {
                    "url": endpoint.url,
                    "api_families": list(endpoint.api_families),
                }
                for name, endpoint in service_endpoints.items()
            },
            "apis": apis,
        }

    def get_api_endpoint_families(self) -> list[str]:
        """Return provider-neutral Floe semantic API families backed by Cube."""
        return list(_API_FAMILIES)

    def get_api_endpoints(self) -> dict[str, str]:
        """Return Cube API endpoint URLs.

        Returns:
            Dictionary mapping endpoint names to URL paths.
        """
        base = self._config.server_url
        return {
            "rest": f"{base}/cubejs-api/v1",
            "graphql": f"{base}/cubejs-api/graphql",
            "metadata": f"{base}/cubejs-api/v1/meta",
            "query": f"{base}/cubejs-api/v1/load",
            "sql_http": f"{base}/cubejs-api/v1/cubesql",
            "health": f"{base}/readyz",
            "health_ready": f"{base}/readyz",
            "health_live": f"{base}/livez",
        }

    def get_helm_values_override(self) -> dict[str, Any]:
        """Return Helm values for Cube deployment.

        Returns:
            Helm values dictionary for the Cube subchart.
        """
        return {
            "cube": {
                "enabled": True,
                "api": {
                    "env": {
                        "CUBEJS_DB_TYPE": "duckdb",
                        "CUBEJS_DB_NAME": self._config.database_name,
                    },
                },
            },
        }

    def health_check(self, timeout: float | None = None) -> HealthStatus:
        """Check Cube API server health.

        Args:
            timeout: Maximum time in seconds to wait for response.
                Must be between 0.1 and 10.0. Defaults to config value.

        Returns:
            HealthStatus indicating server availability.

        Raises:
            ValueError: If timeout is outside valid range.

        Requirements:
            FR-048: OTel span for health check
            FR-049: Configurable timeout
            FR-050: Response time measurement
        """
        # Resolve effective timeout. An unstarted plugin has no initialised
        # config, so reading self._config.health_check_timeout would fail.
        # Return UNHEALTHY immediately — callers should pass an explicit
        # timeout or call startup() first.
        if timeout is not None:
            effective_timeout = timeout
        elif not self._started:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="Plugin not started",
                details={
                    "reason": "not_started",
                },
            )
        else:
            effective_timeout = self._config.health_check_timeout

        if effective_timeout < _MIN_TIMEOUT or effective_timeout > _MAX_TIMEOUT:
            msg = (
                f"timeout must be between {_MIN_TIMEOUT} and "
                f"{_MAX_TIMEOUT}, got {effective_timeout}"
            )
            raise ValueError(msg)

        if not self._started:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="Plugin not started",
                details={
                    "reason": "not_started",
                    "timeout": effective_timeout,
                },
            )

        # FR-048: OTel span for health check (raw tracer API since we catch
        # all exceptions internally rather than letting them propagate)
        tracer = get_tracer()
        with tracer.start_as_current_span(
            "semantic.health_check",
            attributes={
                "semantic.operation": "health_check",
                "semantic.server_url": self._config.server_url,
                "semantic.timeout": effective_timeout,
            },
        ) as span:
            checked_at = datetime.now(timezone.utc)
            start = time.perf_counter()

            try:
                if self._client is None:
                    msg = "HTTP client not initialized — call startup() first"
                    raise RuntimeError(msg)
                health_url = f"{self._config.server_url}/readyz"
                response = self._client.get(health_url, timeout=effective_timeout)
                elapsed_ms = (time.perf_counter() - start) * 1000
                span.set_attribute(ATTR_DURATION_MS, elapsed_ms)

                if response.status_code == 200:
                    span.set_attribute("semantic.health_status", "healthy")
                    return HealthStatus(
                        state=HealthState.HEALTHY,
                        message="Cube API is healthy",
                        details={
                            "response_time_ms": elapsed_ms,
                            "checked_at": checked_at,
                            "timeout": effective_timeout,
                            "status_code": response.status_code,
                        },
                    )
                span.set_attribute("semantic.health_status", "unhealthy")
                span.set_attribute("semantic.status_code", response.status_code)
                return HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message=f"Cube API returned status {response.status_code}",
                    details={
                        "response_time_ms": elapsed_ms,
                        "checked_at": checked_at,
                        "timeout": effective_timeout,
                        "status_code": response.status_code,
                        "reason": "unhealthy_response",
                    },
                )
            except httpx.TimeoutException as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                span.set_attribute(ATTR_DURATION_MS, elapsed_ms)
                span.set_attribute("semantic.health_status", "timeout")
                sanitized = sanitize_error_message(str(exc))
                span.set_attribute("exception.type", type(exc).__name__)
                span.set_attribute("exception.message", sanitized)
                logger.warning(
                    "health_check_timeout",
                    server_url=self._config.server_url,
                    timeout=effective_timeout,
                )
                return HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message=f"Cube API health check timed out after {effective_timeout}s",
                    details={
                        "response_time_ms": elapsed_ms,
                        "checked_at": checked_at,
                        "timeout": effective_timeout,
                        "reason": "timeout",
                    },
                )
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                span.set_attribute(ATTR_DURATION_MS, elapsed_ms)
                span.set_attribute("semantic.health_status", "error")
                sanitized = sanitize_error_message(str(exc))
                span.set_attribute("exception.type", type(exc).__name__)
                span.set_attribute("exception.message", sanitized)
                logger.warning(
                    "health_check_error",
                    server_url=self._config.server_url,
                    error=str(exc),
                )
                return HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message=f"Cube API health check failed: {exc}",
                    details={
                        "response_time_ms": elapsed_ms,
                        "checked_at": checked_at,
                        "timeout": effective_timeout,
                        "reason": "connection_error",
                    },
                )

    def startup(self) -> None:
        """Initialize plugin resources.

        Creates an httpx client for health checks and API communication.
        """
        if self._started:
            return
        self._client = httpx.Client()
        self._started = True
        logger.info("cube_plugin_started", server_url=self._config.server_url)

    def shutdown(self) -> None:
        """Release plugin resources.

        Closes the httpx client if active.
        """
        if self._client is not None:
            self._client.close()
            self._client = None
        self._started = False
        logger.info("cube_plugin_stopped")

    def _render_datasource(self, datasource: SemanticDatasourceBinding) -> dict[str, Any]:
        """Render a datasource binding into Cube datasource config."""
        if datasource.driver != "duckdb":
            raise CubeRuntimeConfigError(
                f"Unsupported Cube datasource driver {datasource.driver!r}"
            )
        _assert_no_sentinel_secret_markers(
            datasource.config,
            f"semantic.datasource.{datasource.name}",
        )

        return {
            "name": datasource.name,
            "driver": datasource.driver,
            "config": dict(datasource.config),
            "env_refs": dict(datasource.env_refs),
            "credential_refs": _credential_refs_to_dict(
                datasource.credential_refs,
                f"datasources.{datasource.name}.credential_refs",
            ),
        }

    def _render_environment(
        self,
        binding: SemanticDeploymentBinding,
        datasources: list[dict[str, Any]],
    ) -> dict[str, str]:
        """Render Cube environment variables from binding fragments."""
        env: dict[str, str] = {}
        _ensure_single_datasource(datasources)
        datasource = datasources[0]
        config = datasource["config"]
        env["CUBEJS_DB_TYPE"] = "duckdb"
        database_path = config.get("database_path")
        if database_path is None:
            raise CubeRuntimeConfigError(
                "DuckDB datasource requires config.database_path for CUBEJS_DB_DUCKDB_DATABASE_PATH"
            )
        env["CUBEJS_DB_DUCKDB_DATABASE_PATH"] = str(database_path)
        _set_optional_env(
            env,
            config=config,
            config_key="s3_endpoint",
            env_key="CUBEJS_DB_DUCKDB_S3_ENDPOINT",
        )
        _set_optional_env(
            env,
            config=config,
            config_key="s3_region",
            env_key="CUBEJS_DB_DUCKDB_S3_REGION",
        )
        _set_optional_env(
            env,
            config=config,
            config_key="s3_url_style",
            env_key="CUBEJS_DB_DUCKDB_S3_URL_STYLE",
        )

        schema_path = binding.config.get("schema_path")
        if schema_path is not None:
            env["CUBEJS_SCHEMA_PATH"] = str(schema_path)

        sql_wire_api = _find_api(binding.apis, "sql_wire")
        if sql_wire_api is not None:
            port = sql_wire_api.config.get("port")
            if port is None:
                raise CubeRuntimeConfigError("sql_wire requires config.port for CUBEJS_PG_SQL_PORT")
            env["CUBEJS_PG_SQL_PORT"] = str(_validate_tcp_port(port, "apis.sql_wire.config.port"))

        return env

    def _render_apis(
        self,
        apis: list[SemanticApiBinding],
        service_endpoints: dict[str, SemanticServiceEndpointBinding],
    ) -> dict[str, Any]:
        """Render logical API bindings into Cube API descriptors."""
        rendered: dict[str, Any] = {}
        for api in apis:
            if api.family not in _API_FAMILIES:
                raise CubeRuntimeConfigError(f"Unsupported Cube API family {api.family!r}")
            if api.endpoint_name not in service_endpoints:
                raise CubeRuntimeConfigError(
                    "semantic api endpoint_name references unknown service endpoint: "
                    f"{api.endpoint_name!r}"
                )
            _assert_no_sentinel_secret_markers(api.config, f"semantic.api.{api.family}")

            if api.family == "health":
                rendered["health"] = {
                    "endpoint_name": api.endpoint_name,
                    "ready_path": "/readyz",
                    "live_path": "/livez",
                    "protocol": api.protocol or "http",
                }
                continue

            if api.family == "sql_wire":
                _validate_sql_wire_refs(api)
                rendered["sql_wire"] = {
                    "endpoint_name": api.endpoint_name,
                    "protocol": api.protocol or "postgres-wire",
                    "env": {
                        "port": "CUBEJS_PG_SQL_PORT",
                        "user": "CUBEJS_SQL_USER",
                        "password": "CUBEJS_SQL_PASSWORD",  # pragma: allowlist secret
                    },
                    "credential_refs": _credential_refs_to_dict(
                        api.credential_refs,
                        f"apis.{api.family}.credential_refs",
                    ),
                }
                continue

            path = _API_PATHS.get(api.family)
            if path is None:
                raise CubeRuntimeConfigError(
                    f"No Cube API path mapping for family {api.family!r}",
                    fragment=f"apis.{api.family}",
                )
            rendered[api.family] = {
                "endpoint_name": api.endpoint_name,
                "path": path,
                "protocol": api.protocol or "http",
            }
        return rendered

    def _render_credential_refs(
        self,
        datasources: list[SemanticDatasourceBinding],
        apis: list[SemanticApiBinding],
    ) -> dict[str, dict[str, str | None]]:
        """Collect credential references needed by Cube runtime config."""
        credential_refs: dict[str, dict[str, str | None]] = {}
        for datasource in datasources:
            credential_refs.update(
                _credential_refs_to_dict(
                    datasource.credential_refs,
                    f"datasources.{datasource.name}.credential_refs",
                )
            )
        sql_wire_api = _find_api(apis, "sql_wire")
        if sql_wire_api is not None:
            _validate_sql_wire_refs(sql_wire_api)
            credential_refs["sql_user"] = _credential_ref_to_dict(
                sql_wire_api.credential_refs["user"],
                "apis.sql_wire.credential_refs.user",
            )
            credential_refs["sql_password"] = _credential_ref_to_dict(
                sql_wire_api.credential_refs["password"],
                "apis.sql_wire.credential_refs.password",
            )
        return credential_refs


def _service_endpoints_by_name(
    service_endpoints: list[SemanticServiceEndpointBinding],
) -> dict[str, SemanticServiceEndpointBinding]:
    """Return service endpoints keyed by name."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for endpoint in service_endpoints:
        if endpoint.name in seen:
            duplicates.add(endpoint.name)
        seen.add(endpoint.name)
        _assert_no_endpoint_url_credentials(
            endpoint.url,
            f"service_endpoints.{endpoint.name}.url",
        )
    if duplicates:
        raise CubeRuntimeConfigError(
            f"duplicate service endpoint names: {sorted(duplicates)}",
            fragment="service_endpoints",
        )
    return {endpoint.name: endpoint for endpoint in service_endpoints}


def _assert_no_endpoint_url_credentials(value: Any, path: str) -> None:
    """Reject service endpoint URLs that embed credential material."""
    if not isinstance(value, str) or not value:
        raise CubeRuntimeConfigError(
            f"{path} must be a non-empty string",
            fragment=path,
        )
    parsed = urlsplit(value)
    if parsed.username is not None or parsed.password is not None:
        raise CubeRuntimeConfigError(
            f"{path} must not include embedded credentials",
            fragment=path,
        )


def _validate_tcp_port(value: Any, path: str) -> int:
    """Validate an environment-projected TCP port value."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CubeRuntimeConfigError(
            f"{path} must be an integer TCP port",
            fragment=path,
        )
    if value < 1 or value > 65535:
        raise CubeRuntimeConfigError(
            f"{path} must be a valid TCP port between 1 and 65535",
            fragment=path,
        )
    return value


def _find_api(apis: list[SemanticApiBinding], family: str) -> SemanticApiBinding | None:
    """Return the API binding for a logical family, if declared."""
    return next((api for api in apis if api.family == family), None)


def _ensure_single_datasource(datasources: list[Any]) -> None:
    """Ensure Cube runtime rendering receives exactly one datasource."""
    if len(datasources) != 1:
        raise CubeRuntimeConfigError(
            "Cube runtime rendering supports exactly one datasource binding"
        )


def _validate_unique_api_families(apis: list[SemanticApiBinding]) -> None:
    """Ensure each logical semantic API family is declared at most once."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for api in apis:
        if api.family in seen:
            duplicates.add(api.family)
        seen.add(api.family)
    if duplicates:
        raise CubeRuntimeConfigError(
            f"duplicate semantic API family bindings: {sorted(duplicates)}",
            fragment="apis",
        )


def _set_optional_env(
    env: dict[str, str],
    *,
    config: dict[str, Any],
    config_key: str,
    env_key: str,
) -> None:
    """Set an env var from config when the value is present and non-null."""
    value = config.get(config_key)
    if value is not None:
        env[env_key] = str(value)


def _reject_unsupported_binding_fragments(binding: SemanticDeploymentBinding) -> None:
    """Fail fast on semantic binding fragments this adapter does not render yet."""
    unsupported_fragments: list[str] = []
    if binding.artifacts:
        unsupported_fragments.append("artifacts")
    if binding.publication is not None:
        unsupported_fragments.append("publication")
    if binding.access_policies:
        unsupported_fragments.append("access_policies")
    if binding.env_refs:
        unsupported_fragments.append("env_refs")
    if binding.credential_refs:
        unsupported_fragments.append("credential_refs")

    for datasource in binding.datasources:
        if datasource.endpoint_url is not None:
            unsupported_fragments.append(f"datasources.{datasource.name}.endpoint_url")
        if datasource.env_refs:
            unsupported_fragments.append(f"datasources.{datasource.name}.env_refs")

    for endpoint in binding.service_endpoints:
        if endpoint.config:
            unsupported_fragments.append(f"service_endpoints.{endpoint.name}.config")
        if endpoint.env_refs:
            unsupported_fragments.append(f"service_endpoints.{endpoint.name}.env_refs")
        if endpoint.credential_refs:
            unsupported_fragments.append(f"service_endpoints.{endpoint.name}.credential_refs")

    for api in binding.apis:
        if api.path is not None:
            unsupported_fragments.append(f"apis.{api.family}.path")
        if api.env_refs:
            unsupported_fragments.append(f"apis.{api.family}.env_refs")
        if api.family != "sql_wire" and api.credential_refs:
            unsupported_fragments.append(f"apis.{api.family}.credential_refs")

    if unsupported_fragments:
        raise CubeRuntimeConfigError(
            "unsupported semantic binding fragments for Cube runtime rendering: "
            f"{', '.join(unsupported_fragments)}"
        )


def _validate_sql_wire_refs(api: SemanticApiBinding) -> None:
    """Validate SQL wire credential references needed by Cube."""
    required_refs = {"user", "password"}
    missing = required_refs - set(api.credential_refs)
    if missing:
        raise CubeRuntimeConfigError(
            "sql_wire requires credential_refs for CUBEJS_SQL_USER and "
            f"CUBEJS_SQL_PASSWORD; missing {sorted(missing)}"
        )


def _render_secret_environment_refs(
    datasources: list[SemanticDatasourceBinding],
    apis: list[SemanticApiBinding],
) -> dict[str, dict[str, str | None]]:
    """Map Cube secret environment variables to unresolved credential refs."""
    secret_env_refs: dict[str, dict[str, str | None]] = {}
    _ensure_single_datasource(datasources)
    datasource = datasources[0]
    datasource_secret_env_names = {
        "s3_access_key_id": "CUBEJS_DB_DUCKDB_S3_ACCESS_KEY_ID",
        "s3_secret_access_key": (
            "CUBEJS_DB_DUCKDB_S3_SECRET_ACCESS_KEY"  # pragma: allowlist secret
        ),
    }
    for credential_name, env_name in datasource_secret_env_names.items():
        credential_ref = datasource.credential_refs.get(credential_name)
        if credential_ref is not None:
            secret_env_refs[env_name] = _credential_ref_to_dict(
                credential_ref,
                f"datasources.{datasource.name}.credential_refs.{credential_name}",
            )

    sql_wire_api = _find_api(apis, "sql_wire")
    if sql_wire_api is not None:
        _validate_sql_wire_refs(sql_wire_api)
        secret_env_refs["CUBEJS_SQL_USER"] = _credential_ref_to_dict(
            sql_wire_api.credential_refs["user"],
            "apis.sql_wire.credential_refs.user",
        )
        secret_env_refs["CUBEJS_SQL_PASSWORD"] = _credential_ref_to_dict(
            sql_wire_api.credential_refs["password"],
            "apis.sql_wire.credential_refs.password",
        )
    return secret_env_refs


def _credential_ref_to_dict(ref: CredentialRef, path: str) -> dict[str, str | None]:
    """Serialize a credential reference without resolving secret material."""
    if not isinstance(ref, CredentialRef):
        raise CubeRuntimeConfigError(
            f"{path} must be a CredentialRef instance",
            fragment=path,
        )
    return {"source": ref.source, "name": ref.name, "key": ref.key}


def _credential_refs_to_dict(
    refs: dict[str, CredentialRef],
    path: str,
) -> dict[str, dict[str, str | None]]:
    """Serialize credential reference mapping without secret material."""
    return {name: _credential_ref_to_dict(ref, f"{path}.{name}") for name, ref in refs.items()}


def _assert_no_sentinel_secret_markers(value: Any, path: str) -> None:
    """Reject sentinel markers that indicate unresolved secret material leaked into config."""
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_no_sentinel_secret_markers(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_sentinel_secret_markers(child, f"{path}[{index}]")
        return
    if isinstance(value, str):
        value_text = value.lower()
        if value_text in _SECRET_VALUE_MARKERS or value_text.startswith("raw-secret:"):
            raise CubeRuntimeConfigError(
                f"{path} looks like raw credential material; use credential_refs instead"
            )
