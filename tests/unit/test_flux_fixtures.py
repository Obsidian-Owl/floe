"""Unit tests for testing.fixtures.flux Flux v2 GitOps pytest fixtures.

Tests verify behavioral contracts for Flux suspend/resume helpers and the
flux_suspended pytest fixture. All subprocess calls are mocked -- these are
unit tests that validate argument construction, error handling, logging,
and return-value semantics.

Acceptance Criteria Covered:
    AC-1: flux_suspended fixture suspends and resumes HelmRelease
    AC-2: flux_suspended degrades gracefully without Flux
    AC-7: All Flux subprocess calls log on failure (P56 compliance)
    AC-8: Flux helpers are importable without Flux installed

Test Type Rationale:
    Unit tests -- pure function behavior with subprocess mocked at boundary.
    subprocess.run is an external system call; mocking it is correct per
    TESTING.md boundary classification.
"""

from __future__ import annotations

import inspect
import logging
import subprocess
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_RELEASE_NAME = "floe-platform"
_DEFAULT_NAMESPACE = "floe-test"

_MODULE_PATH = "testing.fixtures.flux"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_subprocess() -> Generator[MagicMock, None, None]:
    """Patch subprocess.run for flux/kubectl tests.

    Yields:
        The MagicMock replacing subprocess.run in the flux module.
    """
    with patch(f"{_MODULE_PATH}.subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture()
def mock_shutil_which() -> Generator[MagicMock, None, None]:
    """Patch shutil.which for flux CLI detection tests.

    Yields:
        The MagicMock replacing shutil.which in the flux module.
    """
    with patch(f"{_MODULE_PATH}.shutil.which") as mock_which:
        yield mock_which


@pytest.fixture()
def mock_request() -> MagicMock:
    """Create a mock pytest.FixtureRequest for fixture tests.

    Returns:
        A MagicMock with addfinalizer method.
    """
    request = MagicMock(spec=pytest.FixtureRequest)
    request.addfinalizer = MagicMock()
    return request


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


# ===========================================================================
# AC-8: Flux helpers are importable without Flux installed
# ===========================================================================


class TestFluxModuleImportability:
    """Tests that the flux module is importable without Flux packages."""

    @pytest.mark.requirement("AC-8")
    def test_flux_module_importable(self) -> None:
        """testing.fixtures.flux module can be imported.

        The module must exist and be importable. This test will fail with
        ImportError until the module is created.
        """
        import testing.fixtures.flux  # noqa: F401

    @pytest.mark.requirement("AC-8")
    def test_flux_module_exports_expected_functions(self) -> None:
        """Module exports is_flux_managed, suspend_helmrelease, resume_helmrelease.

        All three public functions must be importable by name.
        """
        from testing.fixtures.flux import (
            is_flux_managed,
            resume_helmrelease,
            suspend_helmrelease,
        )

        assert callable(is_flux_managed)
        assert callable(suspend_helmrelease)
        assert callable(resume_helmrelease)

    @pytest.mark.requirement("AC-8")
    def test_flux_module_exports_fixture(self) -> None:
        """Module exports flux_suspended fixture function."""
        from testing.fixtures.flux import flux_suspended

        assert callable(flux_suspended)

    @pytest.mark.requirement("AC-8")
    def test_no_flux_python_packages_imported(self) -> None:
        """Module does not import any Flux-specific Python packages.

        All Flux interactions must be via subprocess. Importing flux-specific
        libraries (e.g., fluxcd, flux-local) would break importability on
        systems without Flux installed.
        """
        import testing.fixtures.flux as flux_mod

        source = inspect.getsource(flux_mod)

        # Flux-specific packages that must NOT be imported
        forbidden_imports = [
            "import fluxcd",
            "from fluxcd",
            "import flux_local",
            "from flux_local",
            "import flux",
            "from flux import",
        ]
        for pattern in forbidden_imports:
            assert pattern not in source, (
                f"testing.fixtures.flux must not contain '{pattern}'. "
                f"All Flux interactions must be via subprocess."
            )

    @pytest.mark.requirement("AC-8")
    def test_module_uses_subprocess_for_kubectl(self) -> None:
        """Module uses subprocess module for kubectl/flux CLI calls.

        Verifies that subprocess is imported, confirming the design choice
        of CLI-based interaction rather than Python SDK.
        """
        import testing.fixtures.flux as flux_mod

        source = inspect.getsource(flux_mod)
        assert "import subprocess" in source or "from subprocess" in source, (
            "testing.fixtures.flux must import subprocess for CLI interactions."
        )


# ===========================================================================
# AC-1 / AC-2: is_flux_managed
# ===========================================================================


class TestIsFluxManaged:
    """Tests for is_flux_managed() function."""

    @pytest.mark.requirement("AC-1")
    def test_returns_true_when_kubectl_succeeds(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """is_flux_managed returns True when kubectl get helmrelease succeeds.

        When the Flux CRD is installed and the HelmRelease exists,
        kubectl returns 0 and the function must return True.
        """
        from testing.fixtures.flux import is_flux_managed

        mock_subprocess.return_value = _make_completed_process(
            returncode=0,
            stdout='{"metadata":{"name":"floe-platform"}}',
        )

        result = is_flux_managed(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert result is True

    @pytest.mark.requirement("AC-2")
    def test_returns_false_when_crd_not_installed(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """is_flux_managed returns False when Flux CRD is not installed.

        When kubectl get helmrelease returns non-zero (CRD doesn't exist),
        the function must return False without raising.
        """
        from testing.fixtures.flux import is_flux_managed

        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr='error: the server doesn\'t have a resource type "helmrelease"',
        )

        result = is_flux_managed(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert result is False

    @pytest.mark.requirement("AC-2")
    def test_returns_false_for_nonexistent_release(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """is_flux_managed returns False when the named release doesn't exist.

        Flux CRD is installed but the specific HelmRelease resource is not found.
        kubectl returns non-zero, function returns False.
        """
        from testing.fixtures.flux import is_flux_managed

        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr="Error from server (NotFound): helmreleases.helm.toolkit.fluxcd.io "
            '"floe-platform" not found',
        )

        result = is_flux_managed(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert result is False

    @pytest.mark.requirement("AC-1")
    def test_uses_correct_kubectl_args(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """is_flux_managed runs kubectl with correct resource type and name.

        The command must be:
        kubectl get helmrelease {name} -n {namespace}
        """
        from testing.fixtures.flux import is_flux_managed

        mock_subprocess.return_value = _make_completed_process(returncode=0)

        is_flux_managed("my-release", "my-namespace")

        mock_subprocess.assert_called_once()
        actual_args: list[str] = mock_subprocess.call_args[0][0]

        assert actual_args[0] == "kubectl"
        assert "get" in actual_args
        assert "helmrelease" in actual_args
        assert "my-release" in actual_args
        # Namespace must be present
        ns_idx = actual_args.index("-n")
        assert actual_args[ns_idx + 1] == "my-namespace"

    @pytest.mark.requirement("AC-1")
    def test_return_type_is_bool(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """is_flux_managed returns a bool, not a truthy/falsy value.

        A sloppy implementation might return the CompletedProcess or
        its returncode. Must be exactly True or False.
        """
        from testing.fixtures.flux import is_flux_managed

        mock_subprocess.return_value = _make_completed_process(returncode=0)
        result_true = is_flux_managed(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)
        assert isinstance(result_true, bool), (
            f"is_flux_managed must return bool, got {type(result_true).__name__}"
        )

        mock_subprocess.return_value = _make_completed_process(returncode=1)
        result_false = is_flux_managed(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)
        assert isinstance(result_false, bool), (
            f"is_flux_managed must return bool, got {type(result_false).__name__}"
        )

    @pytest.mark.requirement("AC-1")
    def test_uses_check_false(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """is_flux_managed passes check=False to subprocess.run.

        Must not raise CalledProcessError on non-zero returncode; instead
        it interprets the returncode to decide True/False.
        """
        from testing.fixtures.flux import is_flux_managed

        mock_subprocess.return_value = _make_completed_process(returncode=1)

        # Must not raise
        is_flux_managed(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        _, kwargs = mock_subprocess.call_args
        assert kwargs.get("check") is False, (
            "is_flux_managed must pass check=False to subprocess.run"
        )


# ===========================================================================
# AC-1 / AC-2.3: suspend_helmrelease
# ===========================================================================


class TestSuspendHelmrelease:
    """Tests for suspend_helmrelease() function."""

    @pytest.mark.requirement("AC-1")
    def test_runs_flux_suspend_command(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """suspend_helmrelease runs 'flux suspend helmrelease {name} -n {ns}'.

        Verifies the exact subprocess command constructed includes
        the flux binary, suspend verb, resource type, name, and namespace.
        """
        from testing.fixtures.flux import suspend_helmrelease

        mock_shutil_which.return_value = "/usr/local/bin/flux"
        mock_subprocess.return_value = _make_completed_process(returncode=0)

        suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        mock_subprocess.assert_called_once()
        actual_args: list[str] = mock_subprocess.call_args[0][0]

        assert actual_args[0] == "flux"
        assert "suspend" in actual_args
        assert "helmrelease" in actual_args
        assert _DEFAULT_RELEASE_NAME in actual_args
        # Namespace must be present
        ns_idx = actual_args.index("-n")
        assert actual_args[ns_idx + 1] == _DEFAULT_NAMESPACE

    @pytest.mark.requirement("AC-1")
    def test_returns_true_on_success(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """suspend_helmrelease returns True when flux command succeeds."""
        from testing.fixtures.flux import suspend_helmrelease

        mock_shutil_which.return_value = "/usr/local/bin/flux"
        mock_subprocess.return_value = _make_completed_process(returncode=0)

        result = suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert result is True

    @pytest.mark.requirement("AC-2")
    def test_returns_false_when_flux_not_on_path(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """suspend_helmrelease returns False when flux CLI is not found.

        When shutil.which("flux") returns None, the function must not
        attempt to run flux and must return False.
        """
        from testing.fixtures.flux import suspend_helmrelease

        mock_shutil_which.return_value = None

        result = suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert result is False
        mock_subprocess.assert_not_called()

    @pytest.mark.requirement("AC-2")
    def test_logs_warning_when_flux_not_found(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """suspend_helmrelease logs warning when flux CLI is missing.

        The log message must indicate that flux was not found on PATH
        so operators can diagnose why suspension was skipped.
        """
        from testing.fixtures.flux import suspend_helmrelease

        mock_shutil_which.return_value = None

        with caplog.at_level(logging.WARNING):
            suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) >= 1, (
            "suspend_helmrelease must log a warning when flux CLI is not found"
        )
        # Message must mention flux so operators know what's missing
        combined = " ".join(warning_messages).lower()
        assert "flux" in combined, f"Warning message must mention 'flux'. Got: {warning_messages}"

    @pytest.mark.requirement("AC-7")
    def test_logs_warning_on_flux_command_failure(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """suspend_helmrelease logs warning when flux suspend returns non-zero.

        Per P56: best-effort cleanup must log failures. The warning must
        include the command, returncode, and stderr.
        """
        from testing.fixtures.flux import suspend_helmrelease

        mock_shutil_which.return_value = "/usr/local/bin/flux"
        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr="error: helmrelease not found",
        )

        with caplog.at_level(logging.WARNING):
            suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) >= 1, (
            "suspend_helmrelease must log a warning on flux command failure"
        )

    @pytest.mark.requirement("AC-7")
    def test_log_includes_command_and_returncode_on_failure(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Failure log includes command name and returncode per P56.

        A sloppy implementation might log a generic "failed" message
        without actionable details.
        """
        from testing.fixtures.flux import suspend_helmrelease

        mock_shutil_which.return_value = "/usr/local/bin/flux"
        mock_subprocess.return_value = _make_completed_process(
            returncode=42,
            stderr="something went wrong",
        )

        with caplog.at_level(logging.WARNING):
            suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        warning_text = " ".join(r.message for r in caplog.records if r.levelno >= logging.WARNING)
        assert "42" in warning_text, (
            f"Warning log must include returncode (42). Got: {warning_text}"
        )

    @pytest.mark.requirement("AC-7")
    def test_log_includes_stderr_on_failure(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Failure log includes stderr content per P56.

        The operator needs stderr to diagnose the failure without
        having to manually re-run the command.
        """
        from testing.fixtures.flux import suspend_helmrelease

        mock_shutil_which.return_value = "/usr/local/bin/flux"
        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr="unable to connect to cluster",
        )

        with caplog.at_level(logging.WARNING):
            suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        warning_text = " ".join(r.message for r in caplog.records if r.levelno >= logging.WARNING)
        assert "unable to connect to cluster" in warning_text, (
            f"Warning log must include stderr content. Got: {warning_text}"
        )

    @pytest.mark.requirement("AC-1")
    def test_returns_false_on_flux_command_failure(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """suspend_helmrelease returns False when flux command fails.

        A non-zero returncode from flux suspend means the suspension did
        not succeed. The function must return False, not True.
        """
        from testing.fixtures.flux import suspend_helmrelease

        mock_shutil_which.return_value = "/usr/local/bin/flux"
        mock_subprocess.return_value = _make_completed_process(returncode=1)

        result = suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert result is False


# ===========================================================================
# AC-1 / AC-7: resume_helmrelease
# ===========================================================================


class TestResumeHelmrelease:
    """Tests for resume_helmrelease() function."""

    @pytest.mark.requirement("AC-1")
    def test_runs_flux_resume_command(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """resume_helmrelease runs 'flux resume helmrelease {name} -n {ns}'.

        Verifies the exact subprocess command constructed includes
        the flux binary, resume verb, resource type, name, and namespace.
        """
        from testing.fixtures.flux import resume_helmrelease

        mock_subprocess.return_value = _make_completed_process(returncode=0)

        resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        mock_subprocess.assert_called_once()
        actual_args: list[str] = mock_subprocess.call_args[0][0]

        assert actual_args[0] == "flux"
        assert "resume" in actual_args
        assert "helmrelease" in actual_args
        assert _DEFAULT_RELEASE_NAME in actual_args
        ns_idx = actual_args.index("-n")
        assert actual_args[ns_idx + 1] == _DEFAULT_NAMESPACE

    @pytest.mark.requirement("AC-1")
    def test_uses_check_false(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """resume_helmrelease passes check=False to subprocess.run.

        The resume is a best-effort finalizer operation per AC-1.
        It must not raise CalledProcessError if flux resume fails.
        """
        from testing.fixtures.flux import resume_helmrelease

        mock_subprocess.return_value = _make_completed_process(returncode=1, stderr="error")

        # Must not raise even on failure
        resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        _, kwargs = mock_subprocess.call_args
        assert kwargs.get("check") is False, (
            "resume_helmrelease must use check=False for best-effort cleanup"
        )

    @pytest.mark.requirement("AC-1")
    def test_returns_true_on_success(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """resume_helmrelease returns True when flux resume succeeds."""
        from testing.fixtures.flux import resume_helmrelease

        mock_subprocess.return_value = _make_completed_process(returncode=0)

        result = resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert result is True

    @pytest.mark.requirement("AC-1")
    def test_returns_false_on_failure(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """resume_helmrelease returns False when flux resume fails."""
        from testing.fixtures.flux import resume_helmrelease

        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr="error",
        )

        result = resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert result is False

    @pytest.mark.requirement("AC-7")
    def test_logs_warning_on_failure(
        self,
        mock_subprocess: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """resume_helmrelease logs warning on non-zero returncode.

        Per P56: best-effort cleanup must log failures. No bare
        ``except Exception: pass``.
        """
        from testing.fixtures.flux import resume_helmrelease

        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr="connection refused",
        )

        with caplog.at_level(logging.WARNING):
            resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) >= 1, "resume_helmrelease must log a warning on failure"

    @pytest.mark.requirement("AC-7")
    def test_log_includes_returncode_on_failure(
        self,
        mock_subprocess: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Failure log includes returncode per P56."""
        from testing.fixtures.flux import resume_helmrelease

        mock_subprocess.return_value = _make_completed_process(
            returncode=7,
            stderr="connection timeout",
        )

        with caplog.at_level(logging.WARNING):
            resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        warning_text = " ".join(r.message for r in caplog.records if r.levelno >= logging.WARNING)
        assert "7" in warning_text, f"Warning log must include returncode (7). Got: {warning_text}"

    @pytest.mark.requirement("AC-7")
    def test_log_includes_stderr_on_failure(
        self,
        mock_subprocess: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Failure log includes stderr content per P56."""
        from testing.fixtures.flux import resume_helmrelease

        mock_subprocess.return_value = _make_completed_process(
            returncode=1,
            stderr="tls handshake timeout",
        )

        with caplog.at_level(logging.WARNING):
            resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        warning_text = " ".join(r.message for r in caplog.records if r.levelno >= logging.WARNING)
        assert "tls handshake timeout" in warning_text, (
            f"Warning log must include stderr. Got: {warning_text}"
        )

    @pytest.mark.requirement("AC-7")
    def test_does_not_raise_on_failure(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """resume_helmrelease must not raise exceptions on failure.

        As a best-effort finalizer, it must handle errors gracefully.
        It logs and returns False, never raises.
        """
        from testing.fixtures.flux import resume_helmrelease

        mock_subprocess.return_value = _make_completed_process(
            returncode=127,
            stderr="flux: command not found",
        )

        # Must not raise
        result = resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)
        assert result is False


# ===========================================================================
# AC-7: No bare except blocks (source inspection)
# ===========================================================================


class TestP56Compliance:
    """Verify the module follows P56: no bare except/pass blocks."""

    @pytest.mark.requirement("AC-7")
    def test_no_bare_except_pass(self) -> None:
        """Module source must not contain bare 'except Exception: pass'.

        P56 requires best-effort cleanup to log failures. A bare except
        that swallows errors silently violates this rule.
        """
        import testing.fixtures.flux as flux_mod

        source = inspect.getsource(flux_mod)

        # Check for bare except: pass patterns
        # Match both "except Exception:\n    pass" and "except:\n    pass"
        import re

        bare_except_pass = re.findall(r"except(?:\s+\w+)?:\s*\n\s*pass\b", source)
        assert len(bare_except_pass) == 0, (
            f"Module contains bare except/pass blocks (P56 violation): "
            f"{bare_except_pass}. All exception handlers must log the failure."
        )

    @pytest.mark.requirement("AC-7")
    def test_module_uses_logging(self) -> None:
        """Module must use the logging module for failure reporting.

        P56 requires logging.warning() for best-effort cleanup failures.
        """
        import testing.fixtures.flux as flux_mod

        source = inspect.getsource(flux_mod)

        assert "import logging" in source or "from logging" in source, (
            "Module must import logging for P56-compliant failure reporting."
        )
        assert "logger" in source, "Module must create a logger instance for P56-compliant logging."


# ===========================================================================
# AC-1 / AC-2: flux_suspended fixture
# ===========================================================================


class TestFluxSuspendedFixture:
    """Tests for the flux_suspended pytest fixture."""

    @pytest.mark.requirement("AC-1")
    def test_calls_suspend_when_flux_managed(
        self,
        mock_request: MagicMock,
    ) -> None:
        """flux_suspended calls suspend_helmrelease when release is Flux-managed.

        When is_flux_managed returns True and suspend succeeds, the fixture
        must invoke suspend_helmrelease with the release name and namespace.
        """
        from testing.fixtures.flux import flux_suspended

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=True) as mock_managed,
            patch(f"{_MODULE_PATH}.suspend_helmrelease", return_value=True) as mock_suspend,
            patch(f"{_MODULE_PATH}.resume_helmrelease", return_value=True),
            patch.dict("os.environ", {"FLOE_RELEASE_NAME": _DEFAULT_RELEASE_NAME}, clear=False),
        ):
            flux_suspended(mock_request)

            mock_managed.assert_called_once()
            mock_suspend.assert_called_once()
            # Verify suspend was called with the release name
            suspend_args = mock_suspend.call_args
            assert _DEFAULT_RELEASE_NAME in suspend_args[0] or (
                suspend_args[1].get("name") == _DEFAULT_RELEASE_NAME
                if suspend_args[1]
                else _DEFAULT_RELEASE_NAME == suspend_args[0][0]
            )

    @pytest.mark.requirement("AC-1")
    def test_registers_finalizer(
        self,
        mock_request: MagicMock,
    ) -> None:
        """flux_suspended registers a finalizer via request.addfinalizer.

        The finalizer must be registered so that resume_helmrelease is
        called during test teardown, even if the test fails.
        """
        from testing.fixtures.flux import flux_suspended

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=True),
            patch(f"{_MODULE_PATH}.suspend_helmrelease", return_value=True),
            patch(f"{_MODULE_PATH}.resume_helmrelease", return_value=True),
        ):
            flux_suspended(mock_request)

            mock_request.addfinalizer.assert_called_once()

    @pytest.mark.requirement("AC-1")
    def test_finalizer_calls_resume(
        self,
        mock_request: MagicMock,
    ) -> None:
        """The registered finalizer calls resume_helmrelease.

        After the fixture registers the finalizer, calling it must
        invoke resume_helmrelease to re-enable Flux reconciliation.
        """
        from testing.fixtures.flux import flux_suspended

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=True),
            patch(f"{_MODULE_PATH}.suspend_helmrelease", return_value=True),
            patch(f"{_MODULE_PATH}.resume_helmrelease", return_value=True) as mock_resume,
        ):
            flux_suspended(mock_request)

            # Extract the registered finalizer and call it
            finalizer_fn = mock_request.addfinalizer.call_args[0][0]
            assert callable(finalizer_fn), "Finalizer must be callable"

            finalizer_fn()

            mock_resume.assert_called_once()

    @pytest.mark.requirement("AC-1")
    def test_finalizer_resumes_correct_release(
        self,
        mock_request: MagicMock,
    ) -> None:
        """Finalizer calls resume_helmrelease with the correct release name and namespace.

        A sloppy implementation might hardcode the release name rather
        than using the same name that was suspended.
        """
        from testing.fixtures.flux import flux_suspended

        custom_release = "my-custom-release"

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=True),
            patch(f"{_MODULE_PATH}.suspend_helmrelease", return_value=True),
            patch(f"{_MODULE_PATH}.resume_helmrelease", return_value=True) as mock_resume,
            patch.dict("os.environ", {"FLOE_RELEASE_NAME": custom_release}, clear=False),
        ):
            flux_suspended(mock_request)

            finalizer_fn = mock_request.addfinalizer.call_args[0][0]
            finalizer_fn()

            # Verify resume was called with the same release name that was suspended
            resume_args = mock_resume.call_args[0]
            assert custom_release in resume_args, (
                f"Finalizer must resume the same release that was suspended. "
                f"Expected '{custom_release}' in args, got {resume_args}"
            )

    @pytest.mark.requirement("AC-2")
    def test_no_suspend_when_not_managed(
        self,
        mock_request: MagicMock,
    ) -> None:
        """flux_suspended does not call suspend when release is not Flux-managed.

        When is_flux_managed returns False (CRD not installed or release
        not found), the fixture must return without calling suspend.
        """
        from testing.fixtures.flux import flux_suspended

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=False),
            patch(f"{_MODULE_PATH}.suspend_helmrelease") as mock_suspend,
        ):
            flux_suspended(mock_request)

            mock_suspend.assert_not_called()

    @pytest.mark.requirement("AC-2")
    def test_no_finalizer_when_not_managed(
        self,
        mock_request: MagicMock,
    ) -> None:
        """flux_suspended does not register a finalizer when not managed.

        If the release is not Flux-managed, there is nothing to resume.
        Registering a finalizer that calls resume on a non-Flux release
        would produce confusing warning logs.
        """
        from testing.fixtures.flux import flux_suspended

        with patch(f"{_MODULE_PATH}.is_flux_managed", return_value=False):
            flux_suspended(mock_request)

            mock_request.addfinalizer.assert_not_called()

    @pytest.mark.requirement("AC-2")
    def test_no_suspend_when_flux_cli_missing(
        self,
        mock_request: MagicMock,
    ) -> None:
        """flux_suspended does not suspend when suspend_helmrelease returns False.

        When Flux CLI is not on PATH, suspend_helmrelease returns False.
        The fixture should handle this gracefully -- no finalizer needed
        since nothing was actually suspended.
        """
        from testing.fixtures.flux import flux_suspended

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=True),
            patch(f"{_MODULE_PATH}.suspend_helmrelease", return_value=False),
        ):
            flux_suspended(mock_request)

            # No finalizer because suspension was not actually performed
            mock_request.addfinalizer.assert_not_called()

    @pytest.mark.requirement("AC-1")
    def test_uses_env_var_release_name(
        self,
        mock_request: MagicMock,
    ) -> None:
        """flux_suspended reads FLOE_RELEASE_NAME from environment.

        The release name must come from os.environ.get("FLOE_RELEASE_NAME", "floe-platform").
        """
        from testing.fixtures.flux import flux_suspended

        custom_name = "custom-platform-release"

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=True) as mock_managed,
            patch(f"{_MODULE_PATH}.suspend_helmrelease", return_value=True),
            patch(f"{_MODULE_PATH}.resume_helmrelease", return_value=True),
            patch.dict("os.environ", {"FLOE_RELEASE_NAME": custom_name}, clear=False),
        ):
            flux_suspended(mock_request)

            # is_flux_managed must have been called with the custom release name
            managed_args = mock_managed.call_args[0]
            assert custom_name in managed_args, (
                f"flux_suspended must use FLOE_RELEASE_NAME env var. "
                f"Expected '{custom_name}' in is_flux_managed args, got {managed_args}"
            )

    @pytest.mark.requirement("AC-1")
    def test_default_release_name_when_env_not_set(
        self,
        mock_request: MagicMock,
    ) -> None:
        """flux_suspended defaults to 'floe-platform' when FLOE_RELEASE_NAME is not set.

        When the environment variable is absent, the fixture must use
        the default release name.
        """
        from testing.fixtures.flux import flux_suspended

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=True) as mock_managed,
            patch(f"{_MODULE_PATH}.suspend_helmrelease", return_value=True),
            patch(f"{_MODULE_PATH}.resume_helmrelease", return_value=True),
            patch.dict("os.environ", {}, clear=True),
        ):
            flux_suspended(mock_request)

            managed_args = mock_managed.call_args[0]
            assert "floe-platform" in managed_args, (
                f"flux_suspended must default to 'floe-platform' when "
                f"FLOE_RELEASE_NAME is not set. Got args: {managed_args}"
            )

    @pytest.mark.requirement("AC-1")
    def test_fixture_returns_none(
        self,
        mock_request: MagicMock,
    ) -> None:
        """flux_suspended returns None (it is a setup/teardown fixture).

        The fixture provides no value to tests; its purpose is the
        side effects (suspend + resume).
        """
        from testing.fixtures.flux import flux_suspended

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=True),
            patch(f"{_MODULE_PATH}.suspend_helmrelease", return_value=True),
            patch(f"{_MODULE_PATH}.resume_helmrelease", return_value=True),
        ):
            result = flux_suspended(mock_request)

            assert result is None, (
                f"flux_suspended must return None, got {type(result).__name__}: {result}"
            )


