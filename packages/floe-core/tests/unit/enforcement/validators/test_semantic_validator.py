"""Unit tests for SemanticValidator - TDD tests written first.

Tests for semantic validation of dbt manifest:
- FR-001: ref() resolution validation (T014, T018)
- FR-002: Circular dependency detection (T015, T019)
- FR-003: source() resolution validation (T016, T020)

These tests are written BEFORE implementation (TDD).
They will FAIL until T017-T020 implement SemanticValidator.

Task: T014, T015, T016
Requirements: FR-001, FR-002, FR-003, FR-004
"""

from __future__ import annotations

from typing import Any

import pytest

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def valid_manifest() -> dict[str, Any]:
    """Create a valid dbt manifest with models and sources.

    This manifest has proper ref() and source() relationships:
    - bronze_orders references source.raw.orders
    - silver_orders references bronze_orders
    - gold_orders references silver_orders
    """
    return {
        "metadata": {
            "dbt_version": "1.8.0",
            "generated_at": "2026-01-20T00:00:00Z",
            "invocation_id": "test-id",
        },
        "nodes": {
            "model.my_project.bronze_orders": {
                "name": "bronze_orders",
                "resource_type": "model",
                "package_name": "my_project",
                "unique_id": "model.my_project.bronze_orders",
                "depends_on": {
                    "nodes": ["source.my_project.raw.orders"],
                },
            },
            "model.my_project.silver_orders": {
                "name": "silver_orders",
                "resource_type": "model",
                "package_name": "my_project",
                "unique_id": "model.my_project.silver_orders",
                "depends_on": {
                    "nodes": ["model.my_project.bronze_orders"],
                },
            },
            "model.my_project.gold_orders": {
                "name": "gold_orders",
                "resource_type": "model",
                "package_name": "my_project",
                "unique_id": "model.my_project.gold_orders",
                "depends_on": {
                    "nodes": ["model.my_project.silver_orders"],
                },
            },
        },
        "sources": {
            "source.my_project.raw.orders": {
                "name": "orders",
                "source_name": "raw",
                "resource_type": "source",
                "package_name": "my_project",
                "unique_id": "source.my_project.raw.orders",
            },
        },
        "child_map": {
            "source.my_project.raw.orders": ["model.my_project.bronze_orders"],
            "model.my_project.bronze_orders": ["model.my_project.silver_orders"],
            "model.my_project.silver_orders": ["model.my_project.gold_orders"],
        },
        "parent_map": {
            "model.my_project.bronze_orders": ["source.my_project.raw.orders"],
            "model.my_project.silver_orders": ["model.my_project.bronze_orders"],
            "model.my_project.gold_orders": ["model.my_project.silver_orders"],
        },
    }


@pytest.fixture
def manifest_with_missing_ref() -> dict[str, Any]:
    """Create manifest with an invalid ref() to missing model."""
    return {
        "metadata": {
            "dbt_version": "1.8.0",
            "generated_at": "2026-01-20T00:00:00Z",
            "invocation_id": "test-id",
        },
        "nodes": {
            "model.my_project.silver_orders": {
                "name": "silver_orders",
                "resource_type": "model",
                "package_name": "my_project",
                "unique_id": "model.my_project.silver_orders",
                "depends_on": {
                    # References bronze_orders which doesn't exist
                    "nodes": ["model.my_project.bronze_orders"],
                },
            },
        },
        "sources": {},
        "child_map": {},
        "parent_map": {
            "model.my_project.silver_orders": ["model.my_project.bronze_orders"],
        },
    }


