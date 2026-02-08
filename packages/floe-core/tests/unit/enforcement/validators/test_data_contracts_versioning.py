"""Unit tests for contract versioning validation.

Task: T046, T047, T048
Requirements: FR-015 (Baseline comparison), FR-016 (Breaking changes),
              FR-017 (Non-breaking changes), FR-018 (Patch changes),
              FR-019 (Semantic versioning), FR-020 (FLOE-E520 error)

Tests for semantic versioning rules:
- Breaking changes require MAJOR bump (remove column, change type, make optional required)
- Non-breaking changes require MINOR bump (add optional column, make required optional)
- Patch changes allow PATCH bump (documentation, tags, links)
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestBreakingChangeDetection:
    """Tests for breaking change detection (FR-016, FR-020).

    Task: T046

    Breaking changes require MAJOR version bump:
    - Remove a field/column
    - Change a field's type
    - Make an optional field required
    - Weaken an SLA property
    """

    @pytest.mark.requirement("3C-FR-016")
    def test_column_removal_detected_as_breaking(self) -> None:
        """Test that removing a column is detected as breaking change.

        Baseline: has columns [id, email, name]
        Current: has columns [id, email] (name removed)

        Expected: FLOE-E520 breaking change error
        """
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
      - name: name
        logicalType: string
"""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.1
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        violation = result.violations[0]
        assert violation.error_code == "FLOE-E520"
        assert (
            "name" in violation.message.lower()
            or "removed" in violation.message.lower()
        )

    @pytest.mark.requirement("3C-FR-016")
    def test_type_change_detected_as_breaking(self) -> None:
        """Test that changing a column type is detected as breaking change.

        Baseline: age is integer
        Current: age is string

        Expected: FLOE-E520 breaking change error
        """
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: age
        logicalType: integer
"""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.1
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: age
        logicalType: string
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        violation = result.violations[0]
        assert violation.error_code == "FLOE-E520"
        assert "type" in violation.message.lower() or "age" in violation.message.lower()

    @pytest.mark.requirement("3C-FR-016")
    def test_optional_to_required_detected_as_breaking(self) -> None:
        """Test that making optional field required is detected as breaking.

        Baseline: email is optional (required=False)
        Current: email is required (required=True)

        Expected: FLOE-E520 breaking change error
        """
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
        required: true
      - name: email
        logicalType: string
        required: false
"""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.1
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
        required: true
      - name: email
        logicalType: string
        required: true
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        violation = result.violations[0]
        assert violation.error_code == "FLOE-E520"


class TestNonBreakingChangeDetection:
    """Tests for non-breaking change detection (FR-017).

    Task: T047

    Non-breaking changes require MINOR version bump:
    - Add a new optional field
    - Make a required field optional
    - Add stricter SLA (strengthening)
    """

    @pytest.mark.requirement("3C-FR-017")
    def test_add_optional_column_is_non_breaking(self) -> None:
        """Test that adding optional column is detected as non-breaking.

        Baseline: has columns [id]
        Current: has columns [id, email] (email added, optional)

        Expected: Non-breaking change, requires MINOR bump
        """
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.1.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        # Non-breaking changes are valid if MINOR was bumped
        assert result.valid is True

    @pytest.mark.requirement("3C-FR-017")
    def test_required_to_optional_is_non_breaking(self) -> None:
        """Test that making required field optional is non-breaking.

        Baseline: email is required (required=True)
        Current: email is optional (required=False)

        Expected: Non-breaking change, requires MINOR bump
        """
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
        required: true
      - name: email
        logicalType: string
        required: true
