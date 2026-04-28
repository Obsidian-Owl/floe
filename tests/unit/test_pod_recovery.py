"""Unit tests for testing.fixtures.kubernetes pod recovery utilities.

Tests verify behavioral contracts for kubectl/helm wrappers and pod recovery
logic. All subprocess calls are mocked -- these are unit tests that validate
argument construction, error handling, and return-value semantics.

Acceptance Criteria Covered:
    AC-1: All functions exist with correct signatures; namespace is explicit param
    BC-1: PodRecoveryError has actionable diagnostics (pod-not-found,
          kubectl-delete-failure, recovery-timeout) with DISTINCT messages
    BC-2: run_kubectl(namespace=None) omits -n flag from subprocess args
    BC-3: get_pod_uid returns None on kubectl failure or empty stdout

Test Type Rationale:
    Unit tests -- pure function behavior with subprocess mocked at boundary.
    subprocess.run is an external system call; mocking it is correct per
    TESTING.md boundary classification.
"""

from __future__ import annotations

import subprocess
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from testing.fixtures.kubernetes import (
    PodRecoveryError,
    PodRecoveryResult,
    assert_pod_recovery,
    check_pod_ready,
    get_pod_uid,
    run_helm,
    run_helm_template,
    run_kubectl,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_subprocess() -> Generator[MagicMock, None, None]:
    """Patch subprocess.run for kubectl/helm tests.

    Yields:
        The MagicMock replacing subprocess.run.
    """
    with patch("testing.fixtures.kubernetes.subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture()
def recovery_mocks() -> Generator[dict[str, MagicMock], None, None]:
    """Patch get_pod_uid, run_kubectl, and wait_for_condition for assert_pod_recovery tests.

    Provides a dict of mocks keyed by function name.

    Yields:
        Dict with keys 'get_pod_uid', 'run_kubectl', 'wait_for_condition'.
    """
    with (
        patch("testing.fixtures.kubernetes.get_pod_uid") as mock_get_uid,
        patch("testing.fixtures.kubernetes.run_kubectl") as mock_run_kubectl,
        patch("testing.fixtures.kubernetes.wait_for_condition") as mock_wait,
    ):
        yield {
            "get_pod_uid": mock_get_uid,
            "run_kubectl": mock_run_kubectl,
            "wait_for_condition": mock_wait,
        }


# ---------------------------------------------------------------------------
# TestRunKubectl
# ---------------------------------------------------------------------------


class TestRunKubectl:
    """Tests for run_kubectl subprocess wrapper."""

    @pytest.mark.requirement("AC-2.7")
    def test_namespace_included_when_specified(self, mock_subprocess: MagicMock) -> None:
        """Verify -n <namespace> is injected when namespace is provided.

        Ensures the constructed command includes -n before the namespace value
        and that both appear in the correct position (after 'kubectl', before args).
        """
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_kubectl(["get", "pods"], namespace="kube-system")

        actual_args: list[str] = mock_subprocess.call_args[0][0]
        assert actual_args[0] == "kubectl"
        # -n and namespace must be present and adjacent
        ns_idx = actual_args.index("-n")
        assert actual_args[ns_idx + 1] == "kube-system"
        # The user-supplied args must also be present
        assert "get" in actual_args
        assert "pods" in actual_args

    @pytest.mark.requirement("AC-2.7")
    def test_namespace_omitted_when_none(self, mock_subprocess: MagicMock) -> None:
        """Verify -n flag is NOT present when namespace is None (BC-2).

        A sloppy implementation might always append -n even with None.
        """
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_kubectl(["get", "nodes"], namespace=None)

        actual_args: list[str] = mock_subprocess.call_args[0][0]
        assert "-n" not in actual_args, "run_kubectl must omit -n flag when namespace is None"

    @pytest.mark.requirement("AC-2.7")
    def test_namespace_omitted_when_empty_string(self, mock_subprocess: MagicMock) -> None:
        """Verify -n flag is NOT present when namespace is empty string (BC-2).

        Empty string is falsy in Python, so it should behave like None.
        """
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_kubectl(["get", "pods"], namespace="")

        actual_args: list[str] = mock_subprocess.call_args[0][0]
        assert "-n" not in actual_args, "run_kubectl must omit -n flag for empty namespace"

    @pytest.mark.requirement("AC-2.7")
    def test_namespace_omitted_by_default(self, mock_subprocess: MagicMock) -> None:
        """Verify namespace defaults to None and -n is omitted (BC-2).

        Calling run_kubectl without the namespace kwarg must behave identically
        to namespace=None.
        """
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_kubectl(["version"])

        actual_args: list[str] = mock_subprocess.call_args[0][0]
        assert "-n" not in actual_args

    @pytest.mark.requirement("AC-2.7")
    def test_returns_completed_process(self, mock_subprocess: MagicMock) -> None:
        """Verify run_kubectl returns the subprocess.CompletedProcess unchanged.

        The wrapper must not swallow or transform the result.
        """
        expected = subprocess.CompletedProcess(
            args=["kubectl", "get", "pods"],
            returncode=0,
            stdout="NAME  READY\npod-1  1/1\n",
            stderr="",
        )
        mock_subprocess.return_value = expected

        result = run_kubectl(["get", "pods"], namespace="default")

        assert result is expected

    @pytest.mark.requirement("AC-2.7")
    def test_timeout_forwarded_to_subprocess(self, mock_subprocess: MagicMock) -> None:
        """Verify the timeout parameter is forwarded to subprocess.run."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_kubectl(["get", "pods"], namespace="default", timeout=120)

        _, kwargs = mock_subprocess.call_args
        assert kwargs.get("timeout") == 120

    @pytest.mark.requirement("AC-2.7")
    def test_default_timeout_is_60(self, mock_subprocess: MagicMock) -> None:
        """Verify default timeout is 60 seconds when not specified."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_kubectl(["get", "pods"])

        _, kwargs = mock_subprocess.call_args
        assert kwargs.get("timeout") == 60

    @pytest.mark.requirement("AC-2.7")
    def test_captures_output_as_text(self, mock_subprocess: MagicMock) -> None:
        """Verify subprocess.run is called with capture_output=True and text=True."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_kubectl(["get", "pods"])

        _, kwargs = mock_subprocess.call_args
        assert kwargs.get("capture_output") is True
        assert kwargs.get("text") is True

    @pytest.mark.requirement("AC-2.7")
    def test_does_not_use_shell(self, mock_subprocess: MagicMock) -> None:
        """Verify subprocess.run is NOT called with shell=True (security)."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_kubectl(["get", "pods"])

        _, kwargs = mock_subprocess.call_args
        # shell must be False or absent
        assert kwargs.get("shell", False) is False


# ---------------------------------------------------------------------------
# TestRunHelm
# ---------------------------------------------------------------------------


class TestRunHelm:
    """Tests for run_helm subprocess wrapper."""

    @pytest.mark.requirement("AC-2.7")
    def test_prepends_helm_to_args(self, mock_subprocess: MagicMock) -> None:
        """Verify 'helm' is the first element in the subprocess command."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_helm(["upgrade", "--install", "my-release", "my-chart"])

        actual_args: list[str] = mock_subprocess.call_args[0][0]
        assert actual_args[0] == "helm"
        assert "upgrade" in actual_args
        assert "--install" in actual_args

    @pytest.mark.requirement("AC-2.7")
    def test_default_timeout_is_900(self, mock_subprocess: MagicMock) -> None:
        """Verify default timeout is 900 seconds (15 minutes) for helm commands."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_helm(["list"])

        _, kwargs = mock_subprocess.call_args
        assert kwargs.get("timeout") == 900

    @pytest.mark.requirement("AC-2.7")
    def test_custom_timeout_forwarded(self, mock_subprocess: MagicMock) -> None:
        """Verify custom timeout is forwarded to subprocess.run."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_helm(["list"], timeout=300)

        _, kwargs = mock_subprocess.call_args
        assert kwargs.get("timeout") == 300

    @pytest.mark.requirement("AC-2.7")
    def test_returns_completed_process(self, mock_subprocess: MagicMock) -> None:
        """Verify run_helm returns the subprocess.CompletedProcess unchanged."""
        expected = subprocess.CompletedProcess(
            args=["helm", "list"],
            returncode=0,
            stdout="NAME\tREVISION\n",
            stderr="",
        )
        mock_subprocess.return_value = expected

        result = run_helm(["list"])

        assert result is expected

    @pytest.mark.requirement("AC-2.7")
    def test_does_not_use_shell(self, mock_subprocess: MagicMock) -> None:
        """Verify subprocess.run is NOT called with shell=True (security)."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_helm(["list"])

        _, kwargs = mock_subprocess.call_args
        assert kwargs.get("shell", False) is False


class TestRunHelmTemplate:
    """Tests for chart-driven Helm template rendering."""

    @pytest.mark.requirement("AC-2.7")
    def test_adds_chart_declared_repositories_before_dependency_build(
        self,
        tmp_path: Path,
        mock_subprocess: MagicMock,
    ) -> None:
        """Helm repositories must be derived from Chart.yaml dependencies."""
        chart_path = tmp_path / "chart"
        chart_path.mkdir()
        (chart_path / "Chart.yaml").write_text(
            """
apiVersion: v2
name: test-chart
version: 0.1.0
dependencies:
  - name: dagster
    version: 1.0.0
    repository: https://dagster-io.github.io/helm
  - name: opentelemetry-collector
    alias: otel
    version: 1.0.0
    repository: https://open-telemetry.github.io/opentelemetry-helm-charts
  - name: local-only
    version: 1.0.0
    repository: file://../local-only
""",
        )
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="rendered", stderr=""
        )

        result = run_helm_template("test-release", chart_path, timeout=60)

        assert result.returncode == 0
        commands = [call.args[0] for call in mock_subprocess.call_args_list]
        assert commands == [
            [
                "helm",
                "repo",
                "add",
                "dagster",
                "https://dagster-io.github.io/helm",
                "--force-update",
            ],
            [
                "helm",
                "repo",
                "add",
                "otel",
                "https://open-telemetry.github.io/opentelemetry-helm-charts",
                "--force-update",
            ],
            ["helm", "dependency", "build", str(chart_path)],
            ["helm", "template", "test-release", str(chart_path)],
        ]

    @pytest.mark.requirement("AC-2.7")
    def test_returns_repo_add_failure_before_rendering(
        self,
        tmp_path: Path,
        mock_subprocess: MagicMock,
    ) -> None:
        """Repository setup failures should be returned without template execution."""
        chart_path = tmp_path / "chart"
        chart_path.mkdir()
        (chart_path / "Chart.yaml").write_text(
            """
apiVersion: v2
name: test-chart
version: 0.1.0
dependencies:
  - name: dagster
    version: 1.0.0
    repository: https://dagster-io.github.io/helm
""",
        )
        expected = subprocess.CompletedProcess(
            args=["helm", "repo", "add"],
            returncode=1,
            stdout="",
            stderr="repo error",
        )
        mock_subprocess.return_value = expected

        result = run_helm_template("test-release", chart_path)

        assert result is expected
        assert len(mock_subprocess.call_args_list) == 1

    @pytest.mark.requirement("AC-2.7")
    def test_forwards_values_set_values_and_schema_flag(
        self,
        tmp_path: Path,
        mock_subprocess: MagicMock,
    ) -> None:
        """Template arguments should preserve caller-provided render options."""
        chart_path = tmp_path / "chart"
        chart_path.mkdir()
        (chart_path / "Chart.yaml").write_text(
            """
apiVersion: v2
name: test-chart
version: 0.1.0
""",
        )
        values_path = tmp_path / "values.yaml"
        values_path.write_text("networkPolicy:\n  enabled: true\n")
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="rendered", stderr=""
        )

        run_helm_template(
            "test-release",
            chart_path,
            values_path=values_path,
            set_values={"networkPolicy.enabled": "true"},
            skip_schema_validation=True,
        )

        template_command = mock_subprocess.call_args_list[-1].args[0]
        assert template_command == [
            "helm",
            "template",
            "test-release",
            str(chart_path),
            "--skip-schema-validation",
            "-f",
            str(values_path),
            "--set",
            "networkPolicy.enabled=true",
        ]