@pytest.fixture
def manifest_with_circular_dependency() -> dict[str, Any]:
    """Create manifest with a circular dependency.

    Cycle: model_a -> model_b -> model_c -> model_a
    """
    return {
        "metadata": {
            "dbt_version": "1.8.0",
            "generated_at": "2026-01-20T00:00:00Z",
            "invocation_id": "test-id",
        },
        "nodes": {
            "model.my_project.model_a": {
                "name": "model_a",
                "resource_type": "model",
                "package_name": "my_project",
                "unique_id": "model.my_project.model_a",
                "depends_on": {
                    "nodes": ["model.my_project.model_c"],
                },
            },
            "model.my_project.model_b": {
                "name": "model_b",
                "resource_type": "model",
                "package_name": "my_project",
                "unique_id": "model.my_project.model_b",
                "depends_on": {
                    "nodes": ["model.my_project.model_a"],
                },
            },
            "model.my_project.model_c": {
                "name": "model_c",
                "resource_type": "model",
                "package_name": "my_project",
                "unique_id": "model.my_project.model_c",
                "depends_on": {
                    "nodes": ["model.my_project.model_b"],
                },
            },
        },
        "sources": {},
        "child_map": {
            "model.my_project.model_a": ["model.my_project.model_b"],
            "model.my_project.model_b": ["model.my_project.model_c"],
            "model.my_project.model_c": ["model.my_project.model_a"],
        },
        "parent_map": {
            "model.my_project.model_a": ["model.my_project.model_c"],
            "model.my_project.model_b": ["model.my_project.model_a"],
            "model.my_project.model_c": ["model.my_project.model_b"],
        },
    }


@pytest.fixture
def manifest_with_missing_source() -> dict[str, Any]:
    """Create manifest with an invalid source() to missing source."""
    return {
        "metadata": {
            "dbt_version": "1.8.0",
            "generated_at": "2026-01-20T00:00:00Z",
            "invocation_id": "test-id",
        },
        "nodes": {
            "model.my_project.bronze_orders": {
                "name": "bronze_orders",
                "resource_type": "model",
                "package_name": "my_project",
                "unique_id": "model.my_project.bronze_orders",
                "depends_on": {
                    # References source that doesn't exist
                    "nodes": ["source.my_project.raw.orders"],
                },
            },
        },
        "sources": {},  # No sources defined!
        "child_map": {},
        "parent_map": {
            "model.my_project.bronze_orders": ["source.my_project.raw.orders"],
        },
    }


# =============================================================================
# T014: Tests for validate_refs() - FR-001
# =============================================================================


