"""JSON exporter for EnforcementResult.

Exports EnforcementResult to JSON format matching the Pydantic model schema.
Output is human-readable (pretty-printed) and suitable for CI/CD integration.

Task: T054
Requirements: FR-020 (JSON export format)

Example:
    >>> from floe_core.enforcement.exporters.json_exporter import export_json
    >>> export_json(enforcement_result, Path("output/enforcement.json"))
    PosixPath('output/enforcement.json')
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from floe_core.enforcement.result import EnforcementResult

logger = structlog.get_logger(__name__)


def export_json(
    result: EnforcementResult,
    output_path: Path,
) -> Path:
    """Export EnforcementResult to JSON file.

    Serializes the enforcement result to a human-readable JSON file
    using Pydantic's model_dump(). Output includes all fields from
    EnforcementResult, violations, and summary.

    Args:
        result: EnforcementResult from PolicyEnforcer.enforce().
        output_path: Path where JSON file should be written.

    Returns:
        The output path where the file was written.

    Raises:
        OSError: If file write fails due to permissions or disk space.

    Example:
        >>> result = enforcer.enforce(manifest)
        >>> export_json(result, Path("output/enforcement.json"))
        PosixPath('output/enforcement.json')
    """
    log = logger.bind(
        component="json_exporter",
        output_path=str(output_path),
    )

    # Ensure parent directory exists (FR-023)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize using Pydantic model_dump with mode for JSON-compatible output
    data = result.model_dump(mode="json")

    # Write with pretty formatting for readability
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    log.info(
        "json_export_complete",
        violations_count=len(result.violations),
        passed=result.passed,
    )

    return output_path
