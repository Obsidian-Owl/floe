"""Unit tests for security gate scanner parsers and threshold evaluation.

TDD tests for:
- Trivy and Grype JSON output parsers (T147, T149)
- Severity threshold evaluation (T151)

These tests are written FIRST and must FAIL before implementation.

Requirements: FR-053, FR-054, FR-055, FR-056, FR-057
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

# Sample Trivy JSON output for testing
TRIVY_OUTPUT_WITH_VULNERABILITIES: dict[str, Any] = {
    "Results": [
        {
            "Target": "alpine:3.18",
            "Class": "os-pkgs",
            "Type": "alpine",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2024-0001",
                    "PkgName": "openssl",
                    "InstalledVersion": "3.0.0",
                    "FixedVersion": "3.0.1",
                    "Severity": "CRITICAL",
                    "Title": "OpenSSL Buffer Overflow",
                },
                {
                    "VulnerabilityID": "CVE-2024-0002",
                    "PkgName": "zlib",
                    "InstalledVersion": "1.2.0",
                    "FixedVersion": "1.2.1",
                    "Severity": "HIGH",
                    "Title": "Zlib Memory Corruption",
                },
                {
                    "VulnerabilityID": "CVE-2024-0003",
                    "PkgName": "curl",
                    "InstalledVersion": "8.0.0",
                    "FixedVersion": "8.0.1",
                    "Severity": "MEDIUM",
                    "Title": "Curl SSRF Vulnerability",
                },
                {
                    "VulnerabilityID": "CVE-2024-0004",
                    "PkgName": "bash",
                    "InstalledVersion": "5.1.0",
                    "FixedVersion": "5.1.1",
                    "Severity": "LOW",
                    "Title": "Bash Minor Issue",
                },
            ],
        }
    ]
}

TRIVY_OUTPUT_WITH_UNFIXED: dict[str, Any] = {
    "Results": [
        {
            "Target": "debian:11",
            "Class": "os-pkgs",
            "Type": "debian",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2024-1000",
                    "PkgName": "glibc",
                    "InstalledVersion": "2.31",
                    "Severity": "HIGH",
                    "Title": "Glibc Issue (No Fix Available)",
                    # Note: No FixedVersion field = unfixed
                },
                {
                    "VulnerabilityID": "CVE-2024-1001",
                    "PkgName": "openssl",
                    "InstalledVersion": "1.1.1",
                    "FixedVersion": "",  # Empty string = unfixed
                    "Severity": "CRITICAL",
                    "Title": "OpenSSL Critical Issue",
                },
                {
                    "VulnerabilityID": "CVE-2024-1002",
                    "PkgName": "libxml2",
                    "InstalledVersion": "2.9.10",
                    "FixedVersion": "2.9.11",
                    "Severity": "HIGH",
                    "Title": "LibXML2 Issue (Fixed)",
                },
            ],
        }
    ]
}

TRIVY_OUTPUT_EMPTY: dict[str, Any] = {
    "Results": [
        {
            "Target": "clean-image:latest",
            "Class": "os-pkgs",
            "Type": "alpine",
            "Vulnerabilities": None,
        }
    ]
}

TRIVY_OUTPUT_NO_RESULTS: dict[str, Any] = {"Results": []}


class TestTrivyParserBasic:
    """Basic tests for Trivy JSON parser functionality."""

    @pytest.mark.requirement("FR-057")
    def test_parse_trivy_json_with_vulnerabilities(self) -> None:
        """Test parsing Trivy JSON output with vulnerabilities.

        The parser should correctly count vulnerabilities by severity
        and return a SecurityScanResult with accurate counts.
        """
        from floe_core.oci.security_gate import parse_trivy_output
        from floe_core.schemas.promotion import SecurityScanResult

        result = parse_trivy_output(json.dumps(TRIVY_OUTPUT_WITH_VULNERABILITIES))

        assert isinstance(result, SecurityScanResult)
        assert result.critical_count == 1
        assert result.high_count == 1
        assert result.medium_count == 1
        assert result.low_count == 1
        assert result.total_vulnerabilities == 4

    @pytest.mark.requirement("FR-057")
    def test_parse_trivy_json_empty_vulnerabilities(self) -> None:
        """Test parsing Trivy JSON with no vulnerabilities.

        Should return a SecurityScanResult with all counts at zero.
        """
        from floe_core.oci.security_gate import parse_trivy_output
        from floe_core.schemas.promotion import SecurityScanResult

        result = parse_trivy_output(json.dumps(TRIVY_OUTPUT_EMPTY))

        assert isinstance(result, SecurityScanResult)
        assert result.critical_count == 0
        assert result.high_count == 0
        assert result.medium_count == 0
        assert result.low_count == 0
        assert result.total_vulnerabilities == 0

    @pytest.mark.requirement("FR-057")
    def test_parse_trivy_json_no_results(self) -> None:
        """Test parsing Trivy JSON with empty Results array.

        Should return a SecurityScanResult with all counts at zero.
        """
        from floe_core.oci.security_gate import parse_trivy_output
        from floe_core.schemas.promotion import SecurityScanResult

        result = parse_trivy_output(json.dumps(TRIVY_OUTPUT_NO_RESULTS))

        assert isinstance(result, SecurityScanResult)
        assert result.total_vulnerabilities == 0

    @pytest.mark.requirement("FR-057")
    def test_parse_trivy_json_invalid_format(self) -> None:
        """Test parsing invalid JSON raises appropriate error."""
        from floe_core.oci.security_gate import (
            SecurityGateParseError,
            parse_trivy_output,
        )

        with pytest.raises(SecurityGateParseError, match="Invalid.*JSON"):
            parse_trivy_output("not valid json")

    @pytest.mark.requirement("FR-057")
    def test_parse_trivy_json_missing_results_key(self) -> None:
        """Test parsing JSON without Results key raises error."""
        from floe_core.oci.security_gate import (
            SecurityGateParseError,
            parse_trivy_output,
        )

        with pytest.raises(SecurityGateParseError, match="Results"):
            parse_trivy_output('{"something": "else"}')


class TestTrivySeverityFiltering:
    """Tests for severity-based filtering (FR-054)."""

    @pytest.mark.requirement("FR-054")
    def test_filter_by_severity_critical_only(self) -> None:
        """Test filtering to only block on CRITICAL vulnerabilities.

        When block_on_severity is ["CRITICAL"], only CRITICAL CVEs
        should appear in blocking_cves.
        """
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(
            json.dumps(TRIVY_OUTPUT_WITH_VULNERABILITIES),
            block_on_severity=["CRITICAL"],
        )

        assert result.blocking_cves == ["CVE-2024-0001"]
        # Counts should still reflect all vulnerabilities
        assert result.critical_count == 1
        assert result.high_count == 1

    @pytest.mark.requirement("FR-054")
    def test_filter_by_severity_critical_and_high(self) -> None:
        """Test filtering to block on CRITICAL and HIGH.

        Default behavior - both CRITICAL and HIGH CVEs should be blocking.
        """
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(
            json.dumps(TRIVY_OUTPUT_WITH_VULNERABILITIES),
            block_on_severity=["CRITICAL", "HIGH"],
        )

        assert "CVE-2024-0001" in result.blocking_cves
        assert "CVE-2024-0002" in result.blocking_cves
        assert len(result.blocking_cves) == 2

    @pytest.mark.requirement("FR-054")
    def test_filter_by_severity_all_levels(self) -> None:
        """Test filtering to block on all severity levels."""
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(
            json.dumps(TRIVY_OUTPUT_WITH_VULNERABILITIES),
            block_on_severity=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        )

        assert len(result.blocking_cves) == 4

    @pytest.mark.requirement("FR-054")
    def test_filter_by_severity_none_blocking(self) -> None:
        """Test with empty block_on_severity allows all.

        When block_on_severity is empty, no CVEs should be blocking.
        """
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(
            json.dumps(TRIVY_OUTPUT_WITH_VULNERABILITIES),
            block_on_severity=[],
        )

        assert result.blocking_cves == []
        # Counts should still be accurate
        assert result.total_vulnerabilities == 4


class TestTrivyIgnoreUnfixed:
    """Tests for ignore_unfixed option (FR-055)."""

    @pytest.mark.requirement("FR-055")
    def test_ignore_unfixed_true_excludes_unfixed(self) -> None:
        """Test that ignore_unfixed=True excludes vulnerabilities without fixes.

        Vulnerabilities without FixedVersion should not be counted toward
        blocking_cves when ignore_unfixed is True.
        """
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(
            json.dumps(TRIVY_OUTPUT_WITH_UNFIXED),
            block_on_severity=["CRITICAL", "HIGH"],
            ignore_unfixed=True,
        )

        # Only CVE-2024-1002 has a fix and is HIGH severity
        assert result.blocking_cves == ["CVE-2024-1002"]
        # ignored_unfixed should count the unfixed vulns
        assert result.ignored_unfixed == 2

    @pytest.mark.requirement("FR-055")
    def test_ignore_unfixed_false_includes_all(self) -> None:
        """Test that ignore_unfixed=False includes all vulnerabilities.

        Default behavior - all vulnerabilities count regardless of fix status.
        """
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(
            json.dumps(TRIVY_OUTPUT_WITH_UNFIXED),
            block_on_severity=["CRITICAL", "HIGH"],
            ignore_unfixed=False,
        )

        # All CRITICAL and HIGH should be blocking
        assert len(result.blocking_cves) == 3
        assert "CVE-2024-1000" in result.blocking_cves
        assert "CVE-2024-1001" in result.blocking_cves
        assert "CVE-2024-1002" in result.blocking_cves
        assert result.ignored_unfixed == 0

    @pytest.mark.requirement("FR-055")
    def test_ignore_unfixed_counts_correctly(self) -> None:
        """Test that ignored_unfixed counter is accurate."""
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(
            json.dumps(TRIVY_OUTPUT_WITH_UNFIXED),
            block_on_severity=["CRITICAL", "HIGH"],
            ignore_unfixed=True,
        )

        # Two vulnerabilities have no fix (empty or missing FixedVersion)
        assert result.ignored_unfixed == 2


class TestTrivySecurityScanResultIntegration:
    """Tests for SecurityScanResult integration (FR-056)."""

    @pytest.mark.requirement("FR-056")
    def test_result_includes_vulnerability_summary(self) -> None:
        """Test that result includes full vulnerability summary.

        SecurityScanResult should have counts by severity and CVE IDs.
        """
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(
            json.dumps(TRIVY_OUTPUT_WITH_VULNERABILITIES),
            block_on_severity=["CRITICAL", "HIGH"],
        )

        # Verify all severity counts
        assert result.critical_count == 1
        assert result.high_count == 1
        assert result.medium_count == 1
        assert result.low_count == 1

        # Verify blocking CVEs contain the IDs
        assert "CVE-2024-0001" in result.blocking_cves
        assert "CVE-2024-0002" in result.blocking_cves

    @pytest.mark.requirement("FR-056")
    def test_result_is_frozen_immutable(self) -> None:
        """Test that SecurityScanResult from parser is immutable."""
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(json.dumps(TRIVY_OUTPUT_WITH_VULNERABILITIES))

        with pytest.raises(ValidationError):  # Frozen model raises ValidationError
            result.critical_count = 999  # type: ignore[misc]

    @pytest.mark.requirement("FR-056")
    def test_result_total_vulnerabilities_property(self) -> None:
        """Test total_vulnerabilities computed property."""
        from floe_core.oci.security_gate import parse_trivy_output

        result = parse_trivy_output(json.dumps(TRIVY_OUTPUT_WITH_VULNERABILITIES))

        # Should be sum of all severity counts
        expected_total = (
            result.critical_count
            + result.high_count
            + result.medium_count
            + result.low_count
        )
        assert result.total_vulnerabilities == expected_total


class TestTrivyMultipleTargets:
    """Tests for Trivy output with multiple scan targets."""

    @pytest.mark.requirement("FR-057")
    def test_aggregates_vulnerabilities_across_targets(self) -> None:
        """Test that vulnerabilities from multiple targets are aggregated."""
        from floe_core.oci.security_gate import parse_trivy_output

        multi_target_output = {
            "Results": [
                {
                    "Target": "image-layer-1",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-A001",
                            "Severity": "CRITICAL",
                            "FixedVersion": "1.0.1",
                        }
                    ],
                },
                {
                    "Target": "image-layer-2",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-A002",
                            "Severity": "HIGH",
                            "FixedVersion": "2.0.1",
                        },
                        {
                            "VulnerabilityID": "CVE-2024-A003",
                            "Severity": "HIGH",
                            "FixedVersion": "3.0.1",
                        },
                    ],
                },
            ]
        }

        result = parse_trivy_output(json.dumps(multi_target_output))

        assert result.critical_count == 1
        assert result.high_count == 2
        assert result.total_vulnerabilities == 3

    @pytest.mark.requirement("FR-057")
    def test_deduplicates_same_cve_across_targets(self) -> None:
        """Test that same CVE in multiple targets is counted once."""
        from floe_core.oci.security_gate import parse_trivy_output

        duplicate_cve_output = {
            "Results": [
                {
                    "Target": "layer-1",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-DUPE",
                            "Severity": "CRITICAL",
                            "FixedVersion": "1.0.1",
                        }
                    ],
                },
                {
                    "Target": "layer-2",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-DUPE",  # Same CVE
                            "Severity": "CRITICAL",
                            "FixedVersion": "1.0.1",
                        }
                    ],
                },
            ]
        }

        result = parse_trivy_output(
            json.dumps(duplicate_cve_output),
            block_on_severity=["CRITICAL"],
        )

        # Should only appear once in blocking_cves
        assert result.blocking_cves == ["CVE-2024-DUPE"]
        # Count should still be 1 (deduplicated)
        assert result.critical_count == 1


# =============================================================================
# Grype Parser Tests (T149)
# =============================================================================

# Sample Grype JSON output for testing
GRYPE_OUTPUT_WITH_VULNERABILITIES: dict[str, Any] = {
    "matches": [
        {
            "vulnerability": {
                "id": "CVE-2024-G001",
                "severity": "Critical",
                "fix": {"versions": ["1.0.1"], "state": "fixed"},
            },
            "artifact": {
                "name": "openssl",
                "version": "1.0.0",
            },
        },
        {
            "vulnerability": {
                "id": "CVE-2024-G002",
                "severity": "High",
                "fix": {"versions": ["2.0.1"], "state": "fixed"},
            },
            "artifact": {
                "name": "zlib",
                "version": "1.2.0",
            },
        },
        {
            "vulnerability": {
                "id": "CVE-2024-G003",
                "severity": "Medium",
                "fix": {"versions": ["3.0.1"], "state": "fixed"},
            },
            "artifact": {
                "name": "curl",
                "version": "8.0.0",
            },
        },
        {
            "vulnerability": {
                "id": "CVE-2024-G004",
                "severity": "Low",
                "fix": {"versions": ["4.0.1"], "state": "fixed"},
            },
            "artifact": {
                "name": "bash",
                "version": "5.1.0",
            },
        },
    ]
}

GRYPE_OUTPUT_WITH_UNFIXED: dict[str, Any] = {
    "matches": [
        {
            "vulnerability": {
                "id": "CVE-2024-UF001",
                "severity": "High",
                "fix": {"versions": [], "state": "not-fixed"},
            },
            "artifact": {"name": "glibc", "version": "2.31"},
        },
        {
            "vulnerability": {
                "id": "CVE-2024-UF002",
                "severity": "Critical",
                "fix": {"versions": [], "state": "wont-fix"},
            },
            "artifact": {"name": "openssl", "version": "1.1.1"},
        },
        {
            "vulnerability": {
                "id": "CVE-2024-UF003",
                "severity": "High",
                "fix": {"versions": ["2.9.11"], "state": "fixed"},
            },
            "artifact": {"name": "libxml2", "version": "2.9.10"},
        },
    ]
}

GRYPE_OUTPUT_EMPTY: dict[str, Any] = {"matches": []}


class TestGrypeParserBasic:
    """Basic tests for Grype JSON parser functionality (T149)."""

    @pytest.mark.requirement("FR-057")
    def test_parse_grype_json_with_vulnerabilities(self) -> None:
        """Test parsing Grype JSON output with vulnerabilities.

        The parser should correctly count vulnerabilities by severity
        and return a SecurityScanResult with accurate counts.
        """
        from floe_core.oci.security_gate import parse_grype_output
        from floe_core.schemas.promotion import SecurityScanResult

        result = parse_grype_output(json.dumps(GRYPE_OUTPUT_WITH_VULNERABILITIES))

        assert isinstance(result, SecurityScanResult)
        assert result.critical_count == 1
        assert result.high_count == 1
        assert result.medium_count == 1
        assert result.low_count == 1
        assert result.total_vulnerabilities == 4

    @pytest.mark.requirement("FR-057")
    def test_parse_grype_json_empty_matches(self) -> None:
        """Test parsing Grype JSON with no vulnerabilities.

        Should return a SecurityScanResult with all counts at zero.
        """
        from floe_core.oci.security_gate import parse_grype_output
        from floe_core.schemas.promotion import SecurityScanResult

        result = parse_grype_output(json.dumps(GRYPE_OUTPUT_EMPTY))

        assert isinstance(result, SecurityScanResult)
        assert result.critical_count == 0
        assert result.high_count == 0
        assert result.medium_count == 0
        assert result.low_count == 0
        assert result.total_vulnerabilities == 0

    @pytest.mark.requirement("FR-057")
    def test_parse_grype_json_invalid_format(self) -> None:
        """Test parsing invalid JSON raises appropriate error."""
        from floe_core.oci.security_gate import (
            SecurityGateParseError,
            parse_grype_output,
        )

        with pytest.raises(SecurityGateParseError, match="Invalid.*JSON"):
            parse_grype_output("not valid json")

    @pytest.mark.requirement("FR-057")
    def test_parse_grype_json_missing_matches_key(self) -> None:
        """Test parsing JSON without matches key raises error."""
        from floe_core.oci.security_gate import (
            SecurityGateParseError,
            parse_grype_output,
        )

        with pytest.raises(SecurityGateParseError, match="matches"):
            parse_grype_output('{"something": "else"}')


class TestGrypeSeverityFiltering:
    """Tests for Grype severity-based filtering (FR-054)."""

    @pytest.mark.requirement("FR-054")
    def test_filter_by_severity_critical_only(self) -> None:
        """Test filtering to only block on CRITICAL vulnerabilities."""
        from floe_core.oci.security_gate import parse_grype_output

        result = parse_grype_output(
            json.dumps(GRYPE_OUTPUT_WITH_VULNERABILITIES),
            block_on_severity=["CRITICAL"],
        )

        assert result.blocking_cves == ["CVE-2024-G001"]
        # Counts should still reflect all vulnerabilities
        assert result.critical_count == 1
        assert result.high_count == 1

    @pytest.mark.requirement("FR-054")
    def test_filter_by_severity_critical_and_high(self) -> None:
        """Test filtering to block on CRITICAL and HIGH."""
        from floe_core.oci.security_gate import parse_grype_output

        result = parse_grype_output(
            json.dumps(GRYPE_OUTPUT_WITH_VULNERABILITIES),
            block_on_severity=["CRITICAL", "HIGH"],
        )

        assert "CVE-2024-G001" in result.blocking_cves
        assert "CVE-2024-G002" in result.blocking_cves
        assert len(result.blocking_cves) == 2


class TestGrypeIgnoreUnfixed:
    """Tests for Grype ignore_unfixed option (FR-055)."""

    @pytest.mark.requirement("FR-055")
    def test_ignore_unfixed_true_excludes_unfixed(self) -> None:
        """Test that ignore_unfixed=True excludes vulnerabilities without fixes.

        Grype marks unfixed vulnerabilities with state: "not-fixed" or "wont-fix".
        """
        from floe_core.oci.security_gate import parse_grype_output

        result = parse_grype_output(
            json.dumps(GRYPE_OUTPUT_WITH_UNFIXED),
            block_on_severity=["CRITICAL", "HIGH"],
            ignore_unfixed=True,
        )

        # Only CVE-2024-UF003 has a fix and is HIGH severity
        assert result.blocking_cves == ["CVE-2024-UF003"]
        # ignored_unfixed should count the unfixed vulns
        assert result.ignored_unfixed == 2

    @pytest.mark.requirement("FR-055")
    def test_ignore_unfixed_false_includes_all(self) -> None:
        """Test that ignore_unfixed=False includes all vulnerabilities."""
        from floe_core.oci.security_gate import parse_grype_output

        result = parse_grype_output(
            json.dumps(GRYPE_OUTPUT_WITH_UNFIXED),
            block_on_severity=["CRITICAL", "HIGH"],
            ignore_unfixed=False,
        )

        # All CRITICAL and HIGH should be blocking
        assert len(result.blocking_cves) == 3
        assert "CVE-2024-UF001" in result.blocking_cves
        assert "CVE-2024-UF002" in result.blocking_cves
        assert "CVE-2024-UF003" in result.blocking_cves
        assert result.ignored_unfixed == 0


class TestGrypeSeverityNormalization:
    """Tests for Grype severity case normalization (FR-057)."""

    @pytest.mark.requirement("FR-057")
    def test_grype_severity_case_insensitive(self) -> None:
        """Test that Grype severity parsing is case-insensitive.

        Grype uses "Critical", "High", etc. while our config uses "CRITICAL", "HIGH".
        Parser should normalize these.
        """
        from floe_core.oci.security_gate import parse_grype_output

        # Grype uses title case: "Critical", "High", etc.
        mixed_case_output = {
            "matches": [
                {
                    "vulnerability": {
                        "id": "CVE-2024-CASE1",
                        "severity": "Critical",  # Title case
                        "fix": {"versions": ["1.0"], "state": "fixed"},
                    },
                    "artifact": {"name": "pkg", "version": "1.0"},
                },
                {
                    "vulnerability": {
                        "id": "CVE-2024-CASE2",
                        "severity": "HIGH",  # Upper case
                        "fix": {"versions": ["1.0"], "state": "fixed"},
                    },
                    "artifact": {"name": "pkg2", "version": "1.0"},
                },
            ]
        }

        result = parse_grype_output(
            json.dumps(mixed_case_output),
            block_on_severity=["CRITICAL", "HIGH"],
        )

        assert result.critical_count == 1
        assert result.high_count == 1
        assert len(result.blocking_cves) == 2


# =============================================================================
# Security Gate Evaluation Tests (T151)
# =============================================================================


class TestSecurityGateEvaluationBasic:
    """Basic tests for security gate evaluation (T151).

    Tests for evaluate_security_gate() function that determines if
    promotion should be blocked based on scan results and config.
    """

    @pytest.mark.requirement("FR-053")
    def test_evaluate_security_gate_passes_when_no_blocking_cves(self) -> None:
        """Test security gate passes when no blocking vulnerabilities.

        When scan result has no blocking_cves, evaluation should pass.
        """
        from floe_core.oci.security_gate import (
            SecurityGateEvaluation,
            evaluate_security_gate,
        )
        from floe_core.schemas.promotion import SecurityGateConfig, SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=0,
            high_count=0,
            medium_count=2,
            low_count=5,
            blocking_cves=[],
            ignored_unfixed=0,
        )
        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            block_on_severity=["CRITICAL", "HIGH"],
        )

        evaluation = evaluate_security_gate(scan_result, config)

        assert isinstance(evaluation, SecurityGateEvaluation)
        assert evaluation.passed is True
        assert evaluation.blocked is False
        assert evaluation.blocking_cves == []

    @pytest.mark.requirement("FR-053")
    def test_evaluate_security_gate_blocks_with_critical_vulnerabilities(self) -> None:
        """Test security gate blocks when CRITICAL vulnerabilities found.

        When scan result has CRITICAL blocking_cves, evaluation should block.
        """
        from floe_core.oci.security_gate import (
            SecurityGateEvaluation,
            evaluate_security_gate,
        )
        from floe_core.schemas.promotion import SecurityGateConfig, SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=1,
            high_count=0,
            medium_count=0,
            low_count=0,
            blocking_cves=["CVE-2024-0001"],
            ignored_unfixed=0,
        )
        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            block_on_severity=["CRITICAL", "HIGH"],
        )

        evaluation = evaluate_security_gate(scan_result, config)

        assert isinstance(evaluation, SecurityGateEvaluation)
        assert evaluation.passed is False
        assert evaluation.blocked is True
        assert "CVE-2024-0001" in evaluation.blocking_cves

    @pytest.mark.requirement("FR-053")
    def test_evaluate_security_gate_blocks_with_high_vulnerabilities(self) -> None:
        """Test security gate blocks when HIGH vulnerabilities found."""
        from floe_core.oci.security_gate import (
            evaluate_security_gate,
        )
        from floe_core.schemas.promotion import SecurityGateConfig, SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=0,
            high_count=2,
            medium_count=0,
            low_count=0,
            blocking_cves=["CVE-2024-H001", "CVE-2024-H002"],
            ignored_unfixed=0,
        )
        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            block_on_severity=["CRITICAL", "HIGH"],
        )

        evaluation = evaluate_security_gate(scan_result, config)

        assert evaluation.passed is False
        assert evaluation.blocked is True
        assert len(evaluation.blocking_cves) == 2

    @pytest.mark.requirement("FR-053")
    def test_evaluate_security_gate_none_config_always_passes(self) -> None:
        """Test security gate passes when config is None (gate disabled)."""
        from floe_core.oci.security_gate import evaluate_security_gate
        from floe_core.schemas.promotion import SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=5,
            high_count=10,
            medium_count=20,
            low_count=50,
            blocking_cves=["CVE-1", "CVE-2", "CVE-3"],
            ignored_unfixed=0,
        )

        # None config means gate is disabled
        evaluation = evaluate_security_gate(scan_result, config=None)

        assert evaluation.passed is True
        assert evaluation.blocked is False


class TestSecurityGateEvaluationReason:
    """Tests for security gate evaluation reason messages (T151)."""

    @pytest.mark.requirement("FR-053")
    def test_evaluation_provides_reason_when_blocked(self) -> None:
        """Test that blocked evaluation includes reason with CVE details."""
        from floe_core.oci.security_gate import evaluate_security_gate
        from floe_core.schemas.promotion import SecurityGateConfig, SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=1,
            high_count=1,
            medium_count=0,
            low_count=0,
            blocking_cves=["CVE-2024-0001", "CVE-2024-0002"],
            ignored_unfixed=0,
        )
        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            block_on_severity=["CRITICAL", "HIGH"],
        )

        evaluation = evaluate_security_gate(scan_result, config)

        assert evaluation.reason is not None
        assert "CVE-2024-0001" in evaluation.reason
        assert "CVE-2024-0002" in evaluation.reason

    @pytest.mark.requirement("FR-053")
    def test_evaluation_reason_is_none_when_passed(self) -> None:
        """Test that passed evaluation has no reason."""
        from floe_core.oci.security_gate import evaluate_security_gate
        from floe_core.schemas.promotion import SecurityGateConfig, SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=0,
            high_count=0,
            medium_count=1,
            low_count=1,
            blocking_cves=[],
            ignored_unfixed=0,
        )
        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            block_on_severity=["CRITICAL", "HIGH"],
        )

        evaluation = evaluate_security_gate(scan_result, config)

        assert evaluation.passed is True
        assert evaluation.reason is None


class TestSecurityGateEvaluationSummary:
    """Tests for security gate evaluation summary (FR-056)."""

    @pytest.mark.requirement("FR-056")
    def test_evaluation_includes_vulnerability_summary(self) -> None:
        """Test that evaluation includes vulnerability counts summary."""
        from floe_core.oci.security_gate import evaluate_security_gate
        from floe_core.schemas.promotion import SecurityGateConfig, SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=1,
            high_count=2,
            medium_count=3,
            low_count=4,
            blocking_cves=["CVE-2024-0001"],
            ignored_unfixed=1,
        )
        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            block_on_severity=["CRITICAL", "HIGH"],
        )

        evaluation = evaluate_security_gate(scan_result, config)

        # Evaluation should include the scan result for summary access
        assert evaluation.scan_result is not None
        assert evaluation.scan_result.critical_count == 1
        assert evaluation.scan_result.high_count == 2
        assert evaluation.scan_result.total_vulnerabilities == 10

    @pytest.mark.requirement("FR-056")
    def test_evaluation_tracks_ignored_unfixed_count(self) -> None:
        """Test that evaluation tracks ignored unfixed vulnerabilities."""
        from floe_core.oci.security_gate import evaluate_security_gate
        from floe_core.schemas.promotion import SecurityGateConfig, SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=0,
            high_count=1,
            medium_count=0,
            low_count=0,
            blocking_cves=["CVE-2024-FIXED"],
            ignored_unfixed=3,  # 3 unfixed vulns were ignored
        )
        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            block_on_severity=["CRITICAL", "HIGH"],
            ignore_unfixed=True,
        )

        evaluation = evaluate_security_gate(scan_result, config)

        assert evaluation.scan_result.ignored_unfixed == 3


class TestSecurityGateEvaluationImmutability:
    """Tests for SecurityGateEvaluation immutability (FR-056)."""

    @pytest.mark.requirement("FR-056")
    def test_evaluation_result_is_immutable(self) -> None:
        """Test that SecurityGateEvaluation is frozen/immutable."""
        from floe_core.oci.security_gate import evaluate_security_gate
        from floe_core.schemas.promotion import SecurityGateConfig, SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=1,
            high_count=0,
            medium_count=0,
            low_count=0,
            blocking_cves=["CVE-2024-0001"],
            ignored_unfixed=0,
        )
        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            block_on_severity=["CRITICAL"],
        )

        evaluation = evaluate_security_gate(scan_result, config)

        with pytest.raises(ValidationError):  # Frozen model raises ValidationError
            evaluation.passed = True  # type: ignore[misc]


class TestSecurityGateNoneConfig:
    """Tests for security gate with None config (T151)."""

    @pytest.mark.requirement("FR-053")
    def test_evaluate_with_none_config_passes(self) -> None:
        """Test that None config (no gate configured) always passes."""
        from floe_core.oci.security_gate import evaluate_security_gate
        from floe_core.schemas.promotion import SecurityScanResult

        scan_result = SecurityScanResult(
            critical_count=5,
            high_count=10,
            medium_count=20,
            low_count=50,
            blocking_cves=["CVE-1", "CVE-2"],
            ignored_unfixed=0,
        )

        evaluation = evaluate_security_gate(scan_result, config=None)

        assert evaluation.passed is True
        assert evaluation.blocked is False
