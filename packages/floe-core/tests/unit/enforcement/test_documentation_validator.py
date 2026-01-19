"""Unit tests for DocumentationValidator - TDD tests written first.

These tests define the expected behavior for DocumentationValidator before implementation.
They verify model description validation, column description validation, and
placeholder description detection.

Error Codes:
- FLOE-E220: Missing model description
- FLOE-E221: Missing column description
- FLOE-E222: Placeholder description detected (warning)

Task: T061, T062, T063, T064
Requirements: FR-005 (Documentation Enforcement), US5 (Documentation Validation)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_core.enforcement.result import Violation


def _create_model_node(
    name: str,
    description: str | None = None,
    columns: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Helper to create a model node for testing.

    Args:
        name: Model name (e.g., "bronze_orders").
        description: Model description (None = missing).
        columns: Column definitions with optional metadata.

    Returns:
        Model node dictionary matching dbt manifest structure.
    """
    node: dict[str, Any] = {
        "name": name,
        "resource_type": "model",
        "unique_id": f"model.test.{name}",
        "columns": columns or {},
    }
    if description is not None:
        node["description"] = description
    return node


def _create_column(
    name: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Helper to create a column definition for testing.

    Args:
        name: Column name.
        description: Column description (None = missing).

    Returns:
        Column definition dictionary.
    """
    col: dict[str, Any] = {"name": name}
    if description is not None:
        col["description"] = description
    return col


class TestModelDescriptionDetection:
    """Tests for model description detection (T061)."""

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_missing_model_description(self) -> None:
        """DocumentationValidator MUST detect missing model descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description=None)

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E220"
        assert violations[0].model_name == "bronze_orders"
        assert violations[0].policy_type == "documentation"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_empty_model_description(self) -> None:
        """DocumentationValidator MUST detect empty model descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description="")

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E220"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_whitespace_only_model_description(self) -> None:
        """DocumentationValidator MUST detect whitespace-only descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description="   \n\t  ")

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E220"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_passes_valid_model_description(self) -> None:
        """DocumentationValidator MUST pass models with valid descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description="Raw orders data from the e-commerce platform.",
        )

        violations = validator.validate(models=[model])

        assert violations == []

    @pytest.mark.requirement("3A-US5-FR005")
    def test_skips_validation_when_require_descriptions_false(self) -> None:
        """DocumentationValidator MUST skip when require_descriptions=False."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=False)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description=None)

        violations = validator.validate(models=[model])

        assert violations == []


class TestColumnDescriptionDetection:
    """Tests for column description detection (T062)."""

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_missing_column_description(self) -> None:
        """DocumentationValidator MUST detect missing column descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_column_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description="Orders data",
            columns={
                "id": _create_column("id", description=None),
                "customer_id": _create_column("customer_id", description="FK"),
            },
        )

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E221"
        assert violations[0].model_name == "bronze_orders"
        assert violations[0].column_name == "id"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_empty_column_description(self) -> None:
        """DocumentationValidator MUST detect empty column descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_column_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description="Orders data",
            columns={
                "id": _create_column("id", description=""),
            },
        )

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E221"
        assert violations[0].column_name == "id"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_multiple_missing_column_descriptions(self) -> None:
        """DocumentationValidator MUST detect all missing column descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_column_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description="Orders data",
            columns={
                "id": _create_column("id", description=None),
                "customer_id": _create_column("customer_id", description=None),
                "amount": _create_column("amount", description="Order total"),
            },
        )

        violations = validator.validate(models=[model])

        assert len(violations) == 2
        column_names = {v.column_name for v in violations}
        assert column_names == {"id", "customer_id"}

    @pytest.mark.requirement("3A-US5-FR005")
    def test_passes_valid_column_descriptions(self) -> None:
        """DocumentationValidator MUST pass columns with valid descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_column_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description="Orders data",
            columns={
                "id": _create_column("id", description="Primary key"),
                "customer_id": _create_column("customer_id", description="Foreign key"),
            },
        )

        violations = validator.validate(models=[model])

        assert violations == []

    @pytest.mark.requirement("3A-US5-FR005")
    def test_skips_column_validation_when_require_column_descriptions_false(
        self,
    ) -> None:
        """DocumentationValidator MUST skip when require_column_descriptions=False."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_column_descriptions=False)
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description="Orders data",
            columns={
                "id": _create_column("id", description=None),
            },
        )

        violations = validator.validate(models=[model])

        assert violations == []


class TestPlaceholderDescriptionDetection:
    """Tests for placeholder description detection (T063)."""

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_tbd_placeholder(self) -> None:
        """DocumentationValidator MUST detect TBD placeholders."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description="TBD")

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E222"
        assert violations[0].severity == "warning"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_todo_placeholder(self) -> None:
        """DocumentationValidator MUST detect TODO placeholders."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description="TODO: add docs")

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E222"
        assert violations[0].severity == "warning"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_fixme_placeholder(self) -> None:
        """DocumentationValidator MUST detect FIXME placeholders."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description="FIXME")

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E222"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_placeholder_case_insensitive(self) -> None:
        """DocumentationValidator MUST detect placeholders case-insensitively."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description="tbd - needs docs")

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E222"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_detects_column_placeholder(self) -> None:
        """DocumentationValidator MUST detect placeholders in column descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_column_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description="Orders data",
            columns={
                "id": _create_column("id", description="TODO"),
            },
        )

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E222"
        assert violations[0].column_name == "id"


