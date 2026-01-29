"""Unit tests for contract drift detection integration.

Task: T066
Requirements: FR-021 (Schema drift detection), FR-022 (Type mapping),
              FR-023 (Missing columns), FR-024 (Extra columns)

Tests for drift detection integration in ContractValidator:
- validate_with_drift_detection method
- _extract_contract_columns helper
- _drift_result_to_violations converter
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from floe_core.schemas.data_contract import (
    SchemaComparisonResult,
    TypeMismatch,
)


def _install_fake_floe_iceberg(mock_drift_detector_cls: MagicMock) -> dict[str, ModuleType]:
    """Install a fake ``floe_iceberg.drift_detector`` into ``sys.modules``.

    Returns the mapping of injected module names so the caller can clean up.
    """
    pkg = ModuleType("floe_iceberg")
    sub = ModuleType("floe_iceberg.drift_detector")
    sub.DriftDetector = mock_drift_detector_cls  # type: ignore[attr-defined]
    pkg.drift_detector = sub  # type: ignore[attr-defined]
    modules = {"floe_iceberg": pkg, "floe_iceberg.drift_detector": sub}
    sys.modules.update(modules)
    return modules


class TestValidateWithDriftDetection:
    """Tests for ContractValidator.validate_with_drift_detection.

    Task: T066
    Requirements: FR-021, FR-022, FR-023, FR-024
    """

    @pytest.mark.requirement("3C-FR-021")
    def test_drift_detection_skipped_when_no_table_schema(self, tmp_path: Path) -> None:
        """Test that drift detection is skipped when no table schema provided."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        # Create a valid contract file
        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    physicalName: customers
    columns:
      - name: id
        logicalType: string
        required: true
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_yaml)

        validator = ContractValidator()
        result = validator.validate_with_drift_detection(
            contract_path=contract_path,
            table_schema=None,  # No table schema
        )

        # Should still be valid (drift detection skipped)
        assert result.valid is True
        assert len(result.violations) == 0

    @pytest.mark.requirement("3C-FR-021")
    def test_drift_detection_type_mismatch_detected(self, tmp_path: Path) -> None:
        """Test that type mismatches are detected during drift detection."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        # Create a contract with string type
        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    physicalName: customers
    columns:
      - name: id
        logicalType: string
        required: true
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_yaml)

        # Mock the DriftDetector to return a type mismatch
        mock_drift_result = SchemaComparisonResult(
            matches=False,
            type_mismatches=[
                TypeMismatch(
                    column="id",
                    contract_type="string",
                    table_type="integer",
                )
            ],
            missing_columns=[],
            extra_columns=[],
        )

        MockDriftDetector = MagicMock()
        mock_detector = MagicMock()
        mock_detector.compare_schemas.return_value = mock_drift_result
        MockDriftDetector.return_value = mock_detector

        fake_mods = _install_fake_floe_iceberg(MockDriftDetector)
        try:
            with patch(
                "floe_core.enforcement.validators.data_contracts.ContractValidator._extract_contract_columns"
            ) as mock_extract:
                mock_extract.return_value = [{"name": "id", "logicalType": "string"}]

                validator = ContractValidator()
                result = validator.validate_with_drift_detection(
                    contract_path=contract_path,
                    table_schema=MagicMock(),  # Mock table schema
                )
        finally:
            for mod_name in fake_mods:
                sys.modules.pop(mod_name, None)

        # Should have drift violation
        assert result.valid is False
        assert len(result.violations) >= 1

        drift_violation = next(
            (v for v in result.violations if v.error_code == "FLOE-E530"),
            None,
        )
        assert drift_violation is not None
        assert "id" in drift_violation.message
        assert drift_violation.expected == "string"
        assert drift_violation.actual == "integer"

    @pytest.mark.requirement("3C-FR-023")
    def test_drift_detection_missing_column_detected(self, tmp_path: Path) -> None:
        """Test that missing columns are detected during drift detection."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        # Create a contract with two columns
        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    physicalName: customers
    columns:
      - name: id
        logicalType: string
        required: true
      - name: email
        logicalType: string
        required: true
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_yaml)

        # Mock the DriftDetector to return a missing column
        mock_drift_result = SchemaComparisonResult(
            matches=False,
            type_mismatches=[],
            missing_columns=["email"],  # email is in contract but not in table
            extra_columns=[],
        )

        MockDriftDetector = MagicMock()
        mock_detector = MagicMock()
        mock_detector.compare_schemas.return_value = mock_drift_result
        MockDriftDetector.return_value = mock_detector

        fake_mods = _install_fake_floe_iceberg(MockDriftDetector)
        try:
            with patch(
                "floe_core.enforcement.validators.data_contracts.ContractValidator._extract_contract_columns"
            ) as mock_extract:
                mock_extract.return_value = [
                    {"name": "id", "logicalType": "string"},
                    {"name": "email", "logicalType": "string"},
                ]

                validator = ContractValidator()
                result = validator.validate_with_drift_detection(
                    contract_path=contract_path,
                    table_schema=MagicMock(),
                )
        finally:
            for mod_name in fake_mods:
                sys.modules.pop(mod_name, None)

        # Should have drift violation for missing column
        assert result.valid is False

        missing_violation = next(
            (v for v in result.violations if v.error_code == "FLOE-E531"),
            None,
        )
        assert missing_violation is not None
        assert "email" in missing_violation.message

    @pytest.mark.requirement("3C-FR-024")
    def test_drift_detection_extra_columns_do_not_fail(self, tmp_path: Path) -> None:
        """Test that extra columns in table don't cause validation failure."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    physicalName: customers
    columns:
      - name: id
        logicalType: string
        required: true
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_yaml)

        # Mock the DriftDetector to return extra columns (but matches=True)
        mock_drift_result = SchemaComparisonResult(
            matches=True,  # Extra columns don't fail validation
            type_mismatches=[],
            missing_columns=[],
            extra_columns=["created_at", "updated_at"],
        )

        MockDriftDetector = MagicMock()
        mock_detector = MagicMock()
        mock_detector.compare_schemas.return_value = mock_drift_result
        MockDriftDetector.return_value = mock_detector

        fake_mods = _install_fake_floe_iceberg(MockDriftDetector)
        try:
            with patch(
                "floe_core.enforcement.validators.data_contracts.ContractValidator._extract_contract_columns"
            ) as mock_extract:
                mock_extract.return_value = [{"name": "id", "logicalType": "string"}]

                validator = ContractValidator()
                result = validator.validate_with_drift_detection(
                    contract_path=contract_path,
                    table_schema=MagicMock(),
                )
        finally:
            for mod_name in fake_mods:
                sys.modules.pop(mod_name, None)

        # Should be valid (extra columns are informational only)
        assert result.valid is True
        assert len(result.violations) == 0

    @pytest.mark.requirement("3C-FR-021")
    def test_drift_detection_unavailable_gracefully_handled(self, tmp_path: Path) -> None:
        """Test that missing floe_iceberg doesn't cause hard failure."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: customers
    physicalName: customers
    columns:
      - name: id
        logicalType: string
        required: true
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_yaml)

        validator = ContractValidator()

        with patch(
            "floe_core.enforcement.validators.data_contracts.ContractValidator._extract_contract_columns"
        ) as mock_extract:
            mock_extract.return_value = [{"name": "id", "logicalType": "string"}]

            # Simulate ImportError for floe_iceberg.drift_detector
            # We patch builtins.__import__ to raise ImportError for floe_iceberg
            import builtins

            original_import = builtins.__import__

            def import_mock(
                name: str,
                globals_: dict[str, object] | None = None,
                locals_: dict[str, object] | None = None,
                fromlist: tuple[str, ...] = (),
                level: int = 0,
            ) -> object:
                if "floe_iceberg" in name:
                    raise ImportError(f"No module named '{name}'")
                return original_import(name, globals_, locals_, fromlist, level)

            with patch.object(builtins, "__import__", side_effect=import_mock):
                result = validator.validate_with_drift_detection(
                    contract_path=contract_path,
                    table_schema=MagicMock(),
                )

        # Should still be valid (drift detection skipped due to unavailability)
        assert result.valid is True


