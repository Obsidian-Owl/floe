"""Schema drift check implementation for contract monitoring.

Compares actual schema columns against the contract's expected schema definition,
detecting column additions, removals, type changes, and nullability changes.

Tasks: T033
Requirements: FR-011, FR-012, FR-013, FR-014
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import structlog

from floe_core.contracts.monitoring.checks.base import BaseCheck
from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.violations import (
    CheckResult,
    CheckStatus,
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)


class SchemaDriftCheck(BaseCheck):
    """Check that actual schema matches the contract's expected schema definition.

    Reads ``contract_data.schema.columns`` (expected) and compares against
    ``contract_data.actual_schema.columns`` (actual).  Detects four drift types:
    - column_added: Column exists in actual but not in expected (WARNING)
    - column_removed: Column exists in expected but not in actual (CRITICAL)
    - type_changed: Column exists in both but types differ (ERROR)
    - nullability_changed: Column exists with same type but nullability differs (WARNING)

    Returns:
        CheckResult with status PASS if schemas match, FAIL with a
        ContractViolationEvent if drift detected, or ERROR if required
        contract fields are missing.
    """

    @property
    def check_type(self) -> ViolationType:
        """The type of violation this check detects."""
        return ViolationType.SCHEMA_DRIFT

    async def execute(
        self,
        contract: RegisteredContract,
        config: MonitoringConfig,
    ) -> CheckResult:
        """Execute schema drift check against a registered contract.

        Args:
            contract: The registered contract to check.
            config: Global monitoring configuration.

        Returns:
            CheckResult recording the check outcome.
        """
        now = datetime.now(tz=timezone.utc)
        start = time.monotonic()

        # --- Extract expected schema ---
        schema_cfg = contract.contract_data.get("schema", {})
        expected_columns = schema_cfg.get("columns")
        if expected_columns is None:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.SCHEMA_DRIFT,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": "No schema.columns configuration in contract_data"},
            )

        # --- Extract actual schema ---
        actual_schema_cfg = contract.contract_data.get("actual_schema", {})
        actual_columns = actual_schema_cfg.get("columns")
        if actual_columns is None:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.SCHEMA_DRIFT,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": "No actual_schema.columns in contract_data"},
            )

        # --- Build column dicts for O(1) lookup ---
        expected_map: dict[str, dict[str, Any]] = {}
        for col in expected_columns:
            col_name = col.get("name", "")
            expected_map[col_name] = {
                "name": col_name,
                "type": col.get("type", ""),
                "nullable": col.get("nullable", True),
            }

        actual_map: dict[str, dict[str, Any]] = {}
        for col in actual_columns:
            col_name = col.get("name", "")
            actual_map[col_name] = {
                "name": col_name,
                "type": col.get("type", ""),
                "nullable": col.get("nullable", True),
            }

        # --- Detect drifts ---
        drifts: list[dict[str, Any]] = []

        # Column removals (expected but not actual) — CRITICAL
        for col_name in expected_map:
            if col_name not in actual_map:
                drifts.append(
                    {
                        "column": col_name,
                        "drift_type": "column_removed",
                        "expected": f"{expected_map[col_name]['type']} (nullable={expected_map[col_name]['nullable']})",
                        "actual": "MISSING",
                        "severity": ViolationSeverity.CRITICAL,
                    }
                )

        # Column additions (actual but not expected) — WARNING
        for col_name in actual_map:
            if col_name not in expected_map:
                drifts.append(
                    {
                        "column": col_name,
                        "drift_type": "column_added",
                        "expected": "NOT_DEFINED",
                        "actual": f"{actual_map[col_name]['type']} (nullable={actual_map[col_name]['nullable']})",
                        "severity": ViolationSeverity.WARNING,
                    }
                )

        # Type and nullability changes (columns in both) — ERROR/WARNING
        for col_name in expected_map:
            if col_name not in actual_map:
                continue

            expected_type = expected_map[col_name]["type"]
            actual_type = actual_map[col_name]["type"]
            expected_nullable = expected_map[col_name]["nullable"]
            actual_nullable = actual_map[col_name]["nullable"]

            # Type mismatch — ERROR
            if expected_type != actual_type:
                drifts.append(
                    {
                        "column": col_name,
                        "drift_type": "type_changed",
                        "expected": expected_type,
                        "actual": actual_type,
                        "severity": ViolationSeverity.ERROR,
                    }
                )
            # Nullability mismatch — WARNING
            elif expected_nullable != actual_nullable:
                drifts.append(
                    {
                        "column": col_name,
                        "drift_type": "nullability_changed",
                        "expected": f"nullable={expected_nullable}",
                        "actual": f"nullable={actual_nullable}",
                        "severity": ViolationSeverity.WARNING,
                    }
                )

        duration = time.monotonic() - start

        # --- No drifts detected ---
        if not drifts:
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.SCHEMA_DRIFT,
                status=CheckStatus.PASS,
                duration_seconds=duration,
                timestamp=now,
                details={
                    "expected_columns": len(expected_map),
                    "actual_columns": len(actual_map),
                },
            )

        # --- Determine highest severity ---
        severity_priority = {
            ViolationSeverity.CRITICAL: 4,
            ViolationSeverity.ERROR: 3,
            ViolationSeverity.WARNING: 2,
            ViolationSeverity.INFO: 1,
        }
        highest_severity = max(drifts, key=lambda d: severity_priority[d["severity"]])[
            "severity"
        ]

        # --- Build violation event ---
        drift_count = len(drifts)
        message = (
            f"Schema drift detected: {drift_count} drift{'s' if drift_count != 1 else ''} found"
        )

        # Build summary for expected/actual values
        expected_summary = f"{len(expected_map)} columns defined"
        actual_summary = f"{len(actual_map)} columns found"

        violation = ContractViolationEvent(
            contract_name=contract.contract_name,
            contract_version=contract.contract_version,
            violation_type=ViolationType.SCHEMA_DRIFT,
            severity=highest_severity,
            message=message,
            element=None,
            expected_value=expected_summary,
            actual_value=actual_summary,
            timestamp=now,
            check_duration_seconds=duration,
            metadata={
                "drift_count": str(drift_count),
                "expected_columns": str(len(expected_map)),
                "actual_columns": str(len(actual_map)),
            },
        )

        return CheckResult(
            contract_name=contract.contract_name,
            check_type=ViolationType.SCHEMA_DRIFT,
            status=CheckStatus.FAIL,
            duration_seconds=duration,
            timestamp=now,
            details={
                "drift_count": drift_count,
                "expected_columns": len(expected_map),
                "actual_columns": len(actual_map),
                "drifts": drifts,
            },
            violation=violation,
        )
