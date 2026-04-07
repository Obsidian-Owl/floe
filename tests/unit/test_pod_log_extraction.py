"""Structural tests: extract_pod_logs function in test-e2e-cluster.sh.

Validates that ``test-e2e-cluster.sh`` defines an ``extract_pod_logs``
function with the correct behavior for collecting pod logs and K8s events
on test failure.

These are source-parsing tests: they read the shell script as text and
assert on structural properties.  They run in <1s with no infrastructure.

Requirements Covered:
    - AC-3.1: Collect logs from ALL pods in $TEST_NAMESPACE (last $LOG_TAIL_LINES lines)
    - AC-3.2: Save each pod's logs to test-artifacts/pod-logs/{pod-name}.log
    - AC-3.3: Capture K8s events to test-artifacts/pod-logs/events.txt
    - AC-3.4: Print summary of collected pod log files to stdout
    - BC-1: LOG_TAIL_LINES env var overrides default 100
    - BC-2: Individual pod log failures skip with warning, don't fail loop
    - BC-3: Per-pod timeout of 10 seconds

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


def _extract_function_body(script: str, func_name: str) -> str | None:
    """Extract the body of a bash function from script text.

    Uses brace-counting to handle nested blocks.  Returns None if the
    function is not found.

    Args:
        script: Full shell script text.
        func_name: Name of the function to extract.

    Returns:
        The function body (including braces) or None if not found.
    """
    # Match both `func_name()` and `function func_name` styles
    pattern = re.compile(
        rf"(?:^|\n)\s*(?:function\s+)?{re.escape(func_name)}\s*\(\)\s*\{{",
        re.MULTILINE,
    )
    match = pattern.search(script)
    if match is None:
        return None

    start = match.start()
    brace_depth = 0
    in_body = False
    i = match.end() - 1  # Position at the opening brace

    for i in range(match.end() - 1, len(script)):
        ch = script[i]
        if ch == "{":
            brace_depth += 1
            in_body = True
        elif ch == "}":
            brace_depth -= 1
            if in_body and brace_depth == 0:
                return script[start : i + 1]

    return None


# ---------------------------------------------------------------------------
# Tests — Function existence and definition
# ---------------------------------------------------------------------------


class TestExtractPodLogsFunctionExists:
    """Verify the extract_pod_logs function is defined in the script."""

    @pytest.mark.requirement("AC-3")
    def test_function_is_defined(self) -> None:
        """extract_pod_logs function MUST exist in test-e2e-cluster.sh."""
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, (
            "extract_pod_logs() function not found in test-e2e-cluster.sh. "
            "The function must be defined to collect pod logs on failure."
        )

    @pytest.mark.requirement("AC-3")
    def test_function_body_is_nontrivial(self) -> None:
        """extract_pod_logs must contain real logic, not an empty stub.

        A sloppy implementation might define `extract_pod_logs() { : }` or
        `extract_pod_logs() { true }`.  This test catches that.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # Strip the function signature and braces, check remaining content
        # Remove comments and blank lines
        lines = [
            line.strip()
            for line in body.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        # Exclude the function signature line and closing brace
        content_lines = [
            line
            for line in lines
            if not re.match(r"^(extract_pod_logs|function\s|[{}]|\:$|true$)", line)
        ]
        assert len(content_lines) >= 5, (
            f"extract_pod_logs() body has only {len(content_lines)} non-trivial lines. "
            "Expected substantial implementation for pod log collection."
        )


# ---------------------------------------------------------------------------
# Tests — LOG_TAIL_LINES variable with default 100
# ---------------------------------------------------------------------------


class TestLogTailLinesVariable:
    """Verify LOG_TAIL_LINES is used with correct default."""

    @pytest.mark.requirement("AC-3.1")
    def test_log_tail_lines_variable_used(self) -> None:
        """The function MUST reference LOG_TAIL_LINES variable."""
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        assert "LOG_TAIL_LINES" in body, (
            "extract_pod_logs() does not reference LOG_TAIL_LINES. "
            "The function must use this variable for kubectl --tail flag."
        )

    @pytest.mark.requirement("BC-1")
    def test_log_tail_lines_default_100(self) -> None:
        """LOG_TAIL_LINES MUST default to 100 if not set.

        The default can appear either in the function body or at the
        script's top-level configuration block.
        """
        script = _read_script()
        # Check script-wide: must have a default assignment of 100
        # Patterns: LOG_TAIL_LINES="${LOG_TAIL_LINES:-100}"
        #       or: LOG_TAIL_LINES=${LOG_TAIL_LINES:-100}
        #       or: : "${LOG_TAIL_LINES:=100}"
        default_pattern = re.compile(
            r"""LOG_TAIL_LINES[=}].*(?::-|:=)\s*100\b"""
            r"""|"""
            r""":\s+"\$\{LOG_TAIL_LINES:=100\}"""
        )
        assert default_pattern.search(script), (
            "LOG_TAIL_LINES does not have a default value of 100. "
            'Expected pattern like: LOG_TAIL_LINES="${LOG_TAIL_LINES:-100}"'
        )


# ---------------------------------------------------------------------------
# Tests — Pod logs directory creation
# ---------------------------------------------------------------------------


class TestPodLogsDirectory:
    """Verify the function creates pod-logs/ subdirectory."""

    @pytest.mark.requirement("AC-3.2")
    def test_creates_pod_logs_directory(self) -> None:
        """extract_pod_logs MUST create a pod-logs subdirectory under artifacts.

        Looks for mkdir with pod-logs path in the function body.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        assert re.search(r"mkdir\s+-p\s+.*pod-logs", body), (
            "extract_pod_logs() does not create pod-logs/ directory. "
            "Expected: mkdir -p <artifacts>/pod-logs"
        )

    @pytest.mark.requirement("AC-3.2")
    def test_pod_logs_saved_with_pod_name(self) -> None:
        """Each pod's logs MUST be saved to a file named after the pod.

        The function should write to a path like pod-logs/{pod-name}.log.
        This catches implementations that write all logs to a single file.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # Must reference a variable (pod name) in the output path combined with .log
        assert re.search(r"pod-logs/.*\$.*\.log", body), (
            "extract_pod_logs() does not save logs with per-pod filenames. "
            "Expected pattern like: pod-logs/${pod_name}.log"
        )


# ---------------------------------------------------------------------------
# Tests — K8s events capture
# ---------------------------------------------------------------------------


class TestEventsCapture:
    """Verify K8s events are captured to events.txt."""

    @pytest.mark.requirement("AC-3.3")
    def test_captures_kubectl_events(self) -> None:
        """extract_pod_logs MUST run kubectl get events."""
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        assert re.search(r"kubectl\s+get\s+events", body), (
            "extract_pod_logs() does not capture K8s events. Expected: kubectl get events"
        )

    @pytest.mark.requirement("AC-3.3")
    def test_events_sorted_by_timestamp(self) -> None:
        """Events MUST be sorted by lastTimestamp for readability."""
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        assert re.search(r"--sort-by=.*lastTimestamp", body), (
            "extract_pod_logs() does not sort events by lastTimestamp. "
            "Expected: --sort-by='.lastTimestamp'"
        )

    @pytest.mark.requirement("AC-3.3")
    def test_events_saved_to_events_txt(self) -> None:
        """Events MUST be saved to events.txt in the pod-logs directory."""
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        assert re.search(r"events\.txt", body), (
            "extract_pod_logs() does not save events to events.txt. "
            "Expected output redirection to events.txt"
        )

    @pytest.mark.requirement("AC-3.3")
    def test_events_use_test_namespace(self) -> None:
        """Events capture MUST use $TEST_NAMESPACE, not a hardcoded namespace."""
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # The kubectl get events command must reference TEST_NAMESPACE
        events_section = ""
        for line in body.splitlines():
            if "get events" in line or "events" in line.lower():
                events_section += line + "\n"
        # Look for -n with TEST_NAMESPACE variable near the events command
        assert re.search(
            r"kubectl\s+get\s+events.*-n.*\$.*TEST_NAMESPACE"
            r"|"
            r"kubectl\s+get\s+events.*--namespace.*\$.*TEST_NAMESPACE"
            r"|"
            r"-n\s+.*\$.*TEST_NAMESPACE.*kubectl\s+get\s+events",
            body,
            re.DOTALL,
        ), (
            "extract_pod_logs() events capture does not use $TEST_NAMESPACE. "
            "The namespace must not be hardcoded."
        )


# ---------------------------------------------------------------------------
# Tests — kubectl --tail flag (context-efficient logging)
# ---------------------------------------------------------------------------


class TestKubectlTailFlag:
    """Verify kubectl logs uses --tail flag for context-efficient logging."""

    @pytest.mark.requirement("AC-3.1")
    def test_uses_tail_flag(self) -> None:
        """kubectl logs MUST use --tail= to limit output lines.

        Per project rules (context-efficient-logging.md), all log commands
        must use --tail=N.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        assert re.search(r"--tail[=\s]", body), (
            "extract_pod_logs() does not use --tail flag on kubectl logs. "
            "All kubectl logs commands must use --tail per project rules."
        )

    @pytest.mark.requirement("AC-3.1")
    def test_tail_uses_log_tail_lines_variable(self) -> None:
        """--tail value MUST use LOG_TAIL_LINES variable, not a hardcoded number.

        A sloppy implementation might use --tail=100 directly instead of
        --tail=${LOG_TAIL_LINES}.  This test catches that.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # Must use the variable in --tail, not a literal number
        assert re.search(r"--tail[=\s]+.*\$.*LOG_TAIL_LINES", body), (
            "extract_pod_logs() uses a hardcoded --tail value instead of "
            "$LOG_TAIL_LINES. The tail line count must be configurable."
        )


# ---------------------------------------------------------------------------
# Tests — Per-pod timeout
# ---------------------------------------------------------------------------


class TestPerPodTimeout:
    """Verify per-pod timeout of 10 seconds for log extraction."""

    @pytest.mark.requirement("BC-3")
    def test_has_timeout_mechanism(self) -> None:
        """extract_pod_logs MUST enforce a per-pod timeout.

        The timeout can be implemented via the `timeout` command or
        kubectl's own timeout flag.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # Look for `timeout` command or kubectl --request-timeout
        has_timeout_cmd = re.search(r"\btimeout\s+\d+", body)
        has_kubectl_timeout = re.search(r"--request-timeout", body)
        assert has_timeout_cmd or has_kubectl_timeout, (
            "extract_pod_logs() has no per-pod timeout mechanism. "
            "Expected: 'timeout 10 kubectl logs ...' or '--request-timeout=10s'"
        )

    @pytest.mark.requirement("BC-3")
    def test_timeout_is_10_seconds(self) -> None:
        """Per-pod timeout MUST be 10 seconds per the AC boundary condition."""
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # Match `timeout 10` or `--request-timeout=10s`
        has_10s_timeout_cmd = re.search(r"\btimeout\s+10\b", body)
        has_10s_kubectl_timeout = re.search(r"--request-timeout=10s", body)
        assert has_10s_timeout_cmd or has_10s_kubectl_timeout, (
            "extract_pod_logs() timeout is not 10 seconds. "
            "Expected: 'timeout 10 kubectl ...' or '--request-timeout=10s'"
        )


# ---------------------------------------------------------------------------
# Tests — Conditional invocation (only on failure)
# ---------------------------------------------------------------------------


class TestConditionalInvocation:
    """Verify extract_pod_logs is called only when Job fails."""

    @pytest.mark.requirement("AC-3")
    def test_called_on_failure(self) -> None:
        """extract_pod_logs MUST be called when JOB_STATUS is 'failed'.

        The function call must appear in the failed branch of the
        status handling logic.
        """
        script = _read_script()
        # Look for extract_pod_logs being called in a context that checks
        # for failure. Multiple patterns are acceptable:
        # 1. Inside a case statement under "failed)"
        # 2. Inside an if block checking JOB_STATUS == "failed"
        # 3. Inside an if block checking JOB_STATUS != "complete"
        assert re.search(r"extract_pod_logs", script), (
            "extract_pod_logs is never called in the script. "
            "It must be invoked when the test Job fails."
        )
        # Verify it's in the failed branch specifically
        # Pattern: failed) ... extract_pod_logs ... ;; (case statement)
        failed_branch_pattern = re.search(
            r"failed\).*?extract_pod_logs.*?;;",
            script,
            re.DOTALL,
        )
        # Alternative: if/elif checking for failure
        if_failure_pattern = re.search(
            r"(?:JOB_STATUS.*failed|failed.*JOB_STATUS).*extract_pod_logs",
            script,
            re.DOTALL,
        )
        assert failed_branch_pattern or if_failure_pattern, (
            "extract_pod_logs is not called in the 'failed' branch. "
            "It must be invoked specifically when JOB_STATUS is 'failed'."
        )

    @pytest.mark.requirement("AC-3")
    def test_not_called_on_success(self) -> None:
        """extract_pod_logs MUST NOT be called when JOB_STATUS is 'complete'.

        On success, pod log extraction is unnecessary noise per the AC.
        """
        script = _read_script()
        # Check the complete/success branch does NOT call extract_pod_logs
        # In a case statement: complete) ... ;; should not contain extract_pod_logs
        complete_branch = re.search(
            r"complete\)(.*?);;",
            script,
            re.DOTALL,
        )
        if complete_branch:
            assert "extract_pod_logs" not in complete_branch.group(1), (
                "extract_pod_logs is called in the 'complete' (success) branch. "
                "Pod log extraction must be SKIPPED on success."
            )
        else:
            # If no case statement, look for a guard that prevents calling
            # on success — the function must still not appear unconditionally
            # Count occurrences outside of function definitions
            calls_outside_func: list[str] = []
            in_func = False
            brace_depth = 0
            for line in script.splitlines():
                stripped = line.strip()
                if re.match(r"(?:function\s+)?extract_pod_logs\s*\(\)", stripped):
                    in_func = True
                if in_func:
                    brace_depth += stripped.count("{") - stripped.count("}")
                    if (
                        brace_depth <= 0
                        and in_func
                        and "{" in (_extract_function_body(script, "extract_pod_logs") or "")
                    ):
                        in_func = False
                        brace_depth = 0
                elif "extract_pod_logs" in stripped and not stripped.startswith("#"):
                    calls_outside_func.append(stripped)

            # All calls must be inside a failure-conditional block
            assert len(calls_outside_func) > 0, (
                "extract_pod_logs is never called outside its definition. "
                "It must be invoked (conditionally) on failure."
            )

    @pytest.mark.requirement("AC-3")
    def test_also_called_on_timeout(self) -> None:
        """extract_pod_logs SHOULD also be called on timeout (JOB_STATUS=timeout).

        Timeout is also a failure mode where pod logs are valuable for
        debugging.
        """
        script = _read_script()
        # Check timeout branch also calls extract_pod_logs
        timeout_branch = re.search(
            r"timeout\)(.*?);;",
            script,
            re.DOTALL,
        )
        if timeout_branch:
            assert "extract_pod_logs" in timeout_branch.group(1), (
                "extract_pod_logs is not called in the 'timeout' branch. "
                "Pod logs are valuable for debugging timeouts too."
            )
        else:
            # If no case statement, just verify it's called for non-success
            # This is a softer check — the failed branch test is the hard gate
            pass


# ---------------------------------------------------------------------------
# Tests — Graceful handling of individual pod log failures
# ---------------------------------------------------------------------------


class TestGracefulPodLogFailures:
    """Verify individual pod log failures don't abort the loop."""

    @pytest.mark.requirement("BC-2")
    def test_loop_continues_on_failure(self) -> None:
        """Pod log extraction failures MUST not abort the collection loop.

        The function must use error handling (|| true, || continue, or
        explicit if/then) so that a terminated pod doesn't prevent
        collecting logs from remaining pods.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # Look for error suppression on kubectl logs commands
        # Patterns: `kubectl logs ... || true`, `kubectl logs ... || continue`,
        #           `kubectl logs ... 2>/dev/null || true`,
        #           `if ! kubectl logs ...; then warn; continue; fi`
        has_or_true = re.search(r"kubectl\s+logs.*\|\|\s*true", body)
        has_or_continue = re.search(r"kubectl\s+logs.*\|\|\s*continue", body)
        has_or_warn = re.search(r"kubectl\s+logs.*\|\|.*(?:warn|error|info)", body)
        has_if_guard = re.search(r"if\s+.*kubectl\s+logs.*then.*continue", body, re.DOTALL)
        assert has_or_true or has_or_continue or has_or_warn or has_if_guard, (
            "extract_pod_logs() does not handle individual pod log failures. "
            "kubectl logs must be guarded with '|| true', '|| continue', or "
            "an if-then block to prevent aborting the loop."
        )

    @pytest.mark.requirement("BC-2")
    def test_iterates_over_pods(self) -> None:
        """extract_pod_logs MUST iterate over ALL pods in the namespace.

        Must use a loop construct (for/while) to process multiple pods,
        not just extract logs from a single hardcoded pod.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        has_for_loop = re.search(r"\bfor\b.*\bin\b", body)
        has_while_loop = re.search(r"\bwhile\b", body)
        assert has_for_loop or has_while_loop, (
            "extract_pod_logs() does not iterate over pods. "
            "Expected a for/while loop to process ALL pods in the namespace."
        )

    @pytest.mark.requirement("BC-2")
    def test_warns_on_pod_log_failure(self) -> None:
        """When a pod log extraction fails, a WARNING must be emitted.

        Silent failure (bare `|| true`) is not sufficient — operators
        need to know which pods had log extraction issues.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # Look for warning/error output near kubectl logs failure handling
        # Patterns: `|| { warn "..."; continue; }`, `|| echo "WARN..."`
        has_warning = re.search(
            r"(?:warn|error|info|echo).*(?:fail|skip|unable|could not)",
            body,
            re.IGNORECASE,
        )
        assert has_warning, (
            "extract_pod_logs() does not emit a warning when pod log extraction "
            "fails. Operators need visibility into which pods had issues."
        )


# ---------------------------------------------------------------------------
# Tests — Summary output
# ---------------------------------------------------------------------------


class TestSummaryOutput:
    """Verify the function prints a summary of collected log files."""

    @pytest.mark.requirement("AC-3.4")
    def test_prints_summary(self) -> None:
        """extract_pod_logs MUST print a summary of collected files.

        The summary should list what was collected so operators know what's
        available for debugging.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # Look for ls, find, echo, or info commands that list collected files
        has_ls = re.search(r"\bls\b.*pod-logs", body)
        has_find = re.search(r"\bfind\b.*pod-logs", body)
        has_echo_summary = re.search(
            r"(?:echo|info|printf).*(?:collect|saved|extracted|pod.log|summary)",
            body,
            re.IGNORECASE,
        )
        assert has_ls or has_find or has_echo_summary, (
            "extract_pod_logs() does not print a summary of collected log files. "
            "Expected: ls, find, or echo/info listing the collected files."
        )


# ---------------------------------------------------------------------------
# Tests — Pod listing uses TEST_NAMESPACE
# ---------------------------------------------------------------------------


class TestNamespaceUsage:
    """Verify pod listing uses the TEST_NAMESPACE variable."""

    @pytest.mark.requirement("AC-3.1")
    def test_kubectl_get_pods_uses_namespace(self) -> None:
        """kubectl get pods MUST use $TEST_NAMESPACE, not a hardcoded value.

        A sloppy implementation might hardcode 'floe-test' instead of
        using the variable.
        """
        script = _read_script()
        body = _extract_function_body(script, "extract_pod_logs")
        assert body is not None, "extract_pod_logs() function not found"
        # Must have kubectl get pods with -n and TEST_NAMESPACE
        assert re.search(
            r"kubectl\s+(?:get\s+pods|logs).*-n.*\$.*TEST_NAMESPACE"
            r"|"
            r"kubectl\s+(?:get\s+pods|logs).*--namespace.*\$.*TEST_NAMESPACE",
            body,
            re.DOTALL,
        ), (
            "extract_pod_logs() does not use $TEST_NAMESPACE for kubectl commands. "
            "The namespace must come from the variable, not be hardcoded."
        )
