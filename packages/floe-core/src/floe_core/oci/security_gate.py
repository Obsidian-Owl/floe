"""Security gate scanner parsers for promotion lifecycle (T148, T150).

Task IDs: T148, T150
Phase: 14 - Security Gate (US12)
User Story: US12 - Security Gate Configuration
Requirements: FR-054, FR-055, FR-056, FR-057

This module implements parsers for security scanner output formats:
- FR-054: Configurable severity thresholds (block_on_severity)
- FR-055: ignore_unfixed option to exclude vulnerabilities without fixes
- FR-056: Vulnerability summary (counts by severity, CVE IDs)
- FR-057: Standard scanner output formats (Trivy JSON, Grype JSON)

Example:
    >>> from floe_core.oci.security_gate import parse_trivy_output
    >>> result = parse_trivy_output(
    ...     trivy_json_output,
    ...     block_on_severity=["CRITICAL", "HIGH"],
    ...     ignore_unfixed=True,
    ... )
    >>> result.critical_count
    2
    >>> result.blocking_cves
    ['CVE-2024-1234']
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from pydantic import BaseModel, ConfigDict, Field

from floe_core.schemas.promotion import SecurityGateConfig, SecurityScanResult

logger = structlog.get_logger(__name__)


class SecurityGateParseError(Exception):
    """Raised when security scanner output cannot be parsed.

    Attributes:
        message: Description of the parse error.
        scanner_format: Scanner format that failed (trivy, grype).
        raw_output: First 500 chars of the problematic output.

    Examples:
        >>> raise SecurityGateParseError(
        ...     "Invalid JSON",
        ...     scanner_format="trivy",
        ...     raw_output="not json",
        ... )
    """

    def __init__(
        self,
        message: str,
        scanner_format: str = "unknown",
        raw_output: str | None = None,
    ) -> None:
        """Initialize SecurityGateParseError.

        Args:
            message: Description of the parse error.
            scanner_format: Scanner format that failed (trivy, grype).
            raw_output: Raw output that failed to parse (truncated to 500 chars).
        """
        self.message = message
        self.scanner_format = scanner_format
        self.raw_output = raw_output[:500] if raw_output else None
        super().__init__(f"{scanner_format}: {message}")


def parse_trivy_output(
    output: str,
    block_on_severity: list[str] | None = None,
    ignore_unfixed: bool = False,
) -> SecurityScanResult:
    """Parse Trivy JSON output into SecurityScanResult.

    Parses the JSON output from `trivy image --format json` and converts
    it to a SecurityScanResult with vulnerability counts and blocking CVEs.

    Args:
        output: Raw JSON string from Trivy scanner.
        block_on_severity: Severity levels that block promotion.
            Defaults to ["CRITICAL", "HIGH"]. Empty list means no blocking.
        ignore_unfixed: If True, exclude vulnerabilities without fixes from
            blocking_cves and count them in ignored_unfixed.

    Returns:
        SecurityScanResult with vulnerability counts and blocking CVEs.

    Raises:
        SecurityGateParseError: If output is not valid Trivy JSON.

    Examples:
        >>> result = parse_trivy_output('{"Results": []}')
        >>> result.total_vulnerabilities
        0

        >>> result = parse_trivy_output(
        ...     trivy_output,
        ...     block_on_severity=["CRITICAL"],
        ...     ignore_unfixed=True,
        ... )
        >>> result.blocking_cves
        ['CVE-2024-1234']
    """
    log = logger.bind(scanner="trivy", ignore_unfixed=ignore_unfixed)

    # Default block_on_severity
    if block_on_severity is None:
        block_on_severity = ["CRITICAL", "HIGH"]

    # Parse JSON
    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        log.error("trivy_parse_failed", error=str(e))
        raise SecurityGateParseError(
            f"Invalid Trivy JSON: {e}",
            scanner_format="trivy",
            raw_output=output,
        ) from e

    # Validate structure
    if "Results" not in data:
        log.error("trivy_missing_results_key")
        raise SecurityGateParseError(
            "Missing 'Results' key in Trivy output",
            scanner_format="trivy",
            raw_output=output,
        )

    # Count vulnerabilities by severity
    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    blocking_cves: list[str] = []
    ignored_unfixed = 0
    seen_cves: set[str] = set()

    block_severity_set = set(block_on_severity)

    for result in data.get("Results", []):
        vulnerabilities = result.get("Vulnerabilities") or []

        for vuln in vulnerabilities:
            cve_id = vuln.get("VulnerabilityID", "UNKNOWN")
            severity = vuln.get("Severity", "UNKNOWN").upper()
            fixed_version = vuln.get("FixedVersion")

            # Check if this is an unfixed vulnerability
            has_fix = bool(fixed_version and fixed_version.strip())

            # Skip duplicate CVEs (same CVE across multiple targets)
            if cve_id in seen_cves:
                continue
            seen_cves.add(cve_id)

            # Count by severity
            if severity == "CRITICAL":
                critical_count += 1
            elif severity == "HIGH":
                high_count += 1
            elif severity == "MEDIUM":
                medium_count += 1
            elif severity == "LOW":
                low_count += 1
            # UNKNOWN and other severities are not counted

            # Determine if this CVE should block promotion
            if severity in block_severity_set:
                if ignore_unfixed and not has_fix:
                    # Count as ignored but don't add to blocking
                    ignored_unfixed += 1
                    log.debug(
                        "trivy_ignored_unfixed",
                        cve=cve_id,
                        severity=severity,
                    )
                else:
                    blocking_cves.append(cve_id)

    log.info(
        "trivy_parse_complete",
        critical=critical_count,
        high=high_count,
        medium=medium_count,
        low=low_count,
        blocking=len(blocking_cves),
        ignored_unfixed=ignored_unfixed,
    )

    return SecurityScanResult(
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        blocking_cves=blocking_cves,
        ignored_unfixed=ignored_unfixed,
    )


def parse_grype_output(
    output: str,
    block_on_severity: list[str] | None = None,
    ignore_unfixed: bool = False,
) -> SecurityScanResult:
    """Parse Grype JSON output into SecurityScanResult.

    Parses the JSON output from `grype <image> -o json` and converts
    it to a SecurityScanResult with vulnerability counts and blocking CVEs.

    Args:
        output: Raw JSON string from Grype scanner.
        block_on_severity: Severity levels that block promotion.
            Defaults to ["CRITICAL", "HIGH"]. Empty list means no blocking.
        ignore_unfixed: If True, exclude vulnerabilities without fixes from
            blocking_cves and count them in ignored_unfixed.

    Returns:
        SecurityScanResult with vulnerability counts and blocking CVEs.

    Raises:
        SecurityGateParseError: If output is not valid Grype JSON.

    Examples:
        >>> result = parse_grype_output('{"matches": []}')
        >>> result.total_vulnerabilities
        0

        >>> result = parse_grype_output(
        ...     grype_output,
        ...     block_on_severity=["CRITICAL"],
        ...     ignore_unfixed=True,
        ... )
        >>> result.blocking_cves
        ['CVE-2024-1234']
    """
    log = logger.bind(scanner="grype", ignore_unfixed=ignore_unfixed)

    # Default block_on_severity
    if block_on_severity is None:
        block_on_severity = ["CRITICAL", "HIGH"]

    # Parse JSON
    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        log.error("grype_parse_failed", error=str(e))
        raise SecurityGateParseError(
            f"Invalid Grype JSON: {e}",
            scanner_format="grype",
            raw_output=output,
        ) from e

    # Validate structure
    if "matches" not in data:
        log.error("grype_missing_matches_key")
        raise SecurityGateParseError(
            "Missing 'matches' key in Grype output",
            scanner_format="grype",
            raw_output=output,
        )

    # Count vulnerabilities by severity
    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    blocking_cves: list[str] = []
    ignored_unfixed = 0
    seen_cves: set[str] = set()

    # Normalize block_on_severity to uppercase for comparison
    block_severity_set = {s.upper() for s in block_on_severity}

    for match in data.get("matches", []):
        vulnerability = match.get("vulnerability", {})
        cve_id = vulnerability.get("id", "UNKNOWN")
        # Grype uses mixed case (Critical, High) - normalize to uppercase
        severity = vulnerability.get("severity", "UNKNOWN").upper()
        fix_info = vulnerability.get("fix", {})
        fix_state = fix_info.get("state", "unknown")

        # Check if this is an unfixed vulnerability
        # Grype uses "fixed", "not-fixed", "wont-fix", "unknown"
        has_fix = fix_state == "fixed"

        # Skip duplicate CVEs (same CVE across multiple packages)
        if cve_id in seen_cves:
            continue
        seen_cves.add(cve_id)

        # Count by severity
        if severity == "CRITICAL":
            critical_count += 1
        elif severity == "HIGH":
            high_count += 1
        elif severity == "MEDIUM":
            medium_count += 1
        elif severity == "LOW":
            low_count += 1
        # UNKNOWN, NEGLIGIBLE, and other severities are not counted

        # Determine if this CVE should block promotion
        if severity in block_severity_set:
            if ignore_unfixed and not has_fix:
                # Count as ignored but don't add to blocking
                ignored_unfixed += 1
                log.debug(
                    "grype_ignored_unfixed",
                    cve=cve_id,
                    severity=severity,
                    fix_state=fix_state,
                )
            else:
                blocking_cves.append(cve_id)

    log.info(
        "grype_parse_complete",
        critical=critical_count,
        high=high_count,
        medium=medium_count,
        low=low_count,
        blocking=len(blocking_cves),
        ignored_unfixed=ignored_unfixed,
    )

    return SecurityScanResult(
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        blocking_cves=blocking_cves,
        ignored_unfixed=ignored_unfixed,
    )


class SecurityGateEvaluation(BaseModel):
    """Result of security gate evaluation (T152).

    Records whether promotion should be blocked based on security scan results
    and configured severity thresholds.

    Attributes:
        passed: Whether the security gate passed (no blocking vulnerabilities).
        blocked: Whether promotion is blocked (inverse of passed).
        blocking_cves: List of CVE IDs that caused the block.
        reason: Explanation message if blocked, None if passed.
        scan_result: The SecurityScanResult used for evaluation.

    Examples:
        >>> evaluation = SecurityGateEvaluation(
        ...     passed=False,
        ...     blocked=True,
        ...     blocking_cves=["CVE-2024-0001"],
        ...     reason="Blocked by 1 vulnerability: CVE-2024-0001",
        ...     scan_result=scan_result,
        ... )
        >>> evaluation.passed
        False
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool = Field(
        ...,
        description="Whether the security gate passed",
    )
    blocked: bool = Field(
        ...,
        description="Whether promotion is blocked (inverse of passed)",
    )
    blocking_cves: list[str] = Field(
        default_factory=list,
        description="List of CVE IDs that caused the block",
    )
    reason: str | None = Field(
        default=None,
        description="Explanation message if blocked",
    )
    scan_result: SecurityScanResult = Field(
        ...,
        description="The SecurityScanResult used for evaluation",
    )


