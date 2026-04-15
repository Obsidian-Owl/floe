"""Unit tests for Flux crash-recovery and controller health in E2E conftest.py.

Tests verify two new features added to tests/e2e/conftest.py:

1. ``_recover_suspended_flux()`` — session-scoped fixture that detects
   HelmReleases left in suspended state (from a crashed test run) and
   resumes them before the E2E suite starts.

2. ``_check_flux_controllers()`` — verifies Flux source-controller and
   helm-controller pods are Running before E2E tests depend on GitOps.

Tests are split into two categories:

- **Structural**: Parse conftest.py source to verify wiring, dependencies,
  and command patterns.  These guard against regressions where the code
  is refactored away or fixture wiring is broken.

- **Behavioral**: Import the functions and test with mocked subprocess.
  These verify logic: conditional branching, logging, error handling.

Acceptance Criteria Covered:
    AC-3: Session startup crash recovery (_recover_suspended_flux)
    AC-4: Flux controller smoke check (_check_flux_controllers)

Test Type Rationale:
    Unit tests -- subprocess.run is an external system boundary; mocking
    it is correct per TESTING.md.  Structural tests read source text to
    verify fixture wiring that cannot be tested via import alone.
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFTEST_PATH = _REPO_ROOT / "tests" / "e2e" / "conftest.py"

_CONFTEST_MODULE = "tests.e2e.conftest"

_RELEASE_PLATFORM = "floe-platform"
_RELEASE_JOBS = "floe-jobs-test"
_DEFAULT_NAMESPACE = "floe-test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _conftest_source() -> str:
    """Read conftest.py source text.

    Returns:
        Full source text of tests/e2e/conftest.py.

    Raises:
        FileNotFoundError: If conftest.py does not exist at expected path.
    """
    return _CONFTEST_PATH.read_text()


def _make_completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Create a subprocess.CompletedProcess with the given attributes.

    Args:
        returncode: Process exit code.
        stdout: Standard output text.
        stderr: Standard error text.

    Returns:
        CompletedProcess with the specified values.
    """
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_subprocess() -> Generator[MagicMock, None, None]:
    """Patch subprocess.run in the E2E conftest module.

    Yields:
        The MagicMock replacing subprocess.run.
    """
    with patch(f"{_CONFTEST_MODULE}.subprocess.run") as mock_run:
        yield mock_run


# ===========================================================================
# AC-3 STRUCTURAL: _recover_suspended_flux exists and is wired correctly
# ===========================================================================