class TestExtractContractColumns:
    """Tests for ContractValidator._extract_contract_columns helper."""

    @pytest.mark.requirement("3C-FR-021")
    def test_extract_columns_from_schema(self) -> None:
        """Test extracting columns from contract schema."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator
        from floe_core.schemas.data_contract import DataContract

        # Create a mock contract with schema
        mock_contract = MagicMock(spec=DataContract)
        mock_schema = MagicMock()

        # Create property mocks with explicit attribute values
        prop1 = MagicMock()
        prop1.name = "id"
        prop1.logicalType = "string"

        prop2 = MagicMock()
        prop2.name = "email"
        prop2.logicalType = "string"

        prop3 = MagicMock()
        prop3.name = "age"
        prop3.logicalType = "integer"

        mock_schema.properties = [prop1, prop2, prop3]
        mock_contract.schema_ = [mock_schema]

        validator = ContractValidator()
        columns = validator._extract_contract_columns(mock_contract)

        assert len(columns) == 3
        assert columns[0]["name"] == "id"
        assert columns[0]["logicalType"] == "string"
        assert columns[2]["name"] == "age"
        assert columns[2]["logicalType"] == "integer"

    @pytest.mark.requirement("3C-FR-021")
    def test_extract_columns_empty_schema(self) -> None:
        """Test extracting columns from contract with no schema."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator
        from floe_core.schemas.data_contract import DataContract

        mock_contract = MagicMock(spec=DataContract)
        mock_contract.schema_ = None

        validator = ContractValidator()
        columns = validator._extract_contract_columns(mock_contract)

        assert columns == []