# ---------------------------------------------------------------------------
# TestGetPodUid
# ---------------------------------------------------------------------------


class TestGetPodUid:
    """Tests for get_pod_uid -- extracts UID from kubectl output."""

    @pytest.mark.requirement("AC-2.7")
    def test_returns_uid_on_success(self, mock_subprocess: MagicMock) -> None:
        """Verify UID is extracted from kubectl stdout on success.

        A correct implementation must strip whitespace from the output.
        """
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="abc-123-def-456\n",
            stderr="",
        )

        uid = get_pod_uid(label_selector="app=dagster", namespace="default")

        assert uid == "abc-123-def-456"

    @pytest.mark.requirement("AC-2.7")
    def test_returns_none_on_kubectl_failure(self, mock_subprocess: MagicMock) -> None:
        """Verify None is returned when kubectl exits non-zero (BC-3).

        A sloppy implementation might raise or return empty string.
        """
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="error: no matching pods found",
        )

        uid = get_pod_uid(label_selector="app=missing", namespace="default")

        assert uid is None

    @pytest.mark.requirement("AC-2.7")
    def test_returns_none_on_empty_stdout(self, mock_subprocess: MagicMock) -> None:
        """Verify None is returned when kubectl succeeds but stdout is empty (BC-3).

        This happens when the label selector matches no pods.
        A sloppy implementation might return empty string instead of None.
        """
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        uid = get_pod_uid(label_selector="app=ghost", namespace="default")

        assert uid is None

    @pytest.mark.requirement("AC-2.7")
    def test_returns_none_on_whitespace_only_stdout(self, mock_subprocess: MagicMock) -> None:
        """Verify None is returned when stdout is only whitespace (BC-3).

        Edge case: kubectl might emit trailing newlines with no content.
        """
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="   \n  \n",
            stderr="",
        )

        uid = get_pod_uid(label_selector="app=empty", namespace="default")

        assert uid is None

    @pytest.mark.requirement("AC-2.7")
    def test_passes_label_selector_to_kubectl(self, mock_subprocess: MagicMock) -> None:
        """Verify the label selector is forwarded to the kubectl command."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="uid-value\n", stderr=""
        )

        get_pod_uid(label_selector="app=dagster-webserver", namespace="staging")

        actual_args: list[str] = mock_subprocess.call_args[0][0]
        # The label selector must appear after -l
        assert "-l" in actual_args or "--selector" in actual_args
        # The actual selector value must be present
        assert "app=dagster-webserver" in actual_args

    @pytest.mark.requirement("AC-2.7")
    def test_passes_namespace_to_kubectl(self, mock_subprocess: MagicMock) -> None:
        """Verify namespace is forwarded as -n to kubectl."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="uid-value\n", stderr=""
        )

        get_pod_uid(label_selector="app=test", namespace="my-namespace")

        actual_args: list[str] = mock_subprocess.call_args[0][0]
        ns_idx = actual_args.index("-n")
        assert actual_args[ns_idx + 1] == "my-namespace"

    @pytest.mark.requirement("AC-2.7")
    def test_returns_none_on_subprocess_timeout(self, mock_subprocess: MagicMock) -> None:
        """Verify None is returned when subprocess times out (BC-3)."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=["kubectl"], timeout=60)

        uid = get_pod_uid(label_selector="app=slow", namespace="default")

        assert uid is None


# ---------------------------------------------------------------------------
# TestCheckPodReady
# ---------------------------------------------------------------------------


class TestCheckPodReady:
    """Tests for check_pod_ready -- checks pod readiness via kubectl."""

    @pytest.mark.requirement("AC-2.7")
    def test_returns_true_when_all_ready(self, mock_subprocess: MagicMock) -> None:
        """Verify True when all containers report Ready condition."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="True\n",
            stderr="",
        )

        result = check_pod_ready(label_selector="app=dagster", namespace="default")

        assert result is True

    @pytest.mark.requirement("AC-2.7")
    def test_returns_false_when_not_ready(self, mock_subprocess: MagicMock) -> None:
        """Verify False when pod reports not-Ready condition."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="False\n",
            stderr="",
        )

        result = check_pod_ready(label_selector="app=dagster", namespace="default")

        assert result is False

    @pytest.mark.requirement("AC-2.7")
    def test_returns_false_on_kubectl_failure(self, mock_subprocess: MagicMock) -> None:
        """Verify False when kubectl exits non-zero (pod not found, etc)."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="error: no matching pods",
        )

        result = check_pod_ready(label_selector="app=missing", namespace="default")

        assert result is False

    @pytest.mark.requirement("AC-2.7")
    def test_returns_false_on_empty_stdout(self, mock_subprocess: MagicMock) -> None:
        """Verify False when kubectl returns empty output (no pods matched)."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        result = check_pod_ready(label_selector="app=ghost", namespace="default")

        assert result is False

    @pytest.mark.requirement("AC-2.7")
    def test_passes_namespace_explicitly(self, mock_subprocess: MagicMock) -> None:
        """Verify namespace is passed as -n to kubectl (AC-1: explicit param)."""
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="True\n", stderr=""
        )

        check_pod_ready(label_selector="app=test", namespace="prod")

        actual_args: list[str] = mock_subprocess.call_args[0][0]
        ns_idx = actual_args.index("-n")
        assert actual_args[ns_idx + 1] == "prod"

    @pytest.mark.requirement("AC-2.7")
    def test_returns_false_when_mixed_statuses(self, mock_subprocess: MagicMock) -> None:
        """Verify False when multi-replica pods have mixed Ready statuses.

        kubectl returns space-separated statuses for multiple pods.
        If any pod is not Ready, the result must be False.
        """
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="True False True\n",
            stderr="",
        )

        result = check_pod_ready(label_selector="app=web", namespace="default")

        assert result is False

    @pytest.mark.requirement("AC-2.7")
    def test_returns_false_on_subprocess_timeout(self, mock_subprocess: MagicMock) -> None:
        """Verify False when subprocess times out.

        Like get_pod_uid, check_pod_ready catches TimeoutExpired and returns
        False — consistent behavior for both pod query functions.
        """
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=["kubectl"], timeout=60)

        result = check_pod_ready(label_selector="app=slow", namespace="default")

        assert result is False


# ---------------------------------------------------------------------------
# TestAssertPodRecovery
# ---------------------------------------------------------------------------


class TestAssertPodRecovery:
    """Tests for assert_pod_recovery -- orchestrates delete + wait + verify."""

    @pytest.mark.requirement("AC-2.7")
    def test_success_returns_pod_recovery_result(
        self, recovery_mocks: dict[str, MagicMock]
    ) -> None:
        """Verify successful recovery returns PodRecoveryResult with correct fields.

        Must return a PodRecoveryResult with original_uid != new_uid and
        recovery_seconds >= 0.
        """
        recovery_mocks["get_pod_uid"].side_effect = [
            "old-uid-111",  # initial lookup
            "new-uid-222",  # post-recovery lookup
        ]
        recovery_mocks["run_kubectl"].return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        recovery_mocks["wait_for_condition"].return_value = True

        result = assert_pod_recovery(
            label_selector="app=dagster",
            service_name="dagster",
            namespace="default",
            timeout=30.0,
        )

        assert isinstance(result, PodRecoveryResult)
        assert result.original_uid == "old-uid-111"
        assert result.new_uid == "new-uid-222"
        assert result.recovery_seconds >= 0.0

    @pytest.mark.requirement("AC-2.7")
    def test_success_result_has_different_uids(self, recovery_mocks: dict[str, MagicMock]) -> None:
        """Verify original_uid and new_uid are distinct after recovery.

        A sloppy implementation could return the same UID for both fields.
        """
        recovery_mocks["get_pod_uid"].side_effect = [
            "uid-before",
            "uid-after",
        ]
        recovery_mocks["run_kubectl"].return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        recovery_mocks["wait_for_condition"].return_value = True

        result = assert_pod_recovery(
            label_selector="app=test",
            service_name="test",
            namespace="default",
        )

        assert result.original_uid != result.new_uid
        assert result.original_uid == "uid-before"
        assert result.new_uid == "uid-after"

    @pytest.mark.requirement("AC-2.7")
    def test_raises_pod_not_found_when_initial_uid_is_none(
        self, recovery_mocks: dict[str, MagicMock]
    ) -> None:
        """Verify PodRecoveryError with 'not found' message when pod does not exist (BC-1).

        The error message must contain enough context to diagnose the issue:
        the label selector, namespace, and indication that the pod was not found.
        """
        recovery_mocks["get_pod_uid"].return_value = None

        with pytest.raises(PodRecoveryError, match="(?i)not.found") as exc_info:
            assert_pod_recovery(
                label_selector="app=missing",
                service_name="missing-svc",
                namespace="staging",
            )

        error_msg = str(exc_info.value)
        # Actionable diagnostics: must mention the selector and namespace
        assert "app=missing" in error_msg
        assert "staging" in error_msg

    @pytest.mark.requirement("AC-2.7")
    def test_raises_on_kubectl_delete_failure(self, recovery_mocks: dict[str, MagicMock]) -> None:
        """Verify PodRecoveryError with 'delete' message when kubectl delete fails (BC-1).

        The error must be distinguishable from pod-not-found and timeout errors.
        """
        recovery_mocks["get_pod_uid"].return_value = "uid-exists"
        recovery_mocks["run_kubectl"].return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="forbidden: cannot delete"
        )

        with pytest.raises(PodRecoveryError, match="(?i)delete") as exc_info:
            assert_pod_recovery(
                label_selector="app=locked",
                service_name="locked-svc",
                namespace="restricted",
            )

        error_msg = str(exc_info.value)
        # Must include stderr context for actionability (BC-1)
        assert "forbidden" in error_msg.lower()

    @pytest.mark.requirement("AC-2.7")
    def test_raises_on_recovery_timeout(self, recovery_mocks: dict[str, MagicMock]) -> None:
        """Verify PodRecoveryError with 'timeout' message when pod never recovers (BC-1).

        The error must be distinguishable from pod-not-found and delete-failure.
        """
        recovery_mocks["get_pod_uid"].side_effect = [
            "uid-original",  # initial lookup succeeds
            None,  # post-recovery lookup fails (pod never came back)
        ]
        recovery_mocks["run_kubectl"].return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        recovery_mocks["wait_for_condition"].return_value = False

        with pytest.raises(PodRecoveryError, match="(?i)timeout") as exc_info:
            assert_pod_recovery(
                label_selector="app=slow-start",
                service_name="slow-svc",
                namespace="default",
                timeout=5.0,
            )

        error_msg = str(exc_info.value)
        assert "slow-svc" in error_msg or "slow-start" in error_msg

    @pytest.mark.requirement("AC-2.7")
    def test_distinct_error_messages_for_each_failure_mode(
        self, recovery_mocks: dict[str, MagicMock]
    ) -> None:
        """Verify all three failure modes produce distinct error messages (BC-1).

        A sloppy implementation might use the same generic message for all
        failure modes, making diagnosis impossible.
        """
        # Collect error messages for each failure mode
        messages: list[str] = []

        # Mode 1: pod not found
        recovery_mocks["get_pod_uid"].return_value = None
        with pytest.raises(PodRecoveryError) as exc_info:
            assert_pod_recovery(
                label_selector="app=x",
                service_name="x",
                namespace="ns",
            )
        messages.append(str(exc_info.value))

        # Mode 2: delete failure
        recovery_mocks["get_pod_uid"].side_effect = None
        recovery_mocks["get_pod_uid"].return_value = "uid-exists"
        recovery_mocks["run_kubectl"].return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="cannot delete"
        )
        with pytest.raises(PodRecoveryError) as exc_info:
            assert_pod_recovery(
                label_selector="app=x",
                service_name="x",
                namespace="ns",
            )
        messages.append(str(exc_info.value))

        # Mode 3: timeout
        recovery_mocks["get_pod_uid"].side_effect = ["uid-orig", None]
        recovery_mocks["run_kubectl"].return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        recovery_mocks["wait_for_condition"].return_value = False
        with pytest.raises(PodRecoveryError) as exc_info:
            assert_pod_recovery(
                label_selector="app=x",
                service_name="x",
                namespace="ns",
                timeout=1.0,
            )
        messages.append(str(exc_info.value))

        # All three messages must be distinct
        assert len(set(messages)) == 3, f"Expected 3 distinct error messages, got: {messages}"

    @pytest.mark.requirement("AC-2.7")
    def test_invokes_run_kubectl_with_delete(self, recovery_mocks: dict[str, MagicMock]) -> None:
        """Verify assert_pod_recovery calls run_kubectl to delete the pod.

        Side-effect verification: must actually invoke the delete command,
        not just pretend to.
        """
        recovery_mocks["get_pod_uid"].side_effect = ["uid-before", "uid-after"]
        recovery_mocks["run_kubectl"].return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        recovery_mocks["wait_for_condition"].return_value = True

        assert_pod_recovery(
            label_selector="app=web",
            service_name="web",
            namespace="production",
        )

        recovery_mocks["run_kubectl"].assert_called_once()
        delete_args = recovery_mocks["run_kubectl"].call_args
        # Must include 'delete' in the kubectl args
        kubectl_cmd: list[str] = (
            delete_args[0][0] if delete_args[0] else delete_args[1].get("args", [])
        )
        assert "delete" in kubectl_cmd, f"Expected 'delete' in kubectl args, got: {kubectl_cmd}"

        # get_pod_uid must be called exactly twice (before delete + after recovery)
        assert recovery_mocks["get_pod_uid"].call_count == 2

    @pytest.mark.requirement("AC-2.7")
    def test_invokes_wait_for_condition(self, recovery_mocks: dict[str, MagicMock]) -> None:
        """Verify assert_pod_recovery calls wait_for_condition after delete.

        Side-effect verification: must poll for recovery, not just return immediately.
        """
        recovery_mocks["get_pod_uid"].side_effect = ["uid-a", "uid-b"]
        recovery_mocks["run_kubectl"].return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        recovery_mocks["wait_for_condition"].return_value = True

        assert_pod_recovery(
            label_selector="app=test",
            service_name="test",
            namespace="default",
            timeout=15.0,
        )

        recovery_mocks["wait_for_condition"].assert_called_once()

    @pytest.mark.requirement("AC-2.7")
    def test_passes_namespace_to_underlying_functions(
        self, recovery_mocks: dict[str, MagicMock]
    ) -> None:
        """Verify namespace is threaded through to get_pod_uid and run_kubectl (AC-1)."""
        recovery_mocks["get_pod_uid"].side_effect = ["uid-1", "uid-2"]
        recovery_mocks["run_kubectl"].return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        recovery_mocks["wait_for_condition"].return_value = True

        assert_pod_recovery(
            label_selector="app=x",
            service_name="x",
            namespace="custom-ns",
        )

        # get_pod_uid must receive the namespace
        for a_call in recovery_mocks["get_pod_uid"].call_args_list:
            assert a_call[1].get("namespace") == "custom-ns" or (
                len(a_call[0]) >= 2 and a_call[0][1] == "custom-ns"
            )

        # run_kubectl (delete) must receive the namespace
        delete_call = recovery_mocks["run_kubectl"].call_args
        assert delete_call[1].get("namespace") == "custom-ns"


# ---------------------------------------------------------------------------
# TestPodRecoveryResult
# ---------------------------------------------------------------------------


class TestPodRecoveryResult:
    """Tests for PodRecoveryResult NamedTuple structure."""

    @pytest.mark.requirement("AC-2.7")
    def test_fields_accessible_by_name(self) -> None:
        """Verify PodRecoveryResult fields are accessible as named attributes."""
        result = PodRecoveryResult(
            original_uid="uid-aaa",
            new_uid="uid-bbb",
            recovery_seconds=2.5,
        )

        assert result.original_uid == "uid-aaa"
        assert result.new_uid == "uid-bbb"
        assert result.recovery_seconds == pytest.approx(2.5)

    @pytest.mark.requirement("AC-2.7")
    def test_fields_accessible_by_index(self) -> None:
        """Verify PodRecoveryResult fields are accessible by index (NamedTuple contract)."""
        result = PodRecoveryResult(
            original_uid="uid-111",
            new_uid="uid-222",
            recovery_seconds=1.0,
        )

        assert result[0] == "uid-111"
        assert result[1] == "uid-222"
        assert result[2] == pytest.approx(1.0)

    @pytest.mark.requirement("AC-2.7")
    def test_has_exactly_three_fields(self) -> None:
        """Verify PodRecoveryResult has exactly 3 fields."""
        assert PodRecoveryResult._fields == (
            "original_uid",
            "new_uid",
            "recovery_seconds",
        )

    @pytest.mark.requirement("AC-2.7")
    def test_is_immutable(self) -> None:
        """Verify PodRecoveryResult is immutable (NamedTuple behavior)."""
        result = PodRecoveryResult(original_uid="x", new_uid="y", recovery_seconds=0.0)

        with pytest.raises(AttributeError):
            result.original_uid = "z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestPodRecoveryError
# ---------------------------------------------------------------------------


class TestPodRecoveryError:
    """Tests for PodRecoveryError exception class."""

    @pytest.mark.requirement("AC-2.7")
    def test_is_exception_subclass(self) -> None:
        """Verify PodRecoveryError is a proper Exception subclass."""
        assert issubclass(PodRecoveryError, Exception)

    @pytest.mark.requirement("AC-2.7")
    def test_preserves_message(self) -> None:
        """Verify PodRecoveryError preserves the error message."""
        error = PodRecoveryError("pod not found: app=test in namespace default")
        assert "pod not found" in str(error)
        assert "app=test" in str(error)

    @pytest.mark.requirement("AC-2.7")
    def test_can_be_raised_and_caught(self) -> None:
        """Verify PodRecoveryError can be raised and caught specifically."""
        with pytest.raises(PodRecoveryError, match="test message"):
            raise PodRecoveryError("test message")
