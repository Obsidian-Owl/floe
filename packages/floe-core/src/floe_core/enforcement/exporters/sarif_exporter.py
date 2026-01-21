"""SARIF 2.1.0 exporter for EnforcementResult.

Exports EnforcementResult to SARIF (Static Analysis Results Interchange Format)
version 2.1.0, compatible with GitHub Code Scanning and other SARIF consumers.

Task: T055, T056
Requirements: FR-021 (SARIF 2.1.0 export format)

SARIF Specification: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html

Example:
    >>> from floe_core.enforcement.exporters.sarif_exporter import export_sarif
    >>> export_sarif(enforcement_result, Path("output/enforcement.sarif"))
    PosixPath('output/enforcement.sarif')
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from floe_core.enforcement.result import EnforcementResult, Violation

logger = structlog.get_logger(__name__)

# SARIF 2.1.0 schema URL
SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
SARIF_VERSION = "2.1.0"

# Tool information
TOOL_NAME = "floe-policy-enforcer"
TOOL_VERSION = "1.0.0"
TOOL_INFO_URI = "https://floe.dev/docs/enforcement"

# Rule definitions for FLOE error codes
RULE_DEFINITIONS: dict[str, dict[str, str]] = {
    # Naming violations (E2xx)
    "FLOE-E201": {
        "name": "NamingConventionViolation",
        "shortDescription": "Model name violates naming convention",
        "helpUri": "https://floe.dev/docs/enforcement/naming",
    },
    "FLOE-E202": {
        "name": "NamingPatternMismatch",
        "shortDescription": "Model name does not match required pattern",
        "helpUri": "https://floe.dev/docs/enforcement/naming#patterns",
    },
    # Coverage violations (E21x)
    "FLOE-E210": {
        "name": "TestCoverageInsufficient",
        "shortDescription": "Column test coverage below threshold",
        "helpUri": "https://floe.dev/docs/enforcement/coverage",
    },
    "FLOE-E211": {
        "name": "CriticalColumnUntested",
        "shortDescription": "Critical column lacks required tests",
        "helpUri": "https://floe.dev/docs/enforcement/coverage#critical",
    },
    # Documentation violations (E22x)
    "FLOE-E220": {
        "name": "ModelDescriptionMissing",
        "shortDescription": "Model is missing description",
        "helpUri": "https://floe.dev/docs/enforcement/documentation",
    },
    "FLOE-E221": {
        "name": "ColumnDescriptionMissing",
        "shortDescription": "Column is missing description",
        "helpUri": "https://floe.dev/docs/enforcement/documentation#columns",
    },
    "FLOE-E222": {
        "name": "DocumentationIncomplete",
        "shortDescription": "Model documentation is incomplete",
        "helpUri": "https://floe.dev/docs/enforcement/documentation",
    },
    # Semantic violations (E3xx)
    "FLOE-E301": {
        "name": "InvalidModelReference",
        "shortDescription": "Referenced model does not exist",
        "helpUri": "https://floe.dev/docs/enforcement/semantic#refs",
    },
    "FLOE-E302": {
        "name": "CircularDependency",
        "shortDescription": "Circular dependency detected between models",
        "helpUri": "https://floe.dev/docs/enforcement/semantic#circular",
    },
    "FLOE-E303": {
        "name": "InvalidSourceReference",
        "shortDescription": "Referenced source does not exist",
        "helpUri": "https://floe.dev/docs/enforcement/semantic#sources",
    },
    # Custom rule violations (E4xx)
    "FLOE-E400": {
        "name": "TagsRequired",
        "shortDescription": "Model missing required tags",
        "helpUri": "https://floe.dev/docs/enforcement/custom#tags",
    },
    "FLOE-E401": {
        "name": "MetaFieldRequired",
        "shortDescription": "Model missing required meta field",
        "helpUri": "https://floe.dev/docs/enforcement/custom#meta",
    },
    "FLOE-E402": {
        "name": "TestTypeRequired",
        "shortDescription": "Model missing required test type",
        "helpUri": "https://floe.dev/docs/enforcement/custom#tests",
    },
}


def export_sarif(
    result: EnforcementResult,
    output_path: Path,
) -> Path:
    """Export EnforcementResult to SARIF 2.1.0 format.

    Generates a SARIF file compatible with GitHub Code Scanning and other
    SARIF consumers. Maps violations to SARIF results with proper rule
    definitions and locations.

    Args:
        result: EnforcementResult from PolicyEnforcer.enforce().
        output_path: Path where SARIF file should be written.

    Returns:
        The output path where the file was written.

    Raises:
        OSError: If file write fails due to permissions or disk space.

    Example:
        >>> result = enforcer.enforce(manifest)
        >>> export_sarif(result, Path("output/enforcement.sarif"))
        PosixPath('output/enforcement.sarif')
    """
    log = logger.bind(
        component="sarif_exporter",
        output_path=str(output_path),
    )

    # Ensure parent directory exists (FR-023)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build SARIF structure
    sarif_data = _build_sarif_document(result)

    # Write with pretty formatting
    output_path.write_text(
        json.dumps(sarif_data, indent=2, ensure_ascii=False)
    )

    log.info(
        "sarif_export_complete",
        violations_count=len(result.violations),
        rules_count=len(_get_unique_rule_ids(result.violations)),
        passed=result.passed,
    )

    return output_path


def _build_sarif_document(result: EnforcementResult) -> dict[str, Any]:
    """Build the complete SARIF document structure.

    Args:
        result: EnforcementResult to convert.

    Returns:
        SARIF document as dictionary.
    """
    # Collect unique rules used in violations
    rule_ids = _get_unique_rule_ids(result.violations)
    rules = _build_rules(rule_ids)

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "version": TOOL_VERSION,
                        "informationUri": TOOL_INFO_URI,
                        "rules": rules,
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": result.passed,
                        "endTimeUtc": result.timestamp.isoformat().replace("+00:00", "Z"),
                    }
                ],
                "results": [
                    _build_result(violation) for violation in result.violations
                ],
            }
        ],
    }


def _get_unique_rule_ids(violations: list[Violation]) -> set[str]:
    """Get unique rule IDs from violations.

    Args:
        violations: List of violations.

    Returns:
        Set of unique error codes.
    """
    return {v.error_code for v in violations}


def _build_rules(rule_ids: set[str]) -> list[dict[str, Any]]:
    """Build SARIF rule definitions for used rules.

    Args:
        rule_ids: Set of error codes to include.

    Returns:
        List of SARIF rule objects.
    """
    rules: list[dict[str, Any]] = []
    for rule_id in sorted(rule_ids):
        default_rule: dict[str, str] = {
            "name": rule_id.replace("-", ""),
            "shortDescription": f"Policy violation: {rule_id}",
            "helpUri": TOOL_INFO_URI,
        }
        rule_def = RULE_DEFINITIONS.get(rule_id, default_rule)
        rules.append({
            "id": rule_id,
            "name": rule_def["name"],
            "shortDescription": {
                "text": rule_def["shortDescription"],
            },
            "helpUri": rule_def["helpUri"],
        })
    return rules


def _build_result(violation: Violation) -> dict[str, Any]:
    """Build a SARIF result from a violation.

    Args:
        violation: Violation to convert.

    Returns:
        SARIF result object.
    """
    # Build artifact URI from model name
    # Convention: models/<layer>/<model_name>.sql
    model_path = _get_model_path(violation.model_name)

    result: dict[str, Any] = {
        "ruleId": violation.error_code,
        "level": _map_severity_to_level(violation.severity),
        "message": {
            "text": violation.message,
        },
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": model_path,
                    },
                }
            }
        ],
    }

    # Add column region if applicable
    if violation.column_name:
        result["locations"][0]["physicalLocation"]["region"] = {
            "startLine": 1,  # Placeholder - would need actual line from manifest
            "snippet": {
                "text": f"Column: {violation.column_name}",
            },
        }

    return result


def _map_severity_to_level(severity: str) -> str:
    """Map violation severity to SARIF level.

    Args:
        severity: Violation severity ("error" or "warning").

    Returns:
        SARIF level ("error", "warning", or "note").
    """
    mapping = {
        "error": "error",
        "warning": "warning",
    }
    return mapping.get(severity, "note")


def _get_model_path(model_name: str) -> str:
    """Generate a model path from model name.

    Uses dbt convention for model file paths.

    Args:
        model_name: Simple model name (e.g., "stg_customers").

    Returns:
        Relative path to model file.
    """
    # Infer layer from model name prefix
    if model_name.startswith("bronze_") or model_name.startswith("stg_"):
        layer = "staging"
    elif model_name.startswith("silver_") or model_name.startswith("int_"):
        layer = "intermediate"
    elif (
        model_name.startswith("gold_")
        or model_name.startswith("dim_")
        or model_name.startswith("fct_")
    ):
        layer = "marts"
    else:
        layer = "models"

    return f"models/{layer}/{model_name}.sql"