class TestDriftResultToViolations:
    """Tests for ContractValidator._drift_result_to_violations converter."""

    @pytest.mark.requirement("3C-FR-021")
    def test_type_mismatch_to_violation(self) -> None:
        """Test converting type mismatch to FLOE-E530 violation."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        drift_result = SchemaComparisonResult(
            matches=False,
            type_mismatches=[
                TypeMismatch(
                    column="user_id",
                    contract_type="string",
                    table_type="long",
                )
            ],
            missing_columns=[],
            extra_columns=[],
        )

        validator = ContractValidator()
        violations = validator._drift_result_to_violations(drift_result)

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E530"
        assert "user_id" in violations[0].message
        assert violations[0].expected == "string"
        assert violations[0].actual == "long"

    @pytest.mark.requirement("3C-FR-023")
    def test_missing_column_to_violation(self) -> None:
        """Test converting missing column to FLOE-E531 violation."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        drift_result = SchemaComparisonResult(
            matches=False,
            type_mismatches=[],
            missing_columns=["email", "phone"],
            extra_columns=[],
        )

        validator = ContractValidator()
        violations = validator._drift_result_to_violations(drift_result)

        assert len(violations) == 2
        assert all(v.error_code == "FLOE-E531" for v in violations)
        assert "email" in violations[0].message
        assert "phone" in violations[1].message

    @pytest.mark.requirement("3C-FR-021")
    def test_combined_violations(self) -> None:
        """Test converting multiple drift issues to violations."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        drift_result = SchemaComparisonResult(
            matches=False,
            type_mismatches=[
                TypeMismatch(
                    column="id",
                    contract_type="string",
                    table_type="integer",
                )
            ],
            missing_columns=["email"],
            extra_columns=["created_at"],  # Extra columns don't become violations
        )

        validator = ContractValidator()
        violations = validator._drift_result_to_violations(drift_result)

        assert len(violations) == 2  # 1 type mismatch + 1 missing column
        error_codes = [v.error_code for v in violations]
        assert "FLOE-E530" in error_codes
        assert "FLOE-E531" in error_codes


__all__ = [
    "TestValidateWithDriftDetection",
    "TestExtractContractColumns",
    "TestDriftResultToViolations",
]