"""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.1.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
        required: true
      - name: email
        logicalType: string
        required: false
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        assert result.valid is True


class TestPatchChangeDetection:
    """Tests for patch change detection (FR-018).

    Task: T048

    Patch changes allow PATCH version bump:
    - Documentation changes only
    - Tag changes only
    - Link changes only
    """

    @pytest.mark.requirement("3C-FR-018")
    def test_description_change_is_patch(self) -> None:
        """Test that changing description is detected as patch change.

        Baseline: description = "Old description"
        Current: description = "New description"

        Expected: Patch change, PATCH bump sufficient
        """
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
description:
  purpose: Old description
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.1
name: test-contract
status: active
description:
  purpose: New description with more detail
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        # Patch change with PATCH bump is valid
        assert result.valid is True

    @pytest.mark.requirement("3C-FR-018")
    def test_tag_change_is_patch(self) -> None:
        """Test that changing tags is detected as patch change."""
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
tags:
  - production
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.1
name: test-contract
status: active
tags:
  - production
  - gold-tier
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        assert result.valid is True


class TestSemanticVersioningEnforcement:
    """Tests for semantic versioning rule enforcement (FR-019, FR-020).

    Task: T049
    """

    @pytest.mark.requirement("3C-FR-019")
    def test_breaking_change_requires_major_bump(self) -> None:
        """Test that breaking change without MAJOR bump fails.

        Breaking change: remove column
        Version change: 1.0.0 -> 1.0.1 (PATCH only)

        Expected: FLOE-E520 error - MAJOR bump required
        """
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
"""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.1
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        assert result.valid is False
        assert any(v.error_code == "FLOE-E520" for v in result.violations)

    @pytest.mark.requirement("3C-FR-019")
    def test_breaking_change_with_major_bump_passes(self) -> None:
        """Test that breaking change with MAJOR bump passes.

        Breaking change: remove column
        Version change: 1.0.0 -> 2.0.0 (MAJOR)

        Expected: Valid
        """
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
"""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 2.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        assert result.valid is True

    @pytest.mark.requirement("3C-FR-015")
    def test_first_registration_always_valid(self) -> None:
        """Test that first registration (no baseline) is always valid."""
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.versioning import VersioningValidator

        validator = VersioningValidator()
        result = validator.validate_version_change(
            baseline_yaml=None,  # No baseline = first registration
            current_yaml=current_yaml,
        )

        assert result.valid is True


class TestContractValidatorVersioningIntegration:
    """Tests for ContractValidator.validate_with_versioning() integration.

    Task: T054, T055
    """

    @pytest.mark.requirement("3C-FR-015")
    def test_validate_with_versioning_first_registration(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that first registration (no baseline) passes validation."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        # Create contract file
        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        contract_file = tmp_path / "datacontract.yaml"
        contract_file.write_text(contract_yaml)

        validator = ContractValidator()
        result = validator.validate_with_versioning(
            contract_path=contract_file,
            baseline_path=None,  # First registration
        )

        assert result.valid is True

    @pytest.mark.requirement("3C-FR-020")
    def test_validate_with_versioning_breaking_change(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that breaking change without major bump fails."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        # Baseline contract
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
"""
        baseline_file = tmp_path / "baseline" / "datacontract.yaml"
        baseline_file.parent.mkdir(parents=True)
        baseline_file.write_text(baseline_yaml)

        # Current contract (email removed - breaking change)
        current_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.1
name: test-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        current_file = tmp_path / "datacontract.yaml"
        current_file.write_text(current_yaml)

        validator = ContractValidator()
        result = validator.validate_with_versioning(
            contract_path=current_file,
            baseline_path=baseline_file,
        )

        assert result.valid is False
        assert any(v.error_code == "FLOE-E520" for v in result.violations)

    @pytest.mark.requirement("3C-FR-015")
    def test_get_baseline_from_catalog_not_found(self, tmp_path: Path) -> None:
        """Test that missing baseline returns None."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        validator = ContractValidator()
        result = validator.get_baseline_from_catalog(
            contract_id="nonexistent",
            catalog_path=tmp_path,
        )

        assert result is None

    @pytest.mark.requirement("3C-FR-015")
    def test_get_baseline_from_catalog_found(self, tmp_path: Path) -> None:
        """Test that existing baseline is returned."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        # Create baseline in catalog
        baseline_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
"""
        baseline_file = tmp_path / "test-contract.yaml"
        baseline_file.write_text(baseline_yaml)

        validator = ContractValidator()
        result = validator.get_baseline_from_catalog(
            contract_id="test-contract",
            catalog_path=tmp_path,
        )

        assert result is not None
        assert "test-contract" in result


__all__ = [
    "TestBreakingChangeDetection",
    "TestNonBreakingChangeDetection",
    "TestPatchChangeDetection",
    "TestSemanticVersioningEnforcement",
    "TestContractValidatorVersioningIntegration",
]