class TestDocumentationTemplateSuggestion:
    """Tests for documentation template suggestion generation (T064)."""

    @pytest.mark.requirement("3A-US5-FR005")
    def test_suggests_model_description_template(self) -> None:
        """Violation MUST include suggestion for model documentation template."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description=None)

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        # Suggestion should include template or guidance
        assert "description" in violations[0].suggestion.lower()

    @pytest.mark.requirement("3A-US5-FR005")
    def test_suggests_column_description_template(self) -> None:
        """Violation MUST include suggestion for column documentation template."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_column_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description="Orders data",
            columns={
                "id": _create_column("id", description=None),
            },
        )

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert "description" in violations[0].suggestion.lower()

    @pytest.mark.requirement("3A-US5-FR005")
    def test_violation_expected_field(self) -> None:
        """Violation MUST include expected value."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description=None)

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        assert "description" in violations[0].expected.lower()

    @pytest.mark.requirement("3A-US5-FR005")
    def test_violation_actual_field(self) -> None:
        """Violation MUST include actual value (missing or placeholder)."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        model = _create_model_node(name="bronze_orders", description=None)

        violations = validator.validate(models=[model])

        assert len(violations) == 1
        # Actual should indicate missing or None
        actual_lower = violations[0].actual.lower()
        assert "missing" in actual_lower or "none" in actual_lower or "empty" in actual_lower


class TestDocumentationValidatorIntegration:
    """Integration tests for DocumentationValidator.validate() method."""

    @pytest.mark.requirement("3A-US5-FR005")
    def test_validate_returns_empty_when_all_documented(self) -> None:
        """DocumentationValidator.validate() MUST return empty list when all pass."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            require_descriptions=True,
            require_column_descriptions=True,
        )
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description="Raw orders data from e-commerce platform.",
            columns={
                "id": _create_column("id", description="Primary key"),
                "customer_id": _create_column("customer_id", description="Foreign key"),
            },
        )

        violations = validator.validate(models=[model])

        assert violations == []

    @pytest.mark.requirement("3A-US5-FR005")
    def test_validate_multiple_models(self) -> None:
        """DocumentationValidator.validate() MUST validate multiple models."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(require_descriptions=True)
        validator = DocumentationValidator(config)

        models = [
            _create_model_node(name="bronze_orders", description="Orders data"),
            _create_model_node(name="silver_customers", description=None),
            _create_model_node(name="gold_revenue", description="Revenue metrics"),
        ]

        violations = validator.validate(models=models)

        assert len(violations) == 1
        assert violations[0].model_name == "silver_customers"

    @pytest.mark.requirement("3A-US5-FR005")
    def test_validate_combined_model_and_column_checks(self) -> None:
        """DocumentationValidator MUST check both model and column descriptions."""
        from floe_core.enforcement.validators.documentation import (
            DocumentationValidator,
        )
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            require_descriptions=True,
            require_column_descriptions=True,
        )
        validator = DocumentationValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            description=None,  # Missing model description
            columns={
                "id": _create_column("id", description=None),  # Missing column desc
                "amount": _create_column("amount", description="Total"),
            },
        )

        violations = validator.validate(models=[model])

        # Should have violations for both model and column
        assert len(violations) == 2
        error_codes = {v.error_code for v in violations}
        assert "FLOE-E220" in error_codes  # Model
        assert "FLOE-E221" in error_codes  # Column


class TestDocumentationValidatorWithPolicyEnforcer:
    """Integration tests with PolicyEnforcer."""

    @pytest.mark.requirement("3A-US5-FR005")
    def test_documentation_validator_integrated_with_policy_enforcer(self) -> None:
        """DocumentationValidator MUST be wired into PolicyEnforcer.enforce()."""
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(enforcement="off"),  # Disable naming to focus on docs
            quality_gates=QualityGatesConfig(
                require_descriptions=True,
                minimum_test_coverage=0,  # Disable coverage check
            ),
        )

        enforcer = PolicyEnforcer(governance_config=governance)

        manifest = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.test.bronze_orders": {
                    "name": "bronze_orders",
                    "resource_type": "model",
                    "unique_id": "model.test.bronze_orders",
                    "columns": {},
                    # No description - should fail
                },
            },
        }

        result = enforcer.enforce(manifest)

        # Should have documentation violation
        doc_violations = [v for v in result.violations if v.policy_type == "documentation"]
        assert len(doc_violations) >= 1
        assert any(v.error_code == "FLOE-E220" for v in doc_violations)
