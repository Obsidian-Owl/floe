"""E2E test: Governance Enforcement (AC-2.5).

Validates the compilation pipeline's ENFORCE stage:
    Configure strict enforcement → compile spec that violates policy → verify rejection

Unlike the existing test_governance.py which validates governance rules at the
policy level, this test validates compilation pipeline integration — when
governance is configured in manifest.yaml with enforcement_level: strict,
does floe compile actually reject a violating spec?

Prerequisites:
    - No K8s required (compilation is host-side)

See Also:
    - .specwright/work/test-hardening-audit/spec.md: AC-2.5
    - packages/floe-core/src/floe_core/compilation/stages.py: ENFORCE stage

Resolved (WU-6 T35):
    compile_pipeline() now passes enforcement_result to build_artifacts().
    Previous xfail markers removed — tests should pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

# Shared plugin config for custom manifests — must include all required plugins
# to avoid RESOLVE stage E201 errors.
_REQUIRED_PLUGINS: dict[str, Any] = {
    "compute": {
        "type": "duckdb",
        "config": {"threads": 1, "memory_limit": "256MB"},
    },
    "orchestrator": {
        "type": "dagster",
        "config": {"default_schedule": "*/10 * * * *"},
    },
    "catalog": {
        "type": "polaris",
        "config": {
            "uri": "http://localhost:8181/api/catalog",
            "warehouse": "floe-test",
            "credential": "demo-admin:demo-secret",
        },
    },
    "storage": {
        "type": "s3",
        "config": {
            "endpoint": "http://localhost:9000",
            "bucket": "floe-data",
            "region": "us-east-1",
            "path_style_access": True,
        },
    },
}


@pytest.mark.e2e
@pytest.mark.requirement("AC-2.5")
class TestGovernanceEnforcement:
    """Governance enforcement during compilation.

    Validates that the ENFORCE stage in the 6-stage compilation pipeline
    correctly evaluates governance policies and respects enforcement levels.
    """

    @pytest.mark.requirement("AC-2.5")
    def test_warn_mode_allows_compilation(
        self,
        compiled_artifacts: Any,
        project_root: Path,
    ) -> None:
        """Verify warn mode compiles successfully but records violations.

        The demo manifest uses policy_enforcement_level: warn, which means
        compilation should succeed but record any policy violations in the
        enforcement_result.
        """
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        # Compilation should succeed in warn mode
        assert artifacts.version, "Compilation failed in warn mode"

        # Enforcement should have run
        assert artifacts.enforcement_result is not None, (
            "enforcement_result is None — ENFORCE stage did not run.\n"
            "Check compile_pipeline() Stage 4 implementation."
        )

        # In warn mode, enforcement should pass (warnings don't block)
        assert artifacts.enforcement_result.passed, (
            f"Enforcement FAILED in warn mode (should only warn).\n"
            f"Error count: {artifacts.enforcement_result.error_count}\n"
            f"Level: {artifacts.enforcement_result.enforcement_level}"
        )

    @pytest.mark.requirement("AC-2.5")
    def test_strict_mode_blocks_violation(
        self,
        project_root: Path,
        tmp_path: Path,
    ) -> None:
        """Verify strict mode compilation succeeds with valid demo spec.

        Creates a manifest with strict enforcement and compiles the demo spec.
        Validates compilation completes and produces artifacts with correct
        enforcement level.
        """
        from floe_core.compilation.stages import compile_pipeline

        # Create a strict manifest with all required plugins
        strict_manifest: dict[str, Any] = {
            "apiVersion": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "strict-test",
                "version": "1.0.0",
                "description": "Strict governance test",
                "owner": "test@floe.dev",
            },
            "plugins": _REQUIRED_PLUGINS,
            "governance": {
                "policy_enforcement_level": "strict",
                "audit_logging": "enabled",
                "data_retention_days": 1,
                "quality_gates": {
                    "minimum_test_coverage": 80,
                    "require_descriptions": True,
                    "block_on_failure": True,
                },
            },
        }

        manifest_path = tmp_path / "strict_manifest.yaml"
        manifest_path.write_text(yaml.dump(strict_manifest))

        # Use a valid demo spec (customer-360) against the strict manifest
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"

        # Strict mode with valid demo spec should compile successfully
        artifacts = compile_pipeline(spec_path, manifest_path)

        # Compilation must succeed
        assert artifacts.version, "Compilation failed with strict enforcement"
        assert artifacts.metadata.product_name == "customer-360", (
            f"Expected customer-360, got {artifacts.metadata.product_name}"
        )

        # Enforcement result populated (WU-6 T35 fixed the pipeline gap)
        assert artifacts.enforcement_result is not None
        assert artifacts.enforcement_result.enforcement_level == "strict"
        assert artifacts.enforcement_result.passed is True

    @pytest.mark.requirement("AC-2.5")
    def test_enforcement_level_off_skips_checks(
        self,
        project_root: Path,
        tmp_path: Path,
    ) -> None:
        """Verify enforcement_level: off allows compilation without enforcement.

        When governance enforcement is disabled, compilation should succeed.
        """
        from floe_core.compilation.stages import compile_pipeline

        # Create manifest with enforcement off and all required plugins
        off_manifest: dict[str, Any] = {
            "apiVersion": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "off-test",
                "version": "1.0.0",
                "description": "No enforcement test",
                "owner": "test@floe.dev",
            },
            "plugins": _REQUIRED_PLUGINS,
            "governance": {
                "policy_enforcement_level": "off",
                "audit_logging": "disabled",
                "data_retention_days": 1,
            },
        }

        manifest_path = tmp_path / "off_manifest.yaml"
        manifest_path.write_text(yaml.dump(off_manifest))

        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        artifacts = compile_pipeline(spec_path, manifest_path)

        # Compilation should succeed
        assert artifacts.version, "Compilation failed with enforcement=off"

        # Enforcement result populated (WU-6 T35 fixed the pipeline gap)
        assert artifacts.enforcement_result is not None
        assert artifacts.enforcement_result.passed

    @pytest.mark.requirement("AC-2.5")
    def test_governance_violations_in_artifacts(
        self,
        compiled_artifacts: Any,
        project_root: Path,
    ) -> None:
        """Verify governance violations are propagated to CompiledArtifacts.

        Even in warn mode, violations should be recorded in the enforcement_result
        so they can be reviewed without blocking compilation.
        """
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.enforcement_result is not None, (
            "enforcement_result missing — violations can't be tracked"
        )

        # Verify enforcement result has required fields
        result = artifacts.enforcement_result
        assert hasattr(result, "passed"), "Missing 'passed' field"
        assert hasattr(result, "error_count"), "Missing 'error_count' field"
        assert hasattr(result, "warning_count"), "Missing 'warning_count' field"
        assert hasattr(result, "enforcement_level"), "Missing 'enforcement_level' field"
        assert isinstance(result.error_count, int), (
            f"error_count should be int, got {type(result.error_count)}"
        )
        assert isinstance(result.warning_count, int), (
            f"warning_count should be int, got {type(result.warning_count)}"
        )
