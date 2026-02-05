"""Contract tests for DriftDetector import boundary resilience.

Task: T120
Requirements: BOUNDARY-001 (DriftDetector lazy import pattern)

Tests that the ContractValidator in floe-core degrades gracefully
when floe-iceberg is not installed. The lazy import pattern at
data_contracts.py ensures floe-core functions independently.
"""

from __future__ import annotations

from typing import Any

import pytest


class TestDriftDetectorImportResilience:
    """Contract tests for DriftDetector import boundary.

    Validates that the ContractValidator in floe-core handles
    the optional floe-iceberg dependency gracefully via lazy import.
    """

    @pytest.mark.requirement("004d-BOUNDARY-001")
    def test_contract_validator_importable_without_floe_iceberg(self) -> None:
        """Test that ContractValidator is importable regardless of floe_iceberg.

        The lazy import in validate_with_drift_detection() catches ImportError,
        so floe-core's ContractValidator should always be importable.
        """
        from floe_core.enforcement.validators.data_contracts import (
            ContractValidator,
        )

        validator = ContractValidator()
        assert hasattr(validator, "validate")
        assert hasattr(validator, "validate_with_drift_detection")

    @pytest.mark.requirement("004d-BOUNDARY-001")
    def test_drift_detector_lazy_import_does_not_pollute_namespace(self) -> None:
        """Test that the lazy import doesn't add floe_iceberg to data_contracts namespace.

        floe_core should not eagerly import floe_iceberg at module level,
        ensuring the packages remain loosely coupled.
        """
        import floe_core.enforcement.validators.data_contracts as dc_module

        # DriftDetector should NOT be in the module's global namespace
        module_attrs = dir(dc_module)
        assert "DriftDetector" not in module_attrs, (
            "DriftDetector should not be in module-level namespace — "
            "it must be lazily imported inside the method"
        )

    @pytest.mark.requirement("004d-BOUNDARY-001")
    def test_contract_validator_has_drift_detection_method(self) -> None:
        """Test that ContractValidator exposes validate_with_drift_detection.

        The method signature accepts an optional table_schema parameter,
        allowing drift detection to be skipped when no table exists.
        """
        import inspect

        from floe_core.enforcement.validators.data_contracts import (
            ContractValidator,
        )

        method = getattr(ContractValidator, "validate_with_drift_detection", None)
        assert method is not None, (
            "ContractValidator must have validate_with_drift_detection method"
        )

        sig = inspect.signature(method)
        assert "table_schema" in sig.parameters, (
            "validate_with_drift_detection must accept table_schema parameter"
        )
        # table_schema should default to None (drift detection is optional)
        param = sig.parameters["table_schema"]
        assert param.default is None, (
            "table_schema should default to None for graceful degradation"
        )


class TestDriftDetectorExportBoundary:
    """Tests that DriftDetector export from floe-iceberg follows the boundary contract.

    These tests verify the "other side" of the boundary — that floe-iceberg
    correctly exports DriftDetector for consumers that do have it installed.
    """

    @pytest.mark.requirement("004d-BOUNDARY-001")
    def test_drift_detector_importable_when_installed(self) -> None:
        """Test that DriftDetector is importable from floe_iceberg when available."""
        from floe_iceberg.drift_detector import DriftDetector

        detector = DriftDetector()
        assert hasattr(detector, "compare_schemas")

    @pytest.mark.requirement("004d-BOUNDARY-001")
    def test_drift_detector_uses_floe_core_types(self) -> None:
        """Test that DriftDetector returns floe-core types (not its own).

        This ensures the boundary contract: floe-iceberg depends on floe-core
        types, not the other way around.
        """
        from floe_core.schemas.data_contract import SchemaComparisonResult
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField, Schema
        from pyiceberg.types import StringType

        contract_columns = [{"name": "id", "logicalType": "string"}]
        table_schema = Schema(
            NestedField(1, "id", StringType(), required=True),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_columns,
            table_schema=table_schema,
        )

        assert isinstance(result, SchemaComparisonResult)


__all__ = [
    "TestDriftDetectorImportResilience",
    "TestDriftDetectorExportBoundary",
]
