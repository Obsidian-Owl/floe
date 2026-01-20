"""Exporters submodule for policy enforcement results.

This module contains exporters for different output formats:
- export_json: Export results as JSON (EnforcementResult schema)
- export_sarif: Export results as SARIF 2.1.0 for GitHub Code Scanning
- export_html: Export results as human-readable HTML report

Task: T002 (Epic 3B - Policy Validation Enhancement)

Example:
    >>> from floe_core.enforcement.exporters import (
    ...     export_json, export_sarif, export_html
    ... )
    >>> export_json(result, Path("output/enforcement.json"))
    >>> export_sarif(result, Path("output/enforcement.sarif"))
    >>> export_html(result, Path("output/enforcement.html"))
"""

from __future__ import annotations

from pathlib import Path

# Placeholder imports - will be implemented in T054-T058
# from floe_core.enforcement.exporters.json_exporter import export_json
# from floe_core.enforcement.exporters.sarif_exporter import export_sarif
# from floe_core.enforcement.exporters.html_exporter import export_html

__all__: list[str] = [
    # T054: JSON exporter
    "export_json",
    # T055-T056: SARIF exporter
    "export_sarif",
    # T057-T058: HTML exporter
    "export_html",
    # T059: Directory creation helper
    "ensure_output_dir",
]


def ensure_output_dir(path: Path) -> Path:
    """Ensure the output directory exists, creating it if necessary.

    Args:
        path: Path to the output file

    Returns:
        The parent directory path that was ensured to exist

    Raises:
        OSError: If directory creation fails due to permissions

    Example:
        >>> ensure_output_dir(Path("output/reports/enforcement.json"))
        PosixPath('output/reports')
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    return parent


# Placeholder functions - will be replaced by actual imports in T059-T060
def export_json(_result: object, _output_path: Path) -> None:
    """Export enforcement result as JSON. Placeholder - implemented in T054."""
    raise NotImplementedError("export_json will be implemented in T054")


def export_sarif(_result: object, _output_path: Path) -> None:
    """Export enforcement result as SARIF 2.1.0. Placeholder - implemented in T055."""
    raise NotImplementedError("export_sarif will be implemented in T055")


def export_html(_result: object, _output_path: Path) -> None:
    """Export enforcement result as HTML. Placeholder - implemented in T058."""
    raise NotImplementedError("export_html will be implemented in T058")