class TestValidateRefs:
    """Tests for SemanticValidator.validate_refs().

    FR-001: System MUST validate model references (via ref())
    resolve to existing models in the manifest.

    Error code: FLOE-E301
    """

    @pytest.mark.requirement("003b-FR-001")
    def test_valid_refs_no_violations(self, valid_manifest: dict[str, Any]) -> None:
        """Test valid ref() references produce no violations.

        Given a manifest where all ref() calls resolve to existing models,
        When validating refs,
        Then no violations are generated.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_refs(valid_manifest)

        assert violations == []

    @pytest.mark.requirement("003b-FR-001")
    def test_missing_ref_generates_violation(
        self, manifest_with_missing_ref: dict[str, Any]
    ) -> None:
        """Test invalid ref() to missing model generates FLOE-E301.

        Given a manifest where a model refs a non-existent model,
        When validating refs,
        Then a FLOE-E301 violation is generated with model name.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_refs(manifest_with_missing_ref)

        assert len(violations) == 1
        violation = violations[0]
        assert violation.error_code == "FLOE-E301"
        assert violation.policy_type == "semantic"
        assert violation.model_name == "silver_orders"
        assert "bronze_orders" in violation.message

    @pytest.mark.requirement("003b-FR-001")
    def test_missing_ref_includes_missing_model_name(
        self, manifest_with_missing_ref: dict[str, Any]
    ) -> None:
        """Test FLOE-E301 error message includes missing model name.

        Given a manifest with invalid ref(),
        When validating refs,
        Then the violation message specifies which model is missing.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_refs(manifest_with_missing_ref)

        assert len(violations) == 1
        violation = violations[0]
        # Error should mention the missing model
        assert "bronze_orders" in violation.expected or "bronze_orders" in violation.actual

    @pytest.mark.requirement("003b-FR-001")
    def test_missing_ref_has_actionable_suggestion(
        self, manifest_with_missing_ref: dict[str, Any]
    ) -> None:
        """Test FLOE-E301 includes actionable remediation suggestion.

        Given a manifest with invalid ref(),
        When validating refs,
        Then the violation includes a suggestion for fixing it.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_refs(manifest_with_missing_ref)

        assert len(violations) == 1
        violation = violations[0]
        # Suggestion should be non-empty and actionable
        assert len(violation.suggestion) > 0
        assert "ref" in violation.suggestion.lower() or "model" in violation.suggestion.lower()

    @pytest.mark.requirement("003b-FR-001")
    def test_multiple_missing_refs_generate_multiple_violations(self) -> None:
        """Test multiple invalid refs generate multiple violations.

        Given a manifest with two models each referencing missing models,
        When validating refs,
        Then two FLOE-E301 violations are generated.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.model_a": {
                    "name": "model_a",
                    "resource_type": "model",
                    "unique_id": "model.my_project.model_a",
                    "depends_on": {"nodes": ["model.my_project.missing_x"]},
                },
                "model.my_project.model_b": {
                    "name": "model_b",
                    "resource_type": "model",
                    "unique_id": "model.my_project.model_b",
                    "depends_on": {"nodes": ["model.my_project.missing_y"]},
                },
            },
            "sources": {},
            "child_map": {},
            "parent_map": {},
        }

        validator = SemanticValidator()
        violations = validator.validate_refs(manifest)

        assert len(violations) == 2
        error_codes = {v.error_code for v in violations}
        assert error_codes == {"FLOE-E301"}

    @pytest.mark.requirement("003b-FR-001")
    def test_ref_to_source_is_not_error(self, valid_manifest: dict[str, Any]) -> None:
        """Test that dependency on source is handled correctly.

        Given a model depends on a source (not another model),
        When validating refs,
        Then no FLOE-E301 is generated (source validation is separate).
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_refs(valid_manifest)

        # Should not flag source dependencies as missing refs
        assert violations == []


# =============================================================================
# T015: Tests for detect_circular_deps() - FR-002
# =============================================================================