class TestRecoverSuspendedFluxStructural:
    """Structural tests verifying _recover_suspended_flux in conftest.py.

    These parse conftest.py source to verify the fixture exists, is wired
    as a dependency of helm_release_health, and checks the correct releases.
    """

    @pytest.mark.requirement("AC-3")
    def test_recover_suspended_flux_function_exists(self) -> None:
        """conftest.py defines a _recover_suspended_flux function or fixture.

        The function must exist as a callable in the conftest module.  A
        sloppy implementation that omits the function entirely would fail
        this test.
        """
        source = _conftest_source()
        assert re.search(
            r"def\s+_recover_suspended_flux\s*\(",
            source,
        ), (
            "tests/e2e/conftest.py must define _recover_suspended_flux(). "
            "Function not found in source."
        )

    @pytest.mark.requirement("AC-3")
    def test_recover_suspended_flux_is_session_scoped(self) -> None:
        """_recover_suspended_flux must be a session-scoped fixture.

        It runs once per test session to recover from a prior crash.  Using
        function or module scope would run it too many times or not at all.
        """
        source = _conftest_source()
        # Find the fixture decorator near _recover_suspended_flux
        # Pattern: @pytest.fixture(...scope="session"...) before the def
        pattern = re.compile(
            r'@pytest\.fixture\([^)]*scope\s*=\s*["\']session["\'][^)]*\)\s*\n'
            r"(?:.*\n)*?"
            r"def\s+_recover_suspended_flux\s*\(",
        )
        assert pattern.search(source), (
            "_recover_suspended_flux must be decorated with "
            '@pytest.fixture(scope="session"). '
            "Found function but wrong scope or missing decorator."
        )

    @pytest.mark.requirement("AC-3")
    def test_helm_release_health_depends_on_recover_suspended_flux(self) -> None:
        """helm_release_health fixture must depend on _recover_suspended_flux.

        The dependency ensures crash recovery runs before Helm health checks.
        This can be via parameter injection or @pytest.mark.usefixtures.
        """
        source = _conftest_source()

        # Find the helm_release_health function definition and check parameters
        helm_health_match = re.search(
            r"def\s+helm_release_health\s*\(([^)]*)\)",
            source,
        )
        assert helm_health_match is not None, (
            "helm_release_health function not found in conftest.py"
        )

        params = helm_health_match.group(1)
        # Check direct parameter injection
        has_param_dependency = "_recover_suspended_flux" in params

        # Also check for usefixtures decorator above helm_release_health
        usefixtures_pattern = re.compile(
            r'@pytest\.mark\.usefixtures\(\s*["\']_recover_suspended_flux["\']\s*\)\s*\n'
            r"(?:.*\n)*?"
            r"def\s+helm_release_health\s*\(",
        )
        has_usefixtures = usefixtures_pattern.search(source) is not None

        assert has_param_dependency or has_usefixtures, (
            "helm_release_health must depend on _recover_suspended_flux "
            "via parameter injection or @pytest.mark.usefixtures. "
            f"Parameters found: '{params}'"
        )

    @pytest.mark.requirement("AC-3")
    def test_checks_floe_platform_helmrelease(self) -> None:
        """_recover_suspended_flux checks the floe-platform HelmRelease.

        The function must query the suspend status of floe-platform.
        """
        source = _conftest_source()
        assert "floe-platform" in source, (
            "conftest.py must reference floe-platform HelmRelease for crash recovery"
        )
        # More specific: the string must appear in the context of kubectl/suspend check
        # (not just as the existing helm release name in helm_release_health)
        recover_fn_match = re.search(
            r"def\s+_recover_suspended_flux\s*\(.*?\n"
            r"((?:.*\n)*?)"
            r"(?=\ndef\s|\Z)",
            source,
        )
        assert recover_fn_match is not None, "_recover_suspended_flux function body not found"
        fn_body = recover_fn_match.group(1)
        assert "floe-platform" in fn_body, (
            "_recover_suspended_flux must check floe-platform HelmRelease "
            "within its function body, not just elsewhere in conftest.py"
        )

    @pytest.mark.requirement("AC-3")
    def test_checks_floe_jobs_test_helmrelease(self) -> None:
        """_recover_suspended_flux checks the floe-jobs-test HelmRelease.

        Both releases must be checked. A partial implementation that only
        checks floe-platform would leave floe-jobs-test stuck.
        """
        source = _conftest_source()
        recover_fn_match = re.search(
            r"def\s+_recover_suspended_flux\s*\(.*?\n"
            r"((?:.*\n)*?)"
            r"(?=\ndef\s|\Z)",
            source,
        )
        assert recover_fn_match is not None, "_recover_suspended_flux function body not found"
        fn_body = recover_fn_match.group(1)
        assert "floe-jobs-test" in fn_body, (
            "_recover_suspended_flux must check floe-jobs-test HelmRelease. "
            "Only checking floe-platform is a partial implementation."
        )

    @pytest.mark.requirement("AC-3")
    def test_uses_kubectl_get_helmrelease_with_jsonpath(self) -> None:
        """_recover_suspended_flux queries suspend status via kubectl jsonpath.

        Must use kubectl get helmrelease with jsonpath to read .spec.suspend.
        """
        source = _conftest_source()
        recover_fn_match = re.search(
            r"def\s+_recover_suspended_flux\s*\(.*?\n"
            r"((?:.*\n)*?)"
            r"(?=\ndef\s|\Z)",
            source,
        )
        assert recover_fn_match is not None
        fn_body = recover_fn_match.group(1)

        assert re.search(r"kubectl.*get.*helmrelease", fn_body), (
            "_recover_suspended_flux must run 'kubectl get helmrelease' to query suspend status"
        )
        assert re.search(r"\.spec\.suspend", fn_body), (
            "_recover_suspended_flux must query .spec.suspend via jsonpath"
        )

    @pytest.mark.requirement("AC-3")
    def test_uses_flux_resume_command(self) -> None:
        """_recover_suspended_flux uses 'flux resume helmrelease' to unsuspend.

        Must use the flux CLI resume command, not kubectl patch.
        """
        source = _conftest_source()
        recover_fn_match = re.search(
            r"def\s+_recover_suspended_flux\s*\(.*?\n"
            r"((?:.*\n)*?)"
            r"(?=\ndef\s|\Z)",
            source,
        )
        assert recover_fn_match is not None
        fn_body = recover_fn_match.group(1)

        assert re.search(r"flux.*resume.*helmrelease", fn_body), (
            "_recover_suspended_flux must use 'flux resume helmrelease' command. "
            "Found no matching pattern in the function body."
        )


