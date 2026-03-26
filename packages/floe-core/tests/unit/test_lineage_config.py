"""Unit tests for _build_lineage_config() env var override behavior.

Tests that OPENLINEAGE_URL environment variable overrides the manifest
endpoint when present and non-empty.

Task: OpenLineage env var override
Requirements: AC-1 (env var override), AC-6 (unchanged behavior when unset)
"""

from __future__ import annotations

from typing import Any

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
