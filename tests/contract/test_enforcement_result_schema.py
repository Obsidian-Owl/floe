"""Contract tests for EnforcementResult schema stability.

These tests ensure the EnforcementResult schema remains stable and
backward-compatible. Breaking changes should fail these tests.

The EnforcementResult schema is the contract for policy enforcement results
returned by PolicyEnforcer.enforce() and consumed by the compilation pipeline.

Task: T024
Requirements: FR-002 (Pipeline Integration), US1 (Compile-time Enforcement)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

# These imports will fail until implementation (TDD)
# The tests are written FIRST to define the expected contract


class TestEnforcementResultSchemaContract:
    """Contract tests for EnforcementResult schema stability.

    These tests define the expected structure that downstream consumers
    (compilation pipeline, CLI, etc.) can rely on.
    """

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_has_required_fields(self) -> None:
        """Contract: EnforcementResult MUST have all required fields.

        Required fields:
        - passed: bool
        - violations: list[Violation]
        - summary: EnforcementSummary
        - enforcement_level: Literal["off", "warn", "strict"]
        - manifest_version: str
        - timestamp: datetime
        """
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=10, models_validated=10),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        # All required fields accessible
        assert hasattr(result, "passed")
        assert hasattr(result, "violations")
        assert hasattr(result, "summary")
        assert hasattr(result, "enforcement_level")
        assert hasattr(result, "manifest_version")
        assert hasattr(result, "timestamp")

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_serializable_to_json(self) -> None:
        """Contract: EnforcementResult MUST be JSON-serializable.

        Downstream consumers need to persist and transmit results.
        """
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=5, models_validated=5),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        # Should serialize without error
        json_str = result.model_dump_json()
        assert isinstance(json_str, str)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["passed"] is True
        assert parsed["enforcement_level"] == "strict"

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_deserializable_from_json(self) -> None:
        """Contract: EnforcementResult MUST be deserializable from JSON.

        Consumers should be able to reconstruct from persisted data.
        """
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        # Create and serialize
        original = EnforcementResult(
            passed=False,
            violations=[],
            summary=EnforcementSummary(
                total_models=10,
                models_validated=10,
                naming_violations=2,
            ),
            enforcement_level="warn",
            manifest_version="1.5.0",
            timestamp=datetime.now(timezone.utc),
        )
        json_str = original.model_dump_json()

        # Deserialize
        restored = EnforcementResult.model_validate_json(json_str)

        assert restored.passed == original.passed
        assert restored.enforcement_level == original.enforcement_level
        assert restored.summary.naming_violations == 2

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_immutable(self) -> None:
        """Contract: EnforcementResult MUST be immutable (frozen=True).

        Results should not be modified after creation for audit integrity.
        """
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary
        from pydantic import ValidationError

        result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=0, models_validated=0),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises((AttributeError, ValidationError)):
            result.passed = False  # type: ignore[misc]


class TestViolationSchemaContract:
    """Contract tests for Violation schema stability."""

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_has_required_fields(self) -> None:
        """Contract: Violation MUST have all required fields.

        Required fields:
        - error_code: str (format: FLOE-E###)
        - severity: Literal["error", "warning"]
        - policy_type: Literal["naming", "coverage", "documentation"]
        - model_name: str
        - message: str
        - expected: str
        - actual: str
        - suggestion: str
        - documentation_url: str
        """
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="stg_customers",
            message="Model name violates naming convention",
            expected="medallion pattern",
            actual="stg_customers",
            suggestion="Rename to bronze_customers",
            documentation_url="https://floe.dev/docs/naming",
        )

        # All required fields accessible
        assert hasattr(violation, "error_code")
        assert hasattr(violation, "severity")
        assert hasattr(violation, "policy_type")
        assert hasattr(violation, "model_name")
        assert hasattr(violation, "message")
        assert hasattr(violation, "expected")
        assert hasattr(violation, "actual")
        assert hasattr(violation, "suggestion")
        assert hasattr(violation, "documentation_url")

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_serializable_to_json(self) -> None:
        """Contract: Violation MUST be JSON-serializable."""
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E210",
            severity="warning",
            policy_type="coverage",
            model_name="customers",
            message="Coverage below threshold",
            expected="80%",
            actual="60%",
            suggestion="Add column tests",
            documentation_url="https://floe.dev/docs/coverage",
        )

        json_str = violation.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["error_code"] == "FLOE-E210"
        assert parsed["policy_type"] == "coverage"

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_immutable(self) -> None:
        """Contract: Violation MUST be immutable (frozen=True)."""
        from floe_core.enforcement.result import Violation
        from pydantic import ValidationError

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="test",
            message="Error",
            expected="x",
            actual="y",
            suggestion="Fix",
            documentation_url="https://floe.dev",
        )

        with pytest.raises((AttributeError, ValidationError)):
            violation.error_code = "FLOE-E999"  # type: ignore[misc]


class TestEnforcementSummarySchemaContract:
    """Contract tests for EnforcementSummary schema stability."""

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_summary_has_required_fields(self) -> None:
        """Contract: EnforcementSummary MUST have all required fields.

        Required fields:
        - total_models: int
        - models_validated: int
        - naming_violations: int (default 0)
        - coverage_violations: int (default 0)
        - documentation_violations: int (default 0)
        - duration_ms: float (default 0.0)
        """
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(
            total_models=50,
            models_validated=50,
        )

        assert hasattr(summary, "total_models")
        assert hasattr(summary, "models_validated")
        assert hasattr(summary, "naming_violations")
        assert hasattr(summary, "coverage_violations")
        assert hasattr(summary, "documentation_violations")
        assert hasattr(summary, "duration_ms")

        # Check defaults
        assert summary.naming_violations == 0
        assert summary.coverage_violations == 0
        assert summary.documentation_violations == 0
        assert summary.duration_ms == pytest.approx(0.0)

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_summary_serializable_to_json(self) -> None:
        """Contract: EnforcementSummary MUST be JSON-serializable."""
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(
            total_models=100,
            models_validated=98,
            naming_violations=5,
            coverage_violations=10,
            documentation_violations=3,
            duration_ms=1234.56,
        )

        json_str = summary.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["total_models"] == 100
        assert parsed["naming_violations"] == 5
        assert parsed["duration_ms"] == pytest.approx(1234.56)


class TestEnforcementResultComputedProperties:
    """Contract tests for EnforcementResult computed properties."""

    @pytest.mark.requirement("3A-US1-FR002")
    def test_has_errors_property_contract(self) -> None:
        """Contract: EnforcementResult MUST have has_errors computed property.

        Returns True if any violation has severity='error'.
        """
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        # No errors
        result_clean = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=0, models_validated=0),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result_clean.has_errors is False

        # Has errors
        result_with_error = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="test",
                    message="Error",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(total_models=1, models_validated=1),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result_with_error.has_errors is True

    @pytest.mark.requirement("3A-US1-FR002")
    def test_warning_count_property_contract(self) -> None:
        """Contract: EnforcementResult MUST have warning_count computed property."""
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        result = EnforcementResult(
            passed=True,
            violations=[
                Violation(
                    error_code="FLOE-E222",
                    severity="warning",
                    policy_type="documentation",
                    model_name="test1",
                    message="Warning 1",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E222",
                    severity="warning",
                    policy_type="documentation",
                    model_name="test2",
                    message="Warning 2",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(total_models=2, models_validated=2),
            enforcement_level="warn",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result.warning_count == 2

    @pytest.mark.requirement("3A-US1-FR002")
    def test_error_count_property_contract(self) -> None:
        """Contract: EnforcementResult MUST have error_count computed property."""
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        result = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="test1",
                    message="Error 1",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E210",
                    severity="error",
                    policy_type="coverage",
                    model_name="test2",
                    message="Error 2",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E222",
                    severity="warning",
                    policy_type="documentation",
                    model_name="test3",
                    message="Warning",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(total_models=3, models_validated=3),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result.error_count == 2


class TestEnforcementResultSchemaEvolution:
    """Tests for schema evolution and backward compatibility."""

    @pytest.mark.requirement("3A-US1-FR002")
    def test_extra_fields_forbidden(self) -> None:
        """Contract: EnforcementResult MUST reject extra fields (extra=forbid).

        This ensures strict schema compliance and prevents accidental
        field additions that could break downstream consumers.
        """
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="extra_field"):
            EnforcementResult(
                passed=True,
                violations=[],
                summary=EnforcementSummary(total_models=0, models_validated=0),
                enforcement_level="strict",
                manifest_version="1.0.0",
                timestamp=datetime.now(timezone.utc),
                extra_field="not allowed",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("3A-US1-FR002")
    def test_json_schema_export(self) -> None:
        """Contract: EnforcementResult MUST be exportable to JSON Schema.

        This enables IDE autocomplete and external validation.
        """
        from floe_core.enforcement.result import EnforcementResult

        schema = EnforcementResult.model_json_schema()

        assert "properties" in schema
        assert "passed" in schema["properties"]
        assert "violations" in schema["properties"]
        assert "summary" in schema["properties"]
        assert "enforcement_level" in schema["properties"]


# ==============================================================================
# Epic 3B: EnforcementResultSummary Contract Tests (T064)
# ==============================================================================


class TestEnforcementResultSummarySchemaContract:
    """Contract tests for EnforcementResultSummary schema stability.

    EnforcementResultSummary is a lightweight summary included in CompiledArtifacts.
    It provides essential metrics without full violation details.

    Task: T064
    Requirements: FR-024 (Pipeline Integration)
    """

    @pytest.mark.requirement("003b-FR-024")
    def test_enforcement_result_summary_has_required_fields(self) -> None:
        """Contract: EnforcementResultSummary MUST have all required fields.

        Required fields:
        - passed: bool
        - error_count: int
        - warning_count: int
        - policy_types_checked: list[str]
        - models_validated: int
        - enforcement_level: Literal["off", "warn", "strict"]
        """
        from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

        summary = EnforcementResultSummary(
            passed=True,
            error_count=0,
            warning_count=3,
            policy_types_checked=["naming", "coverage", "documentation"],
            models_validated=50,
            enforcement_level="strict",
        )

        # All required fields accessible
        assert hasattr(summary, "passed")
        assert hasattr(summary, "error_count")
        assert hasattr(summary, "warning_count")
        assert hasattr(summary, "policy_types_checked")
        assert hasattr(summary, "models_validated")
        assert hasattr(summary, "enforcement_level")

    @pytest.mark.requirement("003b-FR-024")
    def test_enforcement_result_summary_serializable_to_json(self) -> None:
        """Contract: EnforcementResultSummary MUST be JSON-serializable.

        Downstream consumers need to access this from CompiledArtifacts JSON.
        """
        from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

        summary = EnforcementResultSummary(
            passed=False,
            error_count=5,
            warning_count=10,
            policy_types_checked=["naming", "coverage"],
            models_validated=100,
            enforcement_level="warn",
        )

        # Should serialize without error
        json_str = summary.model_dump_json()
        assert isinstance(json_str, str)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["passed"] is False
        assert parsed["error_count"] == 5
        assert parsed["warning_count"] == 10
        assert parsed["models_validated"] == 100

    @pytest.mark.requirement("003b-FR-024")
    def test_enforcement_result_summary_immutable(self) -> None:
        """Contract: EnforcementResultSummary MUST be immutable (frozen=True).

        Results should not be modified after creation for audit integrity.
        """
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

        summary = EnforcementResultSummary(
            passed=True,
            error_count=0,
            warning_count=0,
            policy_types_checked=[],
            models_validated=0,
            enforcement_level="off",
        )

        with pytest.raises((AttributeError, ValidationError)):
            summary.passed = False  # type: ignore[misc]

    @pytest.mark.requirement("003b-FR-024")
    def test_enforcement_result_summary_extra_fields_forbidden(self) -> None:
        """Contract: EnforcementResultSummary MUST reject extra fields."""
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

        with pytest.raises(ValidationError, match="extra_field"):
            EnforcementResultSummary(
                passed=True,
                error_count=0,
                warning_count=0,
                policy_types_checked=[],
                models_validated=0,
                enforcement_level="warn",
                extra_field="not allowed",  # type: ignore[call-arg]
            )


class TestCreateEnforcementSummaryContract:
    """Contract tests for create_enforcement_summary helper function.

    This helper converts EnforcementResult to EnforcementResultSummary
    for inclusion in CompiledArtifacts.

    Task: T061, T064
    Requirements: FR-024 (Pipeline Integration)
    """

    @pytest.mark.requirement("003b-FR-024")
    def test_create_enforcement_summary_returns_valid_summary(self) -> None:
        """Contract: create_enforcement_summary MUST return valid EnforcementResultSummary."""
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
            create_enforcement_summary,
        )
        from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

        result = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="test",
                    message="Error",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E222",
                    severity="warning",
                    policy_type="documentation",
                    model_name="test2",
                    message="Warning",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(total_models=10, models_validated=10),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        summary = create_enforcement_summary(result)

        assert isinstance(summary, EnforcementResultSummary)
        assert summary.passed is False
        assert summary.error_count == 1
        assert summary.warning_count == 1
        assert summary.models_validated == 10
        assert summary.enforcement_level == "strict"

    @pytest.mark.requirement("003b-FR-024")
    def test_create_enforcement_summary_includes_policy_types(self) -> None:
        """Contract: create_enforcement_summary MUST include policy_types_checked."""
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
            create_enforcement_summary,
        )

        result = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="test",
                    message="Error",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E210",
                    severity="error",
                    policy_type="coverage",
                    model_name="test2",
                    message="Error",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(total_models=5, models_validated=5),
            enforcement_level="warn",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        summary = create_enforcement_summary(result)

        # Policy types should be sorted
        assert summary.policy_types_checked == ["coverage", "naming"]

    @pytest.mark.requirement("003b-FR-024")
    def test_create_enforcement_summary_handles_empty_violations(self) -> None:
        """Contract: create_enforcement_summary MUST handle empty violations list."""
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            create_enforcement_summary,
        )

        result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=50, models_validated=50),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        summary = create_enforcement_summary(result)

        assert summary.passed is True
        assert summary.error_count == 0
        assert summary.warning_count == 0
        # Should include default policy types when no violations
        assert len(summary.policy_types_checked) > 0


class TestCompiledArtifactsEnforcementFieldContract:
    """Contract tests for enforcement_result field in CompiledArtifacts.

    Task: T062, T064
    Requirements: FR-024, FR-025, FR-026 (Pipeline Integration)
    """

    @pytest.mark.requirement("003b-FR-024")
    def test_compiled_artifacts_has_enforcement_result_field(self) -> None:
        """Contract: CompiledArtifacts MUST have optional enforcement_result field."""
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Check field exists in model fields
        fields = CompiledArtifacts.model_fields
        assert "enforcement_result" in fields

        # Field should be optional (default None)
        assert fields["enforcement_result"].default is None

    @pytest.mark.requirement("003b-FR-024")
    def test_compiled_artifacts_version_is_0_3_0(self) -> None:
        """Contract: CompiledArtifacts version MUST be 0.3.0 for Epic 3B."""
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        # Check default version
        fields = CompiledArtifacts.model_fields
        assert fields["version"].default == "0.3.0"

    @pytest.mark.requirement("003b-FR-024")
    def test_compiled_artifacts_enforcement_result_serialization(self) -> None:
        """Contract: enforcement_result MUST serialize correctly in CompiledArtifacts."""
        from datetime import datetime

        from floe_core.schemas.compiled_artifacts import (
            CompilationMetadata,
            CompiledArtifacts,
            EnforcementResultSummary,
            ObservabilityConfig,
            PluginRef,
            ProductIdentity,
            ResolvedModel,
            ResolvedPlugins,
            ResolvedTransforms,
        )
        from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

        enforcement_summary = EnforcementResultSummary(
            passed=True,
            error_count=0,
            warning_count=2,
            policy_types_checked=["naming", "documentation"],
            models_validated=25,
            enforcement_level="warn",
        )

        artifacts = CompiledArtifacts(
            version="0.3.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.3.0",
                source_hash="sha256:abc123",
                product_name="test-product",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.test_product",
                domain="default",
                repository="https://github.com/test",
            ),
            mode="simple",
            inheritance_chain=[],
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    enabled=True,
                    resource_attributes=ResourceAttributes(
                        service_name="test",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="default",
                        floe_product_name="test",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage=True,
                lineage_namespace="test",
            ),
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.9.0"),
                orchestrator=PluginRef(type="dagster", version="1.5.0"),
            ),
            transforms=ResolvedTransforms(
                models=[ResolvedModel(name="test_model", compute="duckdb")],
                default_compute="duckdb",
            ),
            dbt_profiles={"default": {"target": "dev"}},
            enforcement_result=enforcement_summary,
        )

        # Should serialize without error
        json_str = artifacts.model_dump_json()
        parsed = json.loads(json_str)

        # Check enforcement_result is in output
        assert "enforcement_result" in parsed
        assert parsed["enforcement_result"]["passed"] is True
        assert parsed["enforcement_result"]["warning_count"] == 2
