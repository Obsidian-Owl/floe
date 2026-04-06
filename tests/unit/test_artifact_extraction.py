"""Structural tests: artifact extraction in test-e2e-cluster.sh (Step 6).

Validates that ``test-e2e-cluster.sh`` extracts ALL required artifacts from the
test pod PVC after test completion:

- ``e2e-results.xml``  (JUnit XML) -- already implemented
- ``e2e-report.html``  (HTML report) -- NEW, required by AC-5
- ``e2e-report.json``  (JSON report) -- NEW, required by AC-5

These are source-parsing tests: they read the shell script as text and
assert on structural properties.  They run in <1s with no infrastructure.

Requirements Covered:
    - AC-5.1: Script extracts HTML report via kubectl cp
    - AC-5.2: Script extracts JSON report via kubectl cp
    - AC-5.3: HTML and JSON use ${TEST_SUITE} prefix in destination filename
    - AC-5.4: Extraction uses 2>/dev/null || true for non-fatal failure
    - AC-5.5: All three artifact types (XML, HTML, JSON) are extracted

Test Type Rationale:
    Unit tests -- shell script structural validation via text parsing.
    No infrastructure or subprocess execution required.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "testing" / "ci" / "test-e2e-cluster.sh"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_script() -> str:
    """Read the test-e2e-cluster.sh script contents.

    Returns:
        Full text of the shell script.

    Raises:
        FileNotFoundError: If the script does not exist.
    """
    return _SCRIPT_PATH.read_text()


def _extract_step6_block(script: str) -> str:
    """Extract the Step 6 (result extraction) block from the script.

    Looks for the section between the Step 6 header comment and the next
    step header (Step 7) or end of file.

    Args:
        script: Full shell script text.

    Returns:
        The text of the Step 6 block.

    Raises:
        AssertionError: If Step 6 block cannot be found.
    """
    # Match from "Step 6" header to "Step 7" header or EOF
    match = re.search(
        r"#\s*---\s*Step 6.*?---\s*\n(.*?)(?=#\s*---\s*Step 7|$)",
        script,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not locate Step 6 block in test-e2e-cluster.sh. "
        "Expected a comment header like: # --- Step 6: Extract results ---"
    )
    return match.group(1)


def _find_kubectl_cp_commands(text: str) -> list[str]:
    """Extract all kubectl cp logical commands from a block of text.

    Handles backslash line continuations by joining continued lines into
    a single logical command string.

    Args:
        text: Block of shell script text to search.

    Returns:
        List of logical commands containing kubectl cp invocations.
    """
    # First, join backslash-continued lines
    lines = text.splitlines()
    logical_lines: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") and not current:
            continue
        if current or re.search(r"kubectl\s+cp\b", stripped):
            if stripped.endswith("\\"):
                current.append(stripped[:-1].rstrip())
            else:
                current.append(stripped)
                logical_lines.append(" ".join(current))
                current = []
        # Also capture non-continued kubectl cp lines
        elif re.search(r"kubectl\s+cp\b", stripped) and not current:
            logical_lines.append(stripped)

    # If there's a dangling continuation, include it
    if current:
        logical_lines.append(" ".join(current))

    commands: list[str] = []
    for line in logical_lines:
        if re.search(r"kubectl\s+cp\b", line):
            commands.append(line)
    return commands


# ---------------------------------------------------------------------------
# Tests -- JUnit XML extraction (baseline, should PASS)
# ---------------------------------------------------------------------------


class TestJunitXmlExtraction:
    """Verify JUnit XML artifact is extracted (already implemented)."""

    @pytest.mark.requirement("AC-5.5")
    def test_junit_xml_extracted_via_kubectl_cp(self) -> None:
        """Script MUST extract e2e-results.xml from the test pod via kubectl cp.

        This is the baseline -- already implemented in the script.
        Verifies our test infrastructure works before testing new artifacts.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        xml_commands = [cmd for cmd in cp_commands if "e2e-results.xml" in cmd]
        assert len(xml_commands) >= 1, (
            "No kubectl cp command found for e2e-results.xml in Step 6. "
            "JUnit XML extraction must be present."
        )

    @pytest.mark.requirement("AC-5.3")
    def test_junit_xml_uses_test_suite_prefix(self) -> None:
        """JUnit XML destination filename MUST use ${TEST_SUITE} prefix.

        Prevents overwriting when multiple test suites run sequentially.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        xml_commands = [cmd for cmd in cp_commands if "e2e-results.xml" in cmd]
        assert len(xml_commands) >= 1, "No kubectl cp for e2e-results.xml found"

        # The destination path must contain TEST_SUITE variable
        has_test_suite_prefix = any(
            re.search(r"\$\{?TEST_SUITE\}?.*results\.xml", cmd) for cmd in xml_commands
        )
        assert has_test_suite_prefix, (
            "JUnit XML extraction does not use ${TEST_SUITE} prefix in "
            "destination filename. Expected pattern like: "
            "${ARTIFACTS_DIR}/${TEST_SUITE}-results.xml"
        )


# ---------------------------------------------------------------------------
# Tests -- HTML report extraction (RED -- not yet implemented)
# ---------------------------------------------------------------------------


class TestHtmlReportExtraction:
    """Verify HTML report artifact extraction from test pod."""

    @pytest.mark.requirement("AC-5.1")
    def test_html_report_extracted_via_kubectl_cp(self) -> None:
        """Script MUST extract e2e-report.html from the test pod via kubectl cp.

        The HTML report provides a human-readable test results page for
        CI artifact viewers (GitHub Actions, Jenkins, etc.).
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        html_commands = [cmd for cmd in cp_commands if "e2e-report.html" in cmd]
        assert len(html_commands) >= 1, (
            "No kubectl cp command found for e2e-report.html in Step 6. "
            "The HTML report must be extracted from the test pod."
        )

    @pytest.mark.requirement("AC-5.1")
    def test_html_report_source_path_is_correct(self) -> None:
        """HTML report MUST be extracted from /artifacts/e2e-report.html in the pod.

        Catches implementations that use a wrong source path (e.g., /tmp/ or /results/).
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        html_commands = [cmd for cmd in cp_commands if "e2e-report.html" in cmd]
        assert len(html_commands) >= 1, "No kubectl cp for e2e-report.html found"

        # Source path in kubectl cp format: NAMESPACE/POD:/artifacts/e2e-report.html
        has_correct_source = any(
            re.search(r":/artifacts/e2e-report\.html", cmd) for cmd in html_commands
        )
        assert has_correct_source, (
            f"HTML report kubectl cp uses wrong source path. "
            f"Expected source: :/artifacts/e2e-report.html "
            f"Found commands: {html_commands}"
        )

    @pytest.mark.requirement("AC-5.3")
    def test_html_report_uses_test_suite_prefix(self) -> None:
        """HTML report destination MUST use ${TEST_SUITE} prefix in filename.

        Without the prefix, running e2e then e2e-destructive suites would
        overwrite the first suite's HTML report.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        html_commands = [cmd for cmd in cp_commands if "e2e-report.html" in cmd]
        assert len(html_commands) >= 1, "No kubectl cp for e2e-report.html found"

        has_test_suite_prefix = any(
            re.search(r"\$\{?TEST_SUITE\}?.*report\.html", cmd) for cmd in html_commands
        )
        assert has_test_suite_prefix, (
            "HTML report extraction does not use ${TEST_SUITE} prefix in "
            "destination filename. Expected pattern like: "
            "${ARTIFACTS_DIR}/${TEST_SUITE}-report.html"
        )

    @pytest.mark.requirement("AC-5.4")
    def test_html_report_extraction_is_non_fatal(self) -> None:
        """HTML report extraction failure MUST NOT abort the script.

        The report may not exist (e.g., pytest-html not installed or test
        crashed before report generation).  Extraction must use
        2>/dev/null || true or equivalent.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)

        # Find lines containing kubectl cp for HTML report, including
        # continuation on the same or next line
        html_block = _get_command_block_for_artifact(step6, "e2e-report.html")
        assert html_block is not None, "No kubectl cp for e2e-report.html found"

        has_stderr_suppression = "2>/dev/null" in html_block
        has_or_true = re.search(r"\|\|\s*true", html_block) is not None

        assert has_stderr_suppression, (
            "HTML report extraction does not suppress stderr (2>/dev/null). "
            "kubectl cp errors must not pollute output when the report is absent."
        )
        assert has_or_true, (
            "HTML report extraction does not use '|| true' for non-fatal failure. "
            "Missing reports must not cause the script to exit (set -e is active)."
        )


# ---------------------------------------------------------------------------
# Tests -- JSON report extraction (RED -- not yet implemented)
# ---------------------------------------------------------------------------


class TestJsonReportExtraction:
    """Verify JSON report artifact extraction from test pod."""

    @pytest.mark.requirement("AC-5.2")
    def test_json_report_extracted_via_kubectl_cp(self) -> None:
        """Script MUST extract e2e-report.json from the test pod via kubectl cp.

        The JSON report provides machine-readable test results for CI
        pipelines that parse and aggregate test metrics.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        json_commands = [cmd for cmd in cp_commands if "e2e-report.json" in cmd]
        assert len(json_commands) >= 1, (
            "No kubectl cp command found for e2e-report.json in Step 6. "
            "The JSON report must be extracted from the test pod."
        )

    @pytest.mark.requirement("AC-5.2")
    def test_json_report_source_path_is_correct(self) -> None:
        """JSON report MUST be extracted from /artifacts/e2e-report.json in the pod.

        Catches implementations that use a wrong source path.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        json_commands = [cmd for cmd in cp_commands if "e2e-report.json" in cmd]
        assert len(json_commands) >= 1, "No kubectl cp for e2e-report.json found"

        has_correct_source = any(
            re.search(r":/artifacts/e2e-report\.json", cmd) for cmd in json_commands
        )
        assert has_correct_source, (
            f"JSON report kubectl cp uses wrong source path. "
            f"Expected source: :/artifacts/e2e-report.json "
            f"Found commands: {json_commands}"
        )

    @pytest.mark.requirement("AC-5.3")
    def test_json_report_uses_test_suite_prefix(self) -> None:
        """JSON report destination MUST use ${TEST_SUITE} prefix in filename.

        Without the prefix, running multiple test suites would overwrite results.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        json_commands = [cmd for cmd in cp_commands if "e2e-report.json" in cmd]
        assert len(json_commands) >= 1, "No kubectl cp for e2e-report.json found"

        has_test_suite_prefix = any(
            re.search(r"\$\{?TEST_SUITE\}?.*report\.json", cmd) for cmd in json_commands
        )
        assert has_test_suite_prefix, (
            "JSON report extraction does not use ${TEST_SUITE} prefix in "
            "destination filename. Expected pattern like: "
            "${ARTIFACTS_DIR}/${TEST_SUITE}-report.json"
        )

    @pytest.mark.requirement("AC-5.4")
    def test_json_report_extraction_is_non_fatal(self) -> None:
        """JSON report extraction failure MUST NOT abort the script.

        Same rationale as HTML: report may not exist, must not crash script.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)

        json_block = _get_command_block_for_artifact(step6, "e2e-report.json")
        assert json_block is not None, "No kubectl cp for e2e-report.json found"

        has_stderr_suppression = "2>/dev/null" in json_block
        has_or_true = re.search(r"\|\|\s*true", json_block) is not None

        assert has_stderr_suppression, (
            "JSON report extraction does not suppress stderr (2>/dev/null). "
            "kubectl cp errors must not pollute output when the report is absent."
        )
        assert has_or_true, (
            "JSON report extraction does not use '|| true' for non-fatal failure. "
            "Missing reports must not cause the script to exit (set -e is active)."
        )


# ---------------------------------------------------------------------------
# Tests -- Completeness (all three artifacts extracted)
# ---------------------------------------------------------------------------


class TestArtifactCompleteness:
    """Verify all three required artifact types are extracted."""

    @pytest.mark.requirement("AC-5.5")
    def test_all_three_artifact_types_present(self) -> None:
        """Step 6 MUST extract all three artifact types: XML, HTML, and JSON.

        This is a completeness gate -- catches implementations that add one
        new artifact type but forget the other.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        extracted_artifacts: dict[str, bool] = {
            "e2e-results.xml": False,
            "e2e-report.html": False,
            "e2e-report.json": False,
        }

        for cmd in cp_commands:
            for artifact in extracted_artifacts:
                if artifact in cmd:
                    extracted_artifacts[artifact] = True

        missing = [name for name, found in extracted_artifacts.items() if not found]
        assert not missing, (
            f"Step 6 is missing kubectl cp extraction for: {missing}. "
            f"All three artifact types must be extracted: "
            f"{list(extracted_artifacts.keys())}"
        )

    @pytest.mark.requirement("AC-5.5")
    def test_all_extractions_use_kubectl_cp(self) -> None:
        """All artifact extractions MUST use kubectl cp, not other mechanisms.

        Catches implementations that use kubectl exec + cat, or kubectl logs
        redirection, which are fragile alternatives.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)

        required_artifacts = [
            "e2e-results.xml",
            "e2e-report.html",
            "e2e-report.json",
        ]

        for artifact in required_artifacts:
            # Must have a kubectl cp line for this artifact, not just any
            # mention of the filename
            has_kubectl_cp = re.search(
                rf"kubectl\s+cp\s+.*{re.escape(artifact)}",
                step6,
            )
            assert has_kubectl_cp, (
                f"Artifact '{artifact}' is not extracted via kubectl cp. "
                f"All artifacts must use kubectl cp, not kubectl exec or "
                f"other mechanisms."
            )

    @pytest.mark.requirement("AC-5.3")
    def test_all_extractions_use_test_suite_prefix(self) -> None:
        """ALL artifact extractions MUST use ${TEST_SUITE} prefix.

        This is a blanket check -- catches the scenario where one artifact
        is correctly prefixed but another is not.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        artifacts_without_prefix: list[str] = []
        required_artifacts = [
            "results.xml",
            "report.html",
            "report.json",
        ]

        for artifact_suffix in required_artifacts:
            matching_commands = [cmd for cmd in cp_commands if artifact_suffix in cmd]
            if not matching_commands:
                # Missing artifact entirely -- caught by completeness test
                continue

            has_prefix = any(
                re.search(
                    rf"\$\{{?TEST_SUITE\}}?.*{re.escape(artifact_suffix)}",
                    cmd,
                )
                for cmd in matching_commands
            )
            if not has_prefix:
                artifacts_without_prefix.append(artifact_suffix)

        assert not artifacts_without_prefix, (
            f"These artifact extractions lack ${{TEST_SUITE}} prefix in "
            f"destination filename: {artifacts_without_prefix}. "
            f"All artifacts must be prefixed to avoid overwriting across suites."
        )

    @pytest.mark.requirement("AC-5.4")
    def test_all_extractions_are_non_fatal(self) -> None:
        """ALL artifact extractions MUST be non-fatal (2>/dev/null || true).

        A blanket check that no extraction command can crash the script
        under set -e.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)
        cp_commands = _find_kubectl_cp_commands(step6)

        fatal_commands: list[str] = []
        for cmd in cp_commands:
            has_or_true = re.search(r"\|\|\s*true", cmd) is not None
            if not has_or_true:
                fatal_commands.append(cmd)

        assert not fatal_commands, (
            "These kubectl cp commands lack '|| true' and will abort the "
            "script under set -e if the artifact is missing:\n"
            + "\n".join(f"  - {cmd}" for cmd in fatal_commands)
        )


# ---------------------------------------------------------------------------
# Tests -- Extraction ordering and placement
# ---------------------------------------------------------------------------


class TestExtractionPlacement:
    """Verify artifact extraction happens inside the POD_NAME conditional."""

    @pytest.mark.requirement("AC-5")
    def test_html_extraction_inside_pod_name_guard(self) -> None:
        """HTML extraction MUST be inside the if [[ -n POD_NAME ]] block.

        If placed outside, kubectl cp would fail with an empty pod name.
        """
        script = _read_script()
        step6 = _extract_step6_block(script)

        # The POD_NAME guard block
        pod_guard = re.search(
            r"if\s+\[\[\s+-n\s+.*POD_NAME.*\]\].*?then(.*?)(?:\belse\b|\bfi\b)",
            step6,
            re.DOTALL,
        )
        assert pod_guard is not None, "Could not find POD_NAME guard block in Step 6"
        guard_body = pod_guard.group(1)

        assert "e2e-report.html" in guard_body, (
            "HTML report extraction is not inside the POD_NAME guard block. "
            "kubectl cp requires a valid pod name."
        )

    @pytest.mark.requirement("AC-5")
    def test_json_extraction_inside_pod_name_guard(self) -> None:
        """JSON extraction MUST be inside the if [[ -n POD_NAME ]] block."""
        script = _read_script()
        step6 = _extract_step6_block(script)

        pod_guard = re.search(
            r"if\s+\[\[\s+-n\s+.*POD_NAME.*\]\].*?then(.*?)(?:\belse\b|\bfi\b)",
            step6,
            re.DOTALL,
        )
        assert pod_guard is not None, "Could not find POD_NAME guard block in Step 6"
        guard_body = pod_guard.group(1)

        assert "e2e-report.json" in guard_body, (
            "JSON report extraction is not inside the POD_NAME guard block. "
            "kubectl cp requires a valid pod name."
        )


# ---------------------------------------------------------------------------
# Helper -- extract command block for a specific artifact
# ---------------------------------------------------------------------------


def _get_command_block_for_artifact(
    step6_text: str,
    artifact_filename: str,
) -> str | None:
    """Get the full command block (including line continuations) for an artifact.

    Searches for kubectl cp lines referencing the given artifact filename
    and returns the full logical command including any backslash-continued
    lines and the trailing error suppression.

    Args:
        step6_text: The Step 6 block text.
        artifact_filename: The artifact filename to search for (e.g., "e2e-report.html").

    Returns:
        The command block as a string, or None if not found.
    """
    lines = step6_text.splitlines()
    result_lines: list[str] = []
    capturing = False

    for line in lines:
        stripped = line.strip()

        # Skip comments
        if stripped.startswith("#"):
            if capturing:
                # Comment breaks a command sequence
                break
            continue

        if artifact_filename in stripped and "kubectl" in stripped:
            capturing = True

        if capturing:
            result_lines.append(stripped)
            # If line does not end with backslash and is not empty,
            # the command is complete
            if not stripped.endswith("\\") and stripped:
                break

    if not result_lines:
        return None

    return " ".join(result_lines)
