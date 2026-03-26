"""Unit tests for _build_lineage_config() env var override behavior.

Tests that OPENLINEAGE_URL environment variable overrides the manifest
endpoint when present and non-empty.

Task: OpenLineage env var override
Requirements: AC-1 (env var override), AC-6 (unchanged behavior when unset)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from floe_core.compilation.stages import _build_lineage_config
from floe_core.schemas.manifest import (
    LineageManifestConfig,
    ObservabilityManifestConfig,
    PlatformManifest,
)

# Constants to avoid duplicate string literals
MANIFEST_ENDPOINT = "http://marquez.example.com:5000/api/v1/lineage"
"""Manifest-configured lineage endpoint (non-private network for validator)."""

ENV_VAR_ENDPOINT = "http://override.example.com:5100/api/v1/lineage"
"""OPENLINEAGE_URL env var value used in override tests."""

MINIMAL_METADATA: dict[str, Any] = {
    "name": "test-platform",
    "version": "1.0.0",
    "owner": "test@example.com",
}
"""Minimal valid metadata for PlatformManifest construction."""

MINIMAL_PLUGINS: dict[str, Any] = {
    "compute": {"type": "duckdb", "version": "0.9.0"},
    "orchestrator": {"type": "dagster", "version": "1.5.0"},
}
"""Minimal valid plugins for PlatformManifest construction."""


def _make_manifest(
    *,
    lineage_enabled: bool = True,
    transport: str = "http",
    endpoint: str | None = MANIFEST_ENDPOINT,
    observability: ObservabilityManifestConfig | None | object = ...,
) -> PlatformManifest:
    """Build a PlatformManifest with configurable lineage settings.

    Args:
        lineage_enabled: Whether lineage is enabled.
        transport: OpenLineage transport type.
        endpoint: Lineage endpoint URL.
        observability: If ``...`` (sentinel), build from other args.
            If ``None``, set observability to None.

    Returns:
        Configured PlatformManifest instance.
    """
    obs: ObservabilityManifestConfig | None
    if observability is ...:
        obs = ObservabilityManifestConfig(
            lineage=LineageManifestConfig(
                enabled=lineage_enabled,
                transport=transport,  # type: ignore[arg-type]  # Literal coercion
                endpoint=endpoint,
            ),
        )
    elif observability is None:
        obs = None
    else:
        obs = observability  # type: ignore[assignment]

    return PlatformManifest(
        apiVersion="floe.dev/v1",
        kind="Manifest",
        metadata=MINIMAL_METADATA,
        plugins=MINIMAL_PLUGINS,
        observability=obs,
    )


class TestBuildLineageConfigEnvVarOverride:
    """Tests for OPENLINEAGE_URL env var overriding manifest endpoint.

    AC-1: When OPENLINEAGE_URL is set and non-empty, it MUST be used
    as the lineage config URL, overriding the manifest's endpoint value.
    """

    @pytest.mark.requirement("AC-1")
    def test_openlineage_url_env_var_overrides_manifest(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """OPENLINEAGE_URL env var overrides manifest endpoint.

        Set OPENLINEAGE_URL to a different URL than the manifest endpoint.
        The returned config must use the env var value, not the manifest value.
        This proves runtime-configurable endpoint resolution for K8s
        environments where the manifest contains an internal hostname.
        """
        monkeypatch.setenv("OPENLINEAGE_URL", ENV_VAR_ENDPOINT)
        manifest = _make_manifest(endpoint=MANIFEST_ENDPOINT)

        result = _build_lineage_config(manifest)

        assert result is not None, "Expected config dict, got None"
        assert result["url"] == ENV_VAR_ENDPOINT, (
            f"Expected env var URL {ENV_VAR_ENDPOINT!r}, "
            f"got {result.get('url')!r}. "
            "OPENLINEAGE_URL must override the manifest endpoint."
        )
        # Verify it is NOT the manifest endpoint (guards against both
        # being identical by accident -- constants differ above)
        assert result["url"] != MANIFEST_ENDPOINT

    @pytest.mark.requirement("AC-6")
    def test_openlineage_url_env_var_unset_uses_manifest(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When OPENLINEAGE_URL is not set, manifest endpoint is used.

        This is the baseline behavior that must remain unchanged: if no
        env var is present, the manifest's own endpoint is returned.
        """
        monkeypatch.delenv("OPENLINEAGE_URL", raising=False)
        manifest = _make_manifest(endpoint=MANIFEST_ENDPOINT)

        result = _build_lineage_config(manifest)

        assert result is not None, "Expected config dict, got None"
        assert result["url"] == MANIFEST_ENDPOINT, (
            f"Expected manifest URL {MANIFEST_ENDPOINT!r}, got {result.get('url')!r}"
        )

    @pytest.mark.requirement("AC-1")
    def test_openlineage_url_env_var_empty_uses_manifest(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Empty OPENLINEAGE_URL is treated as absent; manifest endpoint used.

        An empty string env var must NOT override the manifest endpoint.
        This prevents accidental blank overrides in container environments
        where env vars may be set to empty strings.
        """
        monkeypatch.setenv("OPENLINEAGE_URL", "")
        manifest = _make_manifest(endpoint=MANIFEST_ENDPOINT)

        result = _build_lineage_config(manifest)

        assert result is not None, "Expected config dict, got None"
        assert result["url"] == MANIFEST_ENDPOINT, (
            f"Expected manifest URL {MANIFEST_ENDPOINT!r} when "
            f"OPENLINEAGE_URL is empty, got {result.get('url')!r}"
        )

    @pytest.mark.requirement("AC-6")
    def test_lineage_disabled_ignores_env_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """OPENLINEAGE_URL has no effect when lineage is disabled.

        Even if the env var is set, disabled lineage must return None.
        The env var override only applies when lineage is actually enabled.
        """
        monkeypatch.setenv("OPENLINEAGE_URL", ENV_VAR_ENDPOINT)
        manifest = _make_manifest(lineage_enabled=False)

        result = _build_lineage_config(manifest)

        assert result is None, (
            f"Expected None when lineage disabled, got {result!r}. "
            "OPENLINEAGE_URL must not re-enable disabled lineage."
        )

    @pytest.mark.requirement("AC-6")
    def test_no_observability_config_ignores_env_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """OPENLINEAGE_URL has no effect when observability is None.

        A manifest without observability config must return None regardless
        of env var presence.
        """
        monkeypatch.setenv("OPENLINEAGE_URL", ENV_VAR_ENDPOINT)
        manifest = _make_manifest(observability=None)

        result = _build_lineage_config(manifest)

        assert result is None, (
            f"Expected None when observability is None, got {result!r}. "
            "OPENLINEAGE_URL must not synthesize observability config."
        )

    @pytest.mark.requirement("AC-1")
    def test_openlineage_url_whitespace_only_uses_manifest(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Whitespace-only OPENLINEAGE_URL is treated as absent.

        A value like ``"   "`` must be stripped and treated as empty,
        falling back to the manifest endpoint.  This guards against
        container environments that set env vars to whitespace.
        """
        monkeypatch.setenv("OPENLINEAGE_URL", "   ")
        manifest = _make_manifest(endpoint=MANIFEST_ENDPOINT)

        result = _build_lineage_config(manifest)

        assert result is not None, "Expected config dict, got None"
        assert result["url"] == MANIFEST_ENDPOINT, (
            f"Expected manifest URL {MANIFEST_ENDPOINT!r} when "
            f"OPENLINEAGE_URL is whitespace-only, got {result.get('url')!r}"
        )

    @pytest.mark.requirement("AC-1")
    def test_returned_config_includes_transport_type(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returned config dict contains ``type`` matching the manifest transport.

        The ``type`` field drives which transport class the emitter uses.
        It must always reflect the manifest's ``lineage.transport`` value.
        """
        monkeypatch.setenv("OPENLINEAGE_URL", ENV_VAR_ENDPOINT)
        manifest = _make_manifest(transport="http", endpoint=MANIFEST_ENDPOINT)

        result = _build_lineage_config(manifest)

        assert result is not None, "Expected config dict, got None"
        assert result["type"] == "http", (
            f"Expected type 'http', got {result.get('type')!r}. "
            "Config type must match manifest transport."
        )

    @pytest.mark.requirement("AC-6")
    def test_http_transport_no_endpoint_returns_none_despite_env_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """HTTP transport with endpoint=None returns None even when env var is set.

        When the manifest declares HTTP transport but provides no endpoint,
        ``_build_lineage_config`` returns None before consulting the env var.
        This is intentional: a manifest without an endpoint is treated as
        incomplete configuration, and the env var cannot rescue it.
        """
        monkeypatch.setenv("OPENLINEAGE_URL", ENV_VAR_ENDPOINT)
        manifest = _make_manifest(transport="http", endpoint=None)

        result = _build_lineage_config(manifest)

        assert result is None, (
            f"Expected None when http transport has no manifest endpoint, "
            f"got {result!r}. The env var must not rescue incomplete config."
        )


class TestCompilePipelineLineageWiring:
    """Tests that compile_pipeline() wires _build_lineage_config() to create_sync_emitter().

    Verifies the integration seam: the config dict produced by
    _build_lineage_config() is passed to create_sync_emitter() unchanged.
    """

    @pytest.mark.requirement("AC-1")
    def test_compile_pipeline_passes_lineage_config_to_emitter(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """compile_pipeline() passes _build_lineage_config() result to create_sync_emitter().

        Patches create_sync_emitter to capture its arguments, then verifies
        that the config dict includes the env-var-overridden URL.
        """
        from pathlib import Path

        monkeypatch.setenv("OPENLINEAGE_URL", ENV_VAR_ENDPOINT)
        # Ensure OTel endpoint is unset so we don't need a real collector
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        root = Path(__file__).parent.parent.parent.parent.parent
        spec_path = root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = root / "demo" / "manifest.yaml"

        if not spec_path.exists() or not manifest_path.exists():
            pytest.skip("Demo spec files not available in this environment")

        captured_configs: list[Any] = []

        from floe_core.lineage.emitter import create_sync_emitter as original_create

        def _capturing_create(
            transport_config: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> Any:
            captured_configs.append(transport_config)
            # Use NoOp transport to avoid network calls
            return original_create(None, **kwargs)

        with patch(
            "floe_core.lineage.emitter.create_sync_emitter",
            side_effect=_capturing_create,
        ):
            from floe_core.compilation.stages import compile_pipeline

            compile_pipeline(spec_path, manifest_path)

        assert len(captured_configs) >= 1, (
            "create_sync_emitter was never called during compile_pipeline()"
        )
        config = captured_configs[0]
        assert config is not None, (
            "create_sync_emitter received None config — "
            "_build_lineage_config() result was not passed through"
        )
        assert config.get("url") == ENV_VAR_ENDPOINT, (
            f"Expected emitter config url {ENV_VAR_ENDPOINT!r}, "
            f"got {config.get('url')!r}. "
            "compile_pipeline() must pass _build_lineage_config() result "
            "to create_sync_emitter()."
        )
        assert config.get("type") == "http", (
            f"Expected emitter config type 'http', got {config.get('type')!r}"
        )