# ===========================================================================
# Mutation resistance: Hardcoded return bypass tests
# ===========================================================================


class TestMutationResistance:
    """Tests that detect hardcoded return values and partial implementations.

    These tests ensure that a sloppy implementation cannot pass by:
    - Always returning True from is_flux_managed
    - Always returning False from is_flux_managed
    - Never actually calling subprocess.run
    - Registering a finalizer that does nothing
    """

    @pytest.mark.requirement("AC-1")
    @pytest.mark.requirement("AC-2")
    def test_is_flux_managed_behavior_depends_on_returncode(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """is_flux_managed must return different values for different returncodes.

        Calling it twice with returncode=0 then returncode=1 must produce
        True then False. A hardcoded implementation fails this test.
        """
        from testing.fixtures.flux import is_flux_managed

        mock_subprocess.return_value = _make_completed_process(returncode=0)
        result_success = is_flux_managed(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        mock_subprocess.return_value = _make_completed_process(returncode=1)
        result_failure = is_flux_managed(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert result_success is True, "Must return True for returncode=0"
        assert result_failure is False, "Must return False for returncode!=0"
        assert result_success != result_failure, (
            "is_flux_managed must produce different results for different returncodes"
        )

    @pytest.mark.requirement("AC-1")
    def test_suspend_actually_calls_subprocess(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """suspend_helmrelease must call subprocess.run, not just return True.

        A partial implementation that checks shutil.which but skips the
        actual subprocess call would pass other tests but fail this one.
        """
        from testing.fixtures.flux import suspend_helmrelease

        mock_shutil_which.return_value = "/usr/local/bin/flux"
        mock_subprocess.return_value = _make_completed_process(returncode=0)

        suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert mock_subprocess.call_count == 1, (
            f"suspend_helmrelease must call subprocess.run exactly once, "
            f"called {mock_subprocess.call_count} times"
        )

    @pytest.mark.requirement("AC-1")
    def test_resume_actually_calls_subprocess(
        self,
        mock_subprocess: MagicMock,
    ) -> None:
        """resume_helmrelease must call subprocess.run, not just return True.

        A partial implementation that always returns True without actually
        running the resume command would leave Flux suspended.
        """
        from testing.fixtures.flux import resume_helmrelease

        mock_subprocess.return_value = _make_completed_process(returncode=0)

        resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)

        assert mock_subprocess.call_count == 1, (
            f"resume_helmrelease must call subprocess.run exactly once, "
            f"called {mock_subprocess.call_count} times"
        )

    @pytest.mark.requirement("AC-1")
    def test_suspend_and_resume_use_different_verbs(
        self,
        mock_subprocess: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """suspend uses 'suspend' verb, resume uses 'resume' verb.

        A copy-paste implementation might use the same verb for both.
        """
        from testing.fixtures.flux import resume_helmrelease, suspend_helmrelease

        mock_shutil_which.return_value = "/usr/local/bin/flux"
        mock_subprocess.return_value = _make_completed_process(returncode=0)

        suspend_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)
        suspend_args: list[str] = mock_subprocess.call_args[0][0]

        mock_subprocess.reset_mock()
        resume_helmrelease(_DEFAULT_RELEASE_NAME, _DEFAULT_NAMESPACE)
        resume_args: list[str] = mock_subprocess.call_args[0][0]

        assert "suspend" in suspend_args, "suspend_helmrelease must use 'suspend' verb"
        assert "resume" in resume_args, "resume_helmrelease must use 'resume' verb"
        assert "resume" not in suspend_args, "suspend_helmrelease must NOT use 'resume' verb"
        assert "suspend" not in resume_args, "resume_helmrelease must NOT use 'suspend' verb"

    @pytest.mark.requirement("AC-1")
    def test_fixture_suspend_and_resume_are_paired(
        self,
        mock_request: MagicMock,
    ) -> None:
        """Fixture must suspend during setup and resume during teardown.

        A broken implementation might suspend but not register a
        finalizer, or register a finalizer that calls suspend instead
        of resume.
        """
        from testing.fixtures.flux import flux_suspended

        with (
            patch(f"{_MODULE_PATH}.is_flux_managed", return_value=True),
            patch(f"{_MODULE_PATH}.suspend_helmrelease", return_value=True) as mock_suspend,
            patch(f"{_MODULE_PATH}.resume_helmrelease", return_value=True) as mock_resume,
        ):
            flux_suspended(mock_request)

            # Suspend was called during setup
            mock_suspend.assert_called_once()

            # Resume was NOT called during setup
            mock_resume.assert_not_called()

            # Call the finalizer
            finalizer_fn = mock_request.addfinalizer.call_args[0][0]
            finalizer_fn()

            # NOW resume should be called
            mock_resume.assert_called_once()