# ===========================================================================
# AC-3 BEHAVIORAL: _recover_suspended_flux logic
# ===========================================================================


class TestRecoverSuspendedFluxBehavioral:
    """Behavioral tests for _recover_suspended_flux() with mocked subprocess.

    These import the function and verify its logic: when it resumes,
    when it no-ops, and what it logs.
    """

    @pytest.mark.requirement("AC-3")
    def test_import_recover_suspended_flux(self) -> None:
        """_recover_suspended_flux is importable from tests.e2e.conftest.

        This test fails with ImportError until the function is implemented.
        """
        from tests.e2e.conftest import _recover_suspended_flux

        assert callable(_recover_suspended_flux)

    @pytest.mark.requirement("AC-3")
    def test_noop_when_kubectl_returns_nonzero(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Returns silently when kubectl returns non-zero (no Flux CRD).

        When kubectl get helmrelease fails (CRD not installed, no cluster),
        the function must return without attempting flux resume. This is the
        "no Flux installed" graceful degradation path.
        """
        from tests.e2e.conftest import _recover_suspended_flux

        # kubectl get helmrelease fails for both releases
        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr='error: the server doesn\'t have a resource type "helmrelease"',
        )

        # Must not raise
        _recover_suspended_flux()

        # Should NOT have run any flux resume commands
        for c in mock_subprocess.call_args_list:
            args = c[0][0] if c[0] else c[1].get("args", [])
            if isinstance(args, list):
                assert "resume" not in args, (
                    "_recover_suspended_flux must not attempt flux resume "
                    "when kubectl get helmrelease returns non-zero"
                )

    @pytest.mark.requirement("AC-3")
    def test_resumes_when_suspend_is_true(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Runs flux resume when kubectl reports suspend=true.

        When kubectl get helmrelease returns 0 and jsonpath output is "true",
        the function must run flux resume for that release.
        """
        from tests.e2e.conftest import _recover_suspended_flux

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """Simulate kubectl returning suspend=true, and flux resume succeeding."""
            if "kubectl" in cmd and "get" in cmd and "helmrelease" in cmd:
                return _make_completed_process(returncode=0, stdout="true")
            if "flux" in cmd and "resume" in cmd:
                return _make_completed_process(returncode=0)
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        _recover_suspended_flux()

        # Verify flux resume was called
        resume_calls = [
            c
            for c in mock_subprocess.call_args_list
            if isinstance(c[0][0], list) and "resume" in c[0][0]
        ]
        assert len(resume_calls) >= 1, (
            "_recover_suspended_flux must run 'flux resume' when suspend=true. "
            f"All calls: {[c[0][0] for c in mock_subprocess.call_args_list]}"
        )

    @pytest.mark.requirement("AC-3")
    def test_resumes_both_releases_when_both_suspended(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Resumes BOTH floe-platform and floe-jobs-test when both are suspended.

        A partial implementation that only checks one release would fail this test.
        """
        from tests.e2e.conftest import _recover_suspended_flux

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """Both releases suspended, resume succeeds."""
            if "kubectl" in cmd and "get" in cmd and "helmrelease" in cmd:
                return _make_completed_process(returncode=0, stdout="true")
            if "flux" in cmd and "resume" in cmd:
                return _make_completed_process(returncode=0)
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        _recover_suspended_flux()

        resume_calls = [
            c
            for c in mock_subprocess.call_args_list
            if isinstance(c[0][0], list) and "resume" in c[0][0]
        ]

        # Extract release names from resume commands
        resumed_names: set[str] = set()
        for c in resume_calls:
            args: list[str] = c[0][0]
            # flux resume helmrelease <name> -n <ns>
            if "helmrelease" in args:
                hr_idx = args.index("helmrelease")
                if hr_idx + 1 < len(args):
                    resumed_names.add(args[hr_idx + 1])

        assert _RELEASE_PLATFORM in resumed_names, (
            f"Must resume {_RELEASE_PLATFORM}. Resumed: {resumed_names}"
        )
        assert _RELEASE_JOBS in resumed_names, (
            f"Must resume {_RELEASE_JOBS}. Resumed: {resumed_names}"
        )

    @pytest.mark.requirement("AC-3")
    def test_does_not_resume_when_suspend_is_not_true(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Does NOT resume when suspend value is not exactly "true".

        When kubectl returns empty string, "false", or other values,
        the function must NOT attempt to resume. A sloppy implementation
        that resumes on any non-error kubectl response would fail this.
        """
        from tests.e2e.conftest import _recover_suspended_flux

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """kubectl succeeds but suspend is "false" or empty."""
            if "kubectl" in cmd and "get" in cmd and "helmrelease" in cmd:
                # Suspend is not set (empty output) or explicitly false
                return _make_completed_process(returncode=0, stdout="")
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        _recover_suspended_flux()

        # No flux resume should have been called
        resume_calls = [
            c
            for c in mock_subprocess.call_args_list
            if isinstance(c[0][0], list) and "resume" in c[0][0]
        ]
        assert len(resume_calls) == 0, (
            "_recover_suspended_flux must NOT resume when suspend is not 'true'. "
            f"resume calls found: {[c[0][0] for c in resume_calls]}"
        )

    @pytest.mark.requirement("AC-3")
    def test_does_not_resume_when_suspend_is_false_string(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Does NOT resume when suspend value is explicitly "false".

        Complements the empty-string test above. A sloppy implementation
        that checks `if stdout:` (truthy) instead of `if stdout == "true"`
        would resume on "false" too.
        """
        from tests.e2e.conftest import _recover_suspended_flux

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """kubectl succeeds and suspend is "false"."""
            if "kubectl" in cmd and "get" in cmd and "helmrelease" in cmd:
                return _make_completed_process(returncode=0, stdout="false")
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        _recover_suspended_flux()

        resume_calls = [
            c
            for c in mock_subprocess.call_args_list
            if isinstance(c[0][0], list) and "resume" in c[0][0]
        ]
        assert len(resume_calls) == 0, (
            "_recover_suspended_flux must NOT resume when suspend is 'false'. "
            "Must compare against exact string 'true', not truthiness."
        )

    @pytest.mark.requirement("AC-3")
    def test_logs_warning_when_resuming(
        self,
        mock_subprocess: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Logs a WARNING when resuming a suspended HelmRelease.

        Operators need to know that a crash-recovery resume happened.
        The log message must be at WARNING level and mention the release name.
        """
        from tests.e2e.conftest import _recover_suspended_flux

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """suspend=true for all releases, resume succeeds."""
            if "kubectl" in cmd and "get" in cmd and "helmrelease" in cmd:
                return _make_completed_process(returncode=0, stdout="true")
            if "flux" in cmd and "resume" in cmd:
                return _make_completed_process(returncode=0)
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        with caplog.at_level(logging.WARNING):
            _recover_suspended_flux()

        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) >= 1, (
            "_recover_suspended_flux must log a WARNING when resuming a suspended "
            "HelmRelease. No warning records found."
        )

        # Warning must identify which release was resumed
        combined_warnings = " ".join(r.message for r in warning_records).lower()
        assert "suspend" in combined_warnings or "resume" in combined_warnings, (
            "Warning message must mention 'suspend' or 'resume'. "
            f"Got: {[r.message for r in warning_records]}"
        )

    @pytest.mark.requirement("AC-3")
    def test_selective_resume_only_suspended_release(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Only resumes the release that is actually suspended, not both.

        If floe-platform is suspended but floe-jobs-test is not, only
        floe-platform should get a flux resume call. A naive implementation
        that always resumes both would fail this test.
        """
        from tests.e2e.conftest import _recover_suspended_flux

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """floe-platform is suspended, floe-jobs-test is not."""
            if "kubectl" in cmd and "get" in cmd and "helmrelease" in cmd:
                # Determine which release is being queried
                if _RELEASE_PLATFORM in cmd:
                    return _make_completed_process(returncode=0, stdout="true")
                if _RELEASE_JOBS in cmd:
                    return _make_completed_process(returncode=0, stdout="false")
                # Fallback: not suspended
                return _make_completed_process(returncode=0, stdout="false")
            if "flux" in cmd and "resume" in cmd:
                return _make_completed_process(returncode=0)
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        _recover_suspended_flux()

        resume_calls = [
            c
            for c in mock_subprocess.call_args_list
            if isinstance(c[0][0], list) and "resume" in c[0][0]
        ]

        # Extract which releases were resumed
        resumed_names: set[str] = set()
        for c in resume_calls:
            args: list[str] = c[0][0]
            if "helmrelease" in args:
                hr_idx = args.index("helmrelease")
                if hr_idx + 1 < len(args):
                    resumed_names.add(args[hr_idx + 1])

        assert _RELEASE_PLATFORM in resumed_names, (
            f"Must resume {_RELEASE_PLATFORM} when it is suspended"
        )
        assert _RELEASE_JOBS not in resumed_names, (
            f"Must NOT resume {_RELEASE_JOBS} when it is not suspended. "
            "Only suspended releases should be resumed."
        )


# ===========================================================================
# AC-4 STRUCTURAL: Flux controller smoke check in conftest.py
# ===========================================================================


class TestFluxControllerSmokeCheckStructural:
    """Structural tests verifying Flux controller health check in conftest.py.

    These parse conftest.py source to verify the check exists and uses
    the correct label selectors and controller names.
    """

    @pytest.mark.requirement("AC-4")
    def test_check_flux_controllers_function_exists(self) -> None:
        """conftest.py defines _check_flux_controllers or equivalent logic.

        The Flux controller health verification must exist as a function
        that can be called during the infrastructure smoke check.
        """
        source = _conftest_source()
        # Accept either a standalone function or inline logic
        has_function = re.search(
            r"def\s+_check_flux_controllers\s*\(",
            source,
        )
        # Also accept it as inline code in infrastructure_smoke_check
        has_inline = (
            "source-controller" in source
            and "helm-controller" in source
            and "flux-system" in source
        )
        assert has_function or has_inline, (
            "conftest.py must contain Flux controller health check logic "
            "(either as _check_flux_controllers function or inline in "
            "infrastructure_smoke_check). Neither found."
        )

    @pytest.mark.requirement("AC-4")
    def test_uses_component_label_selector(self) -> None:
        """Flux controller check uses app.kubernetes.io/component labels.

        Must use the standard Flux label selector to find controller pods,
        not pod name matching which is fragile.
        """
        source = _conftest_source()
        assert "app.kubernetes.io/component" in source, (
            "Flux controller check must use 'app.kubernetes.io/component' "
            "label selector to find controller pods."
        )

    @pytest.mark.requirement("AC-4")
    def test_checks_source_controller(self) -> None:
        """Flux controller check covers source-controller.

        source-controller is required for Flux to pull HelmRepository sources.
        """
        source = _conftest_source()
        assert "source-controller" in source, (
            "Flux controller check must verify source-controller pod health. "
            "String 'source-controller' not found in conftest.py."
        )

    @pytest.mark.requirement("AC-4")
    def test_checks_helm_controller(self) -> None:
        """Flux controller check covers helm-controller.

        helm-controller is required for Flux to reconcile HelmReleases.
        """
        source = _conftest_source()
        assert "helm-controller" in source, (
            "Flux controller check must verify helm-controller pod health. "
            "String 'helm-controller' not found in conftest.py."
        )

    @pytest.mark.requirement("AC-4")
    def test_queries_flux_system_namespace(self) -> None:
        """Flux controller check queries the flux-system namespace.

        Flux controllers live in flux-system by default. The check must
        target this namespace explicitly.
        """
        source = _conftest_source()
        assert "flux-system" in source, "Flux controller check must query 'flux-system' namespace."

    @pytest.mark.requirement("AC-4")
    def test_queries_pod_status_phase(self) -> None:
        """Flux controller check reads pod status.phase.

        Must use jsonpath to read .status.phase from the controller pods
        to determine if they are Running.
        """
        source = _conftest_source()
        assert re.search(r"status\.phase", source), (
            "Flux controller check must query .status.phase to determine "
            "if controller pods are Running."
        )


# ===========================================================================
# AC-4 BEHAVIORAL: _check_flux_controllers logic
# ===========================================================================


class TestFluxControllerSmokeCheckBehavioral:
    """Behavioral tests for _check_flux_controllers() with mocked subprocess.

    These import the function and test its logic with various subprocess
    outcomes: healthy controllers, unhealthy controllers, and missing Flux.
    """

    @pytest.mark.requirement("AC-4")
    def test_import_check_flux_controllers(self) -> None:
        """_check_flux_controllers is importable from tests.e2e.conftest.

        This test fails with ImportError until the function is implemented.
        """
        from tests.e2e.conftest import _check_flux_controllers

        assert callable(_check_flux_controllers)

    @pytest.mark.requirement("AC-4")
    def test_noop_when_flux_system_namespace_missing(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Returns silently when flux-system namespace does not exist.

        When kubectl get namespace flux-system returns non-zero, Flux is
        not installed and the check must be a no-op (not pytest.skip).
        """
        from tests.e2e.conftest import _check_flux_controllers

        # kubectl get namespace flux-system returns non-zero
        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr='Error from server (NotFound): namespaces "flux-system" not found',
        )

        # Must not raise or call pytest.fail/pytest.skip
        _check_flux_controllers()

    @pytest.mark.requirement("AC-4")
    def test_noop_logs_info_when_no_flux(
        self,
        mock_subprocess: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Logs INFO (not WARNING/ERROR) when Flux is not installed.

        The AC specifies INFO log, not pytest.skip(). This distinguishes
        "Flux not installed (OK)" from "Flux broken (FAIL)".
        """
        from tests.e2e.conftest import _check_flux_controllers

        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr='Error from server (NotFound): namespaces "flux-system" not found',
        )

        with caplog.at_level(logging.DEBUG):
            _check_flux_controllers()

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) >= 1, (
            "_check_flux_controllers must log an INFO message when Flux "
            "namespace is missing, indicating no-op. Found no INFO records."
        )

    @pytest.mark.requirement("AC-4")
    def test_does_not_skip_when_no_flux(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Does NOT call pytest.skip() when Flux is not installed.

        Per AC-4: "NOT a pytest.skip()". The function must return normally,
        not skip the test session.
        """
        from tests.e2e.conftest import _check_flux_controllers

        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr='namespaces "flux-system" not found',
        )

        # If pytest.skip() is called, it raises Skipped exception
        # This test PASSES only if no skip is raised
        _check_flux_controllers()
        # If we reach here, no skip was raised. Good.

    @pytest.mark.requirement("AC-4")
    def test_passes_when_both_controllers_running(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Passes without error when both controllers report Running.

        This is the happy path: namespace exists, both pods are Running.
        """
        from tests.e2e.conftest import _check_flux_controllers

        call_count = 0

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """Namespace exists, both controllers Running."""
            nonlocal call_count
            if "get" in cmd and "namespace" in cmd and "flux-system" in cmd:
                return _make_completed_process(returncode=0)
            if "get" in cmd and "pods" in cmd and "flux-system" in cmd:
                call_count += 1
                return _make_completed_process(returncode=0, stdout="Running")
            return _make_completed_process(returncode=0, stdout="Running")

        mock_subprocess.side_effect = _kubectl_side_effect

        # Must not raise
        _check_flux_controllers()

    @pytest.mark.requirement("AC-4")
    def test_fails_when_source_controller_not_running(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Fails with pytest.fail() when source-controller is not Running.

        When the source-controller pod is CrashLoopBackOff, the function
        must call pytest.fail() with a descriptive message.
        """
        from tests.e2e.conftest import _check_flux_controllers

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """Namespace exists, source-controller is crashing."""
            if "get" in cmd and "namespace" in cmd:
                return _make_completed_process(returncode=0)
            if "get" in cmd and "pods" in cmd:
                # Check which controller is being queried
                cmd_str = " ".join(cmd)
                if "source-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout="CrashLoopBackOff")
                if "helm-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout="Running")
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        with pytest.raises(pytest.fail.Exception):
            _check_flux_controllers()

    @pytest.mark.requirement("AC-4")
    def test_fails_when_helm_controller_not_running(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Fails with pytest.fail() when helm-controller is not Running.

        Complement to the source-controller test. A partial implementation
        that only checks one controller would pass one test but fail this one.
        """
        from tests.e2e.conftest import _check_flux_controllers

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """Namespace exists, helm-controller is pending."""
            if "get" in cmd and "namespace" in cmd:
                return _make_completed_process(returncode=0)
            if "get" in cmd and "pods" in cmd:
                cmd_str = " ".join(cmd)
                if "source-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout="Running")
                if "helm-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout="Pending")
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        with pytest.raises(pytest.fail.Exception):
            _check_flux_controllers()

    @pytest.mark.requirement("AC-4")
    def test_failure_message_includes_controller_name(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Failure message includes the name of the failing controller.

        Operators need to know WHICH controller is broken. A generic
        "Flux check failed" message would fail this test.
        """
        from tests.e2e.conftest import _check_flux_controllers

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """helm-controller is in ImagePullBackOff."""
            if "get" in cmd and "namespace" in cmd:
                return _make_completed_process(returncode=0)
            if "get" in cmd and "pods" in cmd:
                cmd_str = " ".join(cmd)
                if "source-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout="Running")
                if "helm-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout="ImagePullBackOff")
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        with pytest.raises(pytest.fail.Exception, match="helm-controller"):
            _check_flux_controllers()

    @pytest.mark.requirement("AC-4")
    def test_failure_message_includes_actual_status(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Failure message includes the actual pod status (e.g. CrashLoopBackOff).

        Operators need to see the actual status, not just "not Running".
        """
        from tests.e2e.conftest import _check_flux_controllers

        bad_status = "CrashLoopBackOff"

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """source-controller in CrashLoopBackOff."""
            if "get" in cmd and "namespace" in cmd:
                return _make_completed_process(returncode=0)
            if "get" in cmd and "pods" in cmd:
                cmd_str = " ".join(cmd)
                if "source-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout=bad_status)
                if "helm-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout="Running")
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        with pytest.raises(pytest.fail.Exception, match=bad_status):
            _check_flux_controllers()

    @pytest.mark.requirement("AC-4")
    def test_checks_both_controllers_not_just_first(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Verifies BOTH controllers are checked, not just the first.

        A sloppy implementation that returns after checking source-controller
        would miss a broken helm-controller. This test has source-controller
        healthy but helm-controller broken.
        """
        from tests.e2e.conftest import _check_flux_controllers

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """source-controller OK, helm-controller broken."""
            if "get" in cmd and "namespace" in cmd:
                return _make_completed_process(returncode=0)
            if "get" in cmd and "pods" in cmd:
                cmd_str = " ".join(cmd)
                if "source-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout="Running")
                if "helm-controller" in cmd_str:
                    return _make_completed_process(returncode=0, stdout="Error")
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        with pytest.raises(pytest.fail.Exception):
            _check_flux_controllers()

    @pytest.mark.requirement("AC-4")
    def test_strips_whitespace_from_status(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """Handles trailing newline/whitespace in kubectl output.

        kubectl jsonpath may include a trailing newline. The function must
        strip whitespace before comparing against "Running".
        """
        from tests.e2e.conftest import _check_flux_controllers

        def _kubectl_side_effect(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            """Both controllers Running but with trailing whitespace."""
            if "get" in cmd and "namespace" in cmd:
                return _make_completed_process(returncode=0)
            if "get" in cmd and "pods" in cmd:
                # Trailing newline, as kubectl often produces
                return _make_completed_process(returncode=0, stdout="Running\n")
            return _make_completed_process(returncode=0)

        mock_subprocess.side_effect = _kubectl_side_effect

        # Must not raise -- "Running\n" should be treated as "Running"
        _check_flux_controllers()