def evaluate_security_gate(
    scan_result: SecurityScanResult,
    config: SecurityGateConfig | None,
) -> SecurityGateEvaluation:
    """Evaluate security scan result against gate configuration.

    Determines if promotion should be blocked based on the scan result
    and configured severity thresholds.

    Args:
        scan_result: SecurityScanResult from a scanner parser.
        config: SecurityGateConfig with severity thresholds. If None,
            the gate is considered disabled and always passes.

    Returns:
        SecurityGateEvaluation with pass/block decision and details.

    Examples:
        >>> evaluation = evaluate_security_gate(scan_result, config)
        >>> evaluation.passed
        True

        >>> evaluation = evaluate_security_gate(scan_result_with_cves, config)
        >>> evaluation.blocked
        True
        >>> evaluation.blocking_cves
        ['CVE-2024-0001']
    """
    log = logger.bind(
        config_present=config is not None,
    )

    # If no config, gate is disabled - always pass
    if config is None:
        log.debug("security_gate_disabled")
        return SecurityGateEvaluation(
            passed=True,
            blocked=False,
            blocking_cves=[],
            reason=None,
            scan_result=scan_result,
        )

    # Check if there are blocking CVEs
    blocking_cves = scan_result.blocking_cves

    if not blocking_cves:
        log.info(
            "security_gate_passed",
            total_vulnerabilities=scan_result.total_vulnerabilities,
        )
        return SecurityGateEvaluation(
            passed=True,
            blocked=False,
            blocking_cves=[],
            reason=None,
            scan_result=scan_result,
        )

    # Gate is blocked
    cve_list = ", ".join(blocking_cves)
    reason = (
        f"Security gate blocked promotion: {len(blocking_cves)} "
        f"blocking vulnerabilities found: {cve_list}"
    )

    log.warning(
        "security_gate_blocked",
        blocking_count=len(blocking_cves),
        blocking_cves=blocking_cves,
    )

    return SecurityGateEvaluation(
        passed=False,
        blocked=True,
        blocking_cves=list(blocking_cves),
        reason=reason,
        scan_result=scan_result,
    )


__all__: list[str] = [
    "SecurityGateParseError",
    "SecurityGateEvaluation",
    "parse_trivy_output",
    "parse_grype_output",
    "evaluate_security_gate",
]