class TestDetectCircularDeps:
    """Tests for SemanticValidator.detect_circular_deps().

    FR-002: System MUST detect circular dependencies between models
    and report the cycle path.

    Error code: FLOE-E302
    """

    @pytest.mark.requirement("003b-FR-002")
    def test_no_circular_deps_no_violations(self, valid_manifest: dict[str, Any]) -> None:
        """Test acyclic dependency graph produces no violations.

        Given a manifest with valid DAG structure (no cycles),
        When detecting circular dependencies,
        Then no violations are generated.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.detect_circular_deps(valid_manifest)

        assert violations == []

    @pytest.mark.requirement("003b-FR-002")
    def test_circular_dependency_generates_violation(
        self, manifest_with_circular_dependency: dict[str, Any]
    ) -> None:
        """Test circular dependency generates FLOE-E302.

        Given a manifest with cycle: model_a -> model_b -> model_c -> model_a,
        When detecting circular dependencies,
        Then a FLOE-E302 violation is generated.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.detect_circular_deps(manifest_with_circular_dependency)

        assert len(violations) >= 1
        violation = violations[0]
        assert violation.error_code == "FLOE-E302"
        assert violation.policy_type == "semantic"

    @pytest.mark.requirement("003b-FR-002")
    def test_circular_dependency_includes_cycle_path(
        self, manifest_with_circular_dependency: dict[str, Any]
    ) -> None:
        """Test FLOE-E302 message includes the cycle path.

        Given a manifest with cycle: model_a -> model_b -> model_c -> model_a,
        When detecting circular dependencies,
        Then the violation message includes all models in the cycle.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.detect_circular_deps(manifest_with_circular_dependency)

        assert len(violations) >= 1
        violation = violations[0]
        # Message should mention the cycle participants
        message_lower = violation.message.lower()
        assert (
            "model_a" in message_lower or "model_b" in message_lower or "model_c" in message_lower
        )

    @pytest.mark.requirement("003b-FR-002")
    def test_self_referencing_model_generates_violation(self) -> None:
        """Test self-referencing model (model refs itself) generates violation.

        Given a model that depends on itself,
        When detecting circular dependencies,
        Then a FLOE-E302 violation is generated.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.self_ref": {
                    "name": "self_ref",
                    "resource_type": "model",
                    "unique_id": "model.my_project.self_ref",
                    "depends_on": {"nodes": ["model.my_project.self_ref"]},
                },
            },
            "sources": {},
            "child_map": {"model.my_project.self_ref": ["model.my_project.self_ref"]},
            "parent_map": {"model.my_project.self_ref": ["model.my_project.self_ref"]},
        }

        validator = SemanticValidator()
        violations = validator.detect_circular_deps(manifest)

        assert len(violations) >= 1
        assert violations[0].error_code == "FLOE-E302"

    @pytest.mark.requirement("003b-FR-002")
    def test_circular_dependency_has_actionable_suggestion(
        self, manifest_with_circular_dependency: dict[str, Any]
    ) -> None:
        """Test FLOE-E302 includes actionable remediation suggestion.

        Given a manifest with circular dependency,
        When detecting circular dependencies,
        Then the violation includes a suggestion for breaking the cycle.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.detect_circular_deps(manifest_with_circular_dependency)

        assert len(violations) >= 1
        violation = violations[0]
        assert len(violation.suggestion) > 0


# =============================================================================
# T016: Tests for validate_sources() - FR-003
# =============================================================================


class TestValidateSources:
    """Tests for SemanticValidator.validate_sources().

    FR-003: System MUST validate source references (via source())
    resolve to defined sources.

    Error code: FLOE-E303
    """

    @pytest.mark.requirement("003b-FR-003")
    def test_valid_sources_no_violations(self, valid_manifest: dict[str, Any]) -> None:
        """Test valid source() references produce no violations.

        Given a manifest where all source() calls resolve to defined sources,
        When validating sources,
        Then no violations are generated.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_sources(valid_manifest)

        assert violations == []

    @pytest.mark.requirement("003b-FR-003")
    def test_missing_source_generates_violation(
        self, manifest_with_missing_source: dict[str, Any]
    ) -> None:
        """Test invalid source() to missing source generates FLOE-E303.

        Given a manifest where a model references an undefined source,
        When validating sources,
        Then a FLOE-E303 violation is generated.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_sources(manifest_with_missing_source)

        assert len(violations) == 1
        violation = violations[0]
        assert violation.error_code == "FLOE-E303"
        assert violation.policy_type == "semantic"
        assert violation.model_name == "bronze_orders"

    @pytest.mark.requirement("003b-FR-003")
    def test_missing_source_includes_source_name(
        self, manifest_with_missing_source: dict[str, Any]
    ) -> None:
        """Test FLOE-E303 error message includes missing source name.

        Given a manifest with invalid source(),
        When validating sources,
        Then the violation message specifies which source is missing.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_sources(manifest_with_missing_source)

        assert len(violations) == 1
        violation = violations[0]
        # Error should mention the missing source
        assert "raw" in violation.message or "orders" in violation.message

    @pytest.mark.requirement("003b-FR-003")
    def test_missing_source_has_actionable_suggestion(
        self, manifest_with_missing_source: dict[str, Any]
    ) -> None:
        """Test FLOE-E303 includes actionable remediation suggestion.

        Given a manifest with invalid source(),
        When validating sources,
        Then the violation includes a suggestion for fixing it.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_sources(manifest_with_missing_source)

        assert len(violations) == 1
        violation = violations[0]
        assert len(violation.suggestion) > 0
        assert "source" in violation.suggestion.lower() or "define" in violation.suggestion.lower()

    @pytest.mark.requirement("003b-FR-003")
    def test_multiple_missing_sources_generate_multiple_violations(self) -> None:
        """Test multiple invalid sources generate multiple violations.

        Given a manifest with two models each referencing missing sources,
        When validating sources,
        Then two FLOE-E303 violations are generated.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.model_a": {
                    "name": "model_a",
                    "resource_type": "model",
                    "unique_id": "model.my_project.model_a",
                    "depends_on": {"nodes": ["source.my_project.missing.source_a"]},
                },
                "model.my_project.model_b": {
                    "name": "model_b",
                    "resource_type": "model",
                    "unique_id": "model.my_project.model_b",
                    "depends_on": {"nodes": ["source.my_project.missing.source_b"]},
                },
            },
            "sources": {},
            "child_map": {},
            "parent_map": {},
        }

        validator = SemanticValidator()
        violations = validator.validate_sources(manifest)

        assert len(violations) == 2
        error_codes = {v.error_code for v in violations}
        assert error_codes == {"FLOE-E303"}


