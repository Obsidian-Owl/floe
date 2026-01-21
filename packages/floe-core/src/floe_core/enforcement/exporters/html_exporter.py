"""HTML exporter for EnforcementResult.

Exports EnforcementResult to a human-readable HTML report using Jinja2 templates.
Output is a standalone HTML file with inline CSS (no JavaScript dependencies).

Task: T057, T058
Requirements: FR-022 (HTML export format)

Example:
    >>> from floe_core.enforcement.exporters.html_exporter import export_html
    >>> export_html(enforcement_result, Path("output/enforcement.html"))
    PosixPath('output/enforcement.html')
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from jinja2 import Environment, PackageLoader, select_autoescape

if TYPE_CHECKING:
    from floe_core.enforcement.result import EnforcementResult

logger = structlog.get_logger(__name__)

# Template environment - loads templates from the templates directory
_template_env: Environment | None = None


def _get_template_env() -> Environment:
    """Get or create the Jinja2 template environment.

    Returns:
        Configured Jinja2 Environment.
    """
    global _template_env
    if _template_env is None:
        _template_env = Environment(
            loader=PackageLoader(
                "floe_core.enforcement.exporters",
                "templates",
            ),
            autoescape=select_autoescape(["html", "xml"]),
        )
    return _template_env


def export_html(
    result: EnforcementResult,
    output_path: Path,
) -> Path:
    """Export EnforcementResult to HTML report.

    Generates a human-readable HTML report using Jinja2 templates.
    The report includes:
    - Summary statistics with pass/fail status
    - Violation counts by policy type
    - Detailed violation list with suggestions
    - Downstream impact information

    The HTML is standalone with inline CSS and no JavaScript.

    Args:
        result: EnforcementResult from PolicyEnforcer.enforce().
        output_path: Path where HTML file should be written.

    Returns:
        The output path where the file was written.

    Raises:
        OSError: If file write fails due to permissions or disk space.

    Example:
        >>> result = enforcer.enforce(manifest)
        >>> export_html(result, Path("output/enforcement.html"))
        PosixPath('output/enforcement.html')
    """
    log = logger.bind(
        component="html_exporter",
        output_path=str(output_path),
    )

    # Ensure parent directory exists (FR-023)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get template
    env = _get_template_env()
    template = env.get_template("report.html.j2")

    # Prepare template context
    context = _build_template_context(result)

    # Render template
    html_content = template.render(**context)

    # Write to file
    output_path.write_text(html_content)

    log.info(
        "html_export_complete",
        violations_count=len(result.violations),
        passed=result.passed,
    )

    return output_path


def _build_template_context(result: EnforcementResult) -> dict[str, Any]:
    """Build the template context from EnforcementResult.

    Args:
        result: EnforcementResult to convert.

    Returns:
        Dictionary of template variables.
    """
    # Format timestamp for display
    timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Convert violations to dictionaries for template
    violations = [_violation_to_dict(v) for v in result.violations]

    # Convert summary to dictionary
    summary = result.summary.model_dump()

    return {
        "passed": result.passed,
        "timestamp": timestamp,
        "manifest_version": result.manifest_version,
        "enforcement_level": result.enforcement_level,
        "summary": summary,
        "violations": violations,
    }


def _violation_to_dict(violation: Any) -> dict[str, Any]:
    """Convert a Violation to a dictionary for the template.

    Args:
        violation: Violation model instance.

    Returns:
        Dictionary representation for template rendering.
    """
    return {
        "error_code": violation.error_code,
        "severity": violation.severity,
        "policy_type": violation.policy_type,
        "model_name": violation.model_name,
        "column_name": violation.column_name,
        "message": violation.message,
        "expected": violation.expected,
        "actual": violation.actual,
        "suggestion": violation.suggestion,
        "documentation_url": violation.documentation_url,
        "downstream_impact": violation.downstream_impact,
        "override_applied": violation.override_applied,
    }
