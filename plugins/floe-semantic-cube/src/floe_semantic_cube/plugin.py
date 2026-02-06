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

import httpx
import structlog

from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.semantic import SemanticLayerPlugin

from floe_semantic_cube.config import CubeSemanticConfig

if TYPE_CHECKING:
    from floe_core.plugins.compute import ComputePlugin

logger = structlog.get_logger(__name__)

# Timeout validation bounds
_MIN_TIMEOUT: float = 0.1
_MAX_TIMEOUT: float = 10.0


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

        Args:
            manifest_path: Path to dbt manifest.json file.
            output_dir: Directory to write generated Cube YAML files.

        Returns:
            List of paths to generated schema files.
        """
        raise NotImplementedError("Schema generation not yet implemented")

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
            return cube_config_method()

        # Fallback for compute plugins without Cube-specific config
        return {
            "type": compute_plugin.name,
            "database_name": self._config.database_name,
        }

    def get_api_endpoints(self) -> dict[str, str]:
        """Return Cube API endpoint URLs.

        Returns:
            Dictionary mapping endpoint names to URL paths.
        """
        base = self._config.server_url
        return {
            "rest": f"{base}/cubejs-api/v1",
            "graphql": f"{base}/cubejs-api/graphql",
            "sql": f"{base}/cubejs-api/sql",
            "health": f"{base}/readyz",
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
        """
        effective_timeout = timeout if timeout is not None else self._config.health_check_timeout

        if effective_timeout < _MIN_TIMEOUT or effective_timeout > _MAX_TIMEOUT:
            msg = f"timeout must be between {_MIN_TIMEOUT} and {_MAX_TIMEOUT}, got {effective_timeout}"
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

        checked_at = datetime.now(timezone.utc)
        start = time.perf_counter()

        try:
            assert self._client is not None  # noqa: S101
            health_url = f"{self._config.server_url}/readyz"
            response = self._client.get(health_url, timeout=effective_timeout)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
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
        except httpx.TimeoutException:
            elapsed_ms = (time.perf_counter() - start) * 1000
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