# =============================================================================
# Tests for validate() - combined validation
# =============================================================================


class TestSemanticValidatorValidate:
    """Tests for SemanticValidator.validate() combined method.

    The validate() method runs all semantic checks:
    - validate_refs()
    - detect_circular_deps()
    - validate_sources()
    """

    @pytest.mark.requirement("003b-FR-001")
    @pytest.mark.requirement("003b-FR-002")
    @pytest.mark.requirement("003b-FR-003")
    def test_validate_runs_all_checks(self, valid_manifest: dict[str, Any]) -> None:
        """Test validate() runs all semantic validation checks.

        Given a valid manifest,
        When calling validate(),
        Then all checks pass with no violations.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate(valid_manifest)

        assert violations == []

    @pytest.mark.requirement("003b-FR-001")
    @pytest.mark.requirement("003b-FR-003")
    def test_validate_combines_all_violations(self) -> None:
        """Test validate() combines violations from all checks.

        Given a manifest with both missing ref and missing source,
        When calling validate(),
        Then violations from both checks are returned.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        # Manifest with both issues
        manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.model_a": {
                    "name": "model_a",
                    "resource_type": "model",
                    "unique_id": "model.my_project.model_a",
                    "depends_on": {
                        "nodes": [
                            "model.my_project.missing_model",  # Missing ref
                            "source.my_project.missing.source",  # Missing source
                        ]
                    },
                },
            },
            "sources": {},
            "child_map": {},
            "parent_map": {},
        }

        validator = SemanticValidator()
        violations = validator.validate(manifest)

        error_codes = {v.error_code for v in violations}
        # Should have both E301 (missing ref) and E303 (missing source)
        assert "FLOE-E301" in error_codes
        assert "FLOE-E303" in error_codes

    @pytest.mark.requirement("003b-FR-004")
    def test_violations_have_severity_error(
        self, manifest_with_missing_ref: dict[str, Any]
    ) -> None:
        """Test semantic violations have error severity by default.

        Given semantic validation finds issues,
        When violations are generated,
        Then they have severity='error'.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_refs(manifest_with_missing_ref)

        assert len(violations) == 1
        assert violations[0].severity == "error"

    @pytest.mark.requirement("003b-FR-004")
    def test_violations_have_documentation_url(
        self, manifest_with_missing_ref: dict[str, Any]
    ) -> None:
        """Test semantic violations include documentation URL.

        Given semantic validation finds issues,
        When violations are generated,
        Then they include a documentation URL.
        """
        from floe_core.enforcement.validators.semantic import SemanticValidator

        validator = SemanticValidator()
        violations = validator.validate_refs(manifest_with_missing_ref)

        assert len(violations) == 1
        assert violations[0].documentation_url.startswith("https://")
