"""Integration test for compile_pipeline() → create_sync_emitter() wiring.

Verifies the integration seam: the config dict produced by
_build_lineage_config() is passed to create_sync_emitter() unchanged.

Task: OpenLineage env var override
Requirements: AC-1 (env var override wiring)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


ENV_VAR_ENDPOINT = "http://override.example.com:5100/api/v1/lineage"
"""OPENLINEAGE_URL env var value used in override tests."""


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
        monkeypatch.setenv("OPENLINEAGE_URL", ENV_VAR_ENDPOINT)
        # Ensure OTel endpoint is unset so we don't need a real collector
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        root = Path(__file__).parent.parent.parent.parent.parent
        spec_path = root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = root / "demo" / "manifest.yaml"

        if not spec_path.exists() or not manifest_path.exists():
            pytest.fail(
                f"Demo spec files not found at {spec_path} / {manifest_path}.\n"
                "These files are required for the wiring integration test.\n"
                "Ensure the demo/ directory is present in the repository root."
            )

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
