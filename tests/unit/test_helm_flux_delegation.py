"""Unit tests: recover_stuck_helm_release delegates to Flux (AC-6).

Tests verify that ``testing/fixtures/helm.py`` ``recover_stuck_helm_release()``
checks if a release is Flux-managed and attempts ``flux reconcile`` before
falling through to Helm rollback.

Two categories:

- **Structural**: Verify the function body contains Flux-related strings and
  that ``helm.py`` imports ``shutil``.  These guard against regressions where
  the Flux delegation code is accidentally removed.

- **Behavioral**: Mock ``subprocess.run`` and ``shutil.which`` at module level
  to verify the control flow for all delegation scenarios.

Acceptance Criteria Covered:
    AC-6: recover_stuck_helm_release delegates to Flux when available
    AC-7: All Flux subprocess calls log on failure (P56 compliance)

Test Type Rationale:
    Unit tests -- subprocess.run and shutil.which are external system
    boundaries; mocking them is correct per TESTING.md boundary classification.
"""

from __future__ import annotations

import inspect
import json
import logging
import subprocess
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from testing.fixtures.helm import recover_stuck_helm_release

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODULE_PATH = "testing.fixtures.helm"
_RELEASE = "floe-platform"
_NAMESPACE = "floe-test"

# JSON payloads for mock helm commands
_STUCK_STATUS_JSON = json.dumps(
    {
        "info": {"status": "pending-upgrade"},
        "version": 3,
    }
)

_DEPLOYED_STATUS_JSON = json.dumps(
    {
        "info": {"status": "deployed"},
        "version": 2,
    }
)

_HISTORY_JSON = json.dumps(
    [
        {"revision": 1, "status": "superseded"},
        {"revision": 2, "status": "deployed"},
        {"revision": 3, "status": "pending-upgrade"},
    ]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed(
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


def _make_helm_runner(
    side_effect: list[subprocess.CompletedProcess[str]] | None = None,
) -> MagicMock:
    """Create a mock helm_runner callable.

    Args:
        side_effect: List of CompletedProcess results to return in order.

    Returns:
        MagicMock configured as a helm_runner.
    """
    runner = MagicMock()
    if side_effect is not None:
        runner.side_effect = side_effect
    return runner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_subprocess_run() -> Generator[MagicMock, None, None]:
    """Patch subprocess.run in the helm module.

    Used for kubectl and flux commands (NOT helm commands, which go through
    helm_runner).

    Yields:
        The MagicMock replacing subprocess.run in testing.fixtures.helm.
    """
    with patch(f"{_MODULE_PATH}.subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture()
def mock_shutil_which() -> Generator[MagicMock, None, None]:
    """Patch shutil.which in the helm module.

    Yields:
        The MagicMock replacing shutil.which in testing.fixtures.helm.
    """
    with patch(f"{_MODULE_PATH}.shutil.which") as mock_which:
        yield mock_which


# ===========================================================================
# AC-6 STRUCTURAL: Function body contains Flux delegation code
# ===========================================================================


class TestRecoverStuckHelmReleaseFluxStructural:
    """Structural tests verifying Flux delegation code exists in helm.py."""

    @pytest.mark.requirement("AC-6")
    def test_function_body_contains_helmrelease(self) -> None:
        """recover_stuck_helm_release body references 'helmrelease'.

        The function must check ``kubectl get helmrelease`` to detect
        Flux-managed releases.  Without this string, the Flux check
        is missing.
        """
        source = inspect.getsource(recover_stuck_helm_release)
        assert "helmrelease" in source.lower(), (
            "recover_stuck_helm_release function body must contain "
            "'helmrelease' (case-insensitive) for the kubectl check. "
            "Found no reference to helmrelease."
        )

    @pytest.mark.requirement("AC-6")
    def test_function_body_contains_flux(self) -> None:
        """recover_stuck_helm_release body references 'flux'.

        The function must call the flux CLI. Without this string,
        flux delegation is missing.
        """
        source = inspect.getsource(recover_stuck_helm_release)
        assert "flux" in source.lower(), (
            "recover_stuck_helm_release function body must contain 'flux' "
            "for CLI delegation. Found no reference to flux."
        )

    @pytest.mark.requirement("AC-6")
    def test_function_body_contains_reconcile(self) -> None:
        """recover_stuck_helm_release body references 'reconcile'.

        The function must run ``flux reconcile helmrelease``.  Without
        'reconcile', the delegation is incomplete.
        """
        source = inspect.getsource(recover_stuck_helm_release)
        assert "reconcile" in source.lower(), (
            "recover_stuck_helm_release function body must contain "
            "'reconcile' for the flux reconcile command. "
            "Found no reference to reconcile."
        )

    @pytest.mark.requirement("AC-6")
    def test_helm_module_imports_shutil(self) -> None:
        """testing/fixtures/helm.py imports shutil.

        ``shutil.which('flux')`` is needed to check CLI availability.
        Without the import, the check cannot work.
        """
        import testing.fixtures.helm as helm_mod

        source = inspect.getsource(helm_mod)
        assert "import shutil" in source or "from shutil" in source, (
            "testing/fixtures/helm.py must import shutil "
            "(for shutil.which('flux') check). No shutil import found."
        )


# ===========================================================================
# AC-6 BEHAVIORAL: Flux-managed + flux on PATH + reconcile SUCCEEDS
# ===========================================================================


class TestFluxReconcileSuccess:
    """When release is Flux-managed AND flux CLI is available AND reconcile
    succeeds, recover_stuck_helm_release should return True without performing
    a Helm rollback."""

    @pytest.mark.requirement("AC-6")
    def test_returns_true_on_successful_flux_reconcile(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """Successful flux reconcile returns True without rollback.

        Flow: helm status (stuck) -> kubectl get helmrelease (exists) ->
        shutil.which (found) -> flux reconcile (success) -> return True.
        No helm rollback should be called.
        """
        # helm_runner: status returns stuck, history should NOT be called
        helm_runner = _make_helm_runner(
            side_effect=[
                # helm status -> stuck
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
            ]
        )

        # subprocess.run: kubectl get helmrelease -> found, flux reconcile -> success
        mock_subprocess_run.side_effect = [
            _make_completed(returncode=0),  # kubectl get helmrelease
            _make_completed(returncode=0),  # flux reconcile
        ]

        # shutil.which("flux") -> found
        mock_shutil_which.return_value = "/usr/local/bin/flux"

        result = recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        assert result is True, (
            "recover_stuck_helm_release should return True when flux reconcile succeeds. Got False."
        )

    @pytest.mark.requirement("AC-6")
    def test_no_helm_rollback_when_flux_reconcile_succeeds(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """No helm rollback/history commands when flux reconcile succeeds.

        When flux reconcile works, the function should return immediately
        without consulting helm history or performing a rollback.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
            ]
        )

        mock_subprocess_run.side_effect = [
            _make_completed(returncode=0),  # kubectl get helmrelease
            _make_completed(returncode=0),  # flux reconcile
        ]
        mock_shutil_which.return_value = "/usr/local/bin/flux"

        recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        # helm_runner should only be called once (for status), never for
        # history or rollback
        assert helm_runner.call_count == 1, (
            f"helm_runner was called {helm_runner.call_count} times. "
            "Expected exactly 1 (status only). Rollback should not happen "
            "when flux reconcile succeeds."
        )

        # Verify the only helm call was status
        status_call_args = helm_runner.call_args_list[0]
        assert "status" in status_call_args[0][0], (
            f"The only helm_runner call should be 'status'. Got: {status_call_args}"
        )

    @pytest.mark.requirement("AC-6")
    def test_flux_reconcile_command_is_correct(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """flux reconcile command includes 'helmrelease', release name, and namespace.

        Verifies the exact command structure: ``flux reconcile helmrelease
        {name} -n {namespace}``.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
            ]
        )

        mock_subprocess_run.side_effect = [
            _make_completed(returncode=0),  # kubectl get helmrelease
            _make_completed(returncode=0),  # flux reconcile
        ]
        mock_shutil_which.return_value = "/usr/local/bin/flux"

        recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        # Find the flux reconcile call among subprocess.run calls
        flux_calls = [
            c for c in mock_subprocess_run.call_args_list if any("flux" in str(arg) for arg in c[0])
        ]
        assert len(flux_calls) >= 1, (
            f"No subprocess.run call with 'flux' found. Calls: {mock_subprocess_run.call_args_list}"
        )

        # Verify the reconcile command structure
        reconcile_call = flux_calls[-1]
        cmd_args = reconcile_call[0][0]  # First positional arg
        assert "flux" in cmd_args, f"Expected 'flux' in command: {cmd_args}"
        assert "reconcile" in cmd_args, f"Expected 'reconcile' in command: {cmd_args}"
        assert "helmrelease" in cmd_args, f"Expected 'helmrelease' in command: {cmd_args}"
        assert _RELEASE in cmd_args, f"Expected '{_RELEASE}' in command: {cmd_args}"
        assert _NAMESPACE in cmd_args, f"Expected '{_NAMESPACE}' in command: {cmd_args}"


# ===========================================================================
# AC-6 BEHAVIORAL: Flux-managed + flux on PATH + reconcile FAILS
# ===========================================================================


class TestFluxReconcileFailure:
    """When flux reconcile fails, recover_stuck_helm_release should fall
    through to existing Helm rollback logic."""

    @pytest.mark.requirement("AC-6")
    def test_falls_through_to_rollback_on_reconcile_failure(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """Failed flux reconcile falls through to existing rollback logic.

        Flow: helm status (stuck) -> kubectl get helmrelease (exists) ->
        shutil.which (found) -> flux reconcile (FAILS) -> helm history ->
        helm rollback.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                # helm status -> stuck
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                # helm history -> find last deployed revision
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                # helm rollback -> success
                _make_completed(returncode=0),
            ]
        )

        mock_subprocess_run.side_effect = [
            _make_completed(returncode=0),  # kubectl get helmrelease
            _make_completed(returncode=1, stderr="reconcile failed"),  # flux reconcile FAILS
        ]
        mock_shutil_which.return_value = "/usr/local/bin/flux"

        result = recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        assert result is True, (
            "recover_stuck_helm_release should return True after falling "
            "through to successful Helm rollback when flux reconcile fails."
        )

    @pytest.mark.requirement("AC-6")
    def test_helm_rollback_invoked_after_reconcile_failure(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """Helm history and rollback are called when flux reconcile fails.

        The function must fall through to the existing rollback path, which
        queries helm history to find the last deployed revision, then
        performs a rollback.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                _make_completed(returncode=0),  # rollback success
            ]
        )

        mock_subprocess_run.side_effect = [
            _make_completed(returncode=0),  # kubectl get helmrelease
            _make_completed(returncode=1, stderr="reconcile failed"),
        ]
        mock_shutil_which.return_value = "/usr/local/bin/flux"

        recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        # helm_runner should be called 3 times: status, history, rollback
        assert helm_runner.call_count == 3, (
            f"helm_runner was called {helm_runner.call_count} times. "
            "Expected 3 (status, history, rollback) when flux reconcile fails."
        )

        # Verify rollback was in the calls
        rollback_calls = [c for c in helm_runner.call_args_list if "rollback" in str(c)]
        assert len(rollback_calls) == 1, (
            f"Expected exactly 1 rollback call, found {len(rollback_calls)}. "
            f"All calls: {helm_runner.call_args_list}"
        )


# ===========================================================================
# AC-6 BEHAVIORAL: Release NOT Flux-managed
# ===========================================================================


class TestNotFluxManaged:
    """When release is NOT Flux-managed, no flux commands should be issued."""

    @pytest.mark.requirement("AC-6")
    def test_no_flux_commands_when_not_flux_managed(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """No flux commands when kubectl get helmrelease returns non-zero.

        When Flux does not manage the release, the function should behave
        exactly as before the Flux delegation was added: go straight to
        helm history + rollback.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                _make_completed(returncode=0),  # rollback
            ]
        )

        # kubectl get helmrelease -> NOT found (not Flux-managed)
        mock_subprocess_run.return_value = _make_completed(returncode=1)

        recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        # Verify NO flux reconcile call was made
        for c in mock_subprocess_run.call_args_list:
            cmd = c[0][0] if c[0] else []
            assert "reconcile" not in str(cmd), (
                f"flux reconcile should NOT be called when release is not "
                f"Flux-managed. Found call: {cmd}"
            )

    @pytest.mark.requirement("AC-6")
    def test_shutil_which_not_called_when_not_flux_managed(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """shutil.which should not be called if release is not Flux-managed.

        Checking for the flux CLI is unnecessary if the release is not
        managed by Flux.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                _make_completed(returncode=0),  # rollback
            ]
        )

        mock_subprocess_run.return_value = _make_completed(returncode=1)

        recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        mock_shutil_which.assert_not_called()

    @pytest.mark.requirement("AC-6")
    def test_falls_through_to_rollback_when_not_flux_managed(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """When not Flux-managed, existing rollback path executes.

        The function should query helm history and perform rollback
        just as it did before the Flux delegation was added.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                _make_completed(returncode=0),  # rollback
            ]
        )

        mock_subprocess_run.return_value = _make_completed(returncode=1)

        result = recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        assert result is True, (
            "recover_stuck_helm_release should return True after successful "
            "Helm rollback when release is not Flux-managed."
        )

        # helm_runner: status, history, rollback
        assert helm_runner.call_count == 3, (
            f"Expected 3 helm_runner calls (status, history, rollback) when "
            f"not Flux-managed. Got {helm_runner.call_count}."
        )


# ===========================================================================
# AC-6 BEHAVIORAL: Flux CLI NOT on PATH
# ===========================================================================


class TestFluxCLINotOnPath:
    """When flux CLI is not on PATH, should skip flux reconcile and fall
    through to existing logic."""

    @pytest.mark.requirement("AC-6")
    def test_skips_reconcile_when_flux_cli_missing(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """No flux reconcile when shutil.which('flux') returns None.

        The release IS Flux-managed (kubectl get helmrelease succeeds) but
        the flux CLI is not installed. Should fall through to rollback.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                _make_completed(returncode=0),  # rollback
            ]
        )

        # kubectl get helmrelease -> found (Flux-managed)
        mock_subprocess_run.return_value = _make_completed(returncode=0)

        # flux CLI NOT on PATH
        mock_shutil_which.return_value = None

        result = recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        assert result is True, (
            "recover_stuck_helm_release should return True after Helm "
            "rollback when flux CLI is missing."
        )

    @pytest.mark.requirement("AC-6")
    def test_no_flux_reconcile_call_when_cli_missing(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """subprocess.run should only be called for kubectl, not flux, when
        flux CLI is missing."""
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                _make_completed(returncode=0),
            ]
        )

        mock_subprocess_run.return_value = _make_completed(returncode=0)
        mock_shutil_which.return_value = None

        recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        # subprocess.run should be called for kubectl only, never with "flux reconcile"
        for c in mock_subprocess_run.call_args_list:
            cmd = c[0][0] if c[0] else []
            if "reconcile" in str(cmd):
                pytest.fail(
                    f"flux reconcile should NOT be called when flux CLI "
                    f"is not on PATH. Found call: {cmd}"
                )

    @pytest.mark.requirement("AC-6")
    def test_falls_through_to_helm_rollback_when_cli_missing(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """Helm rollback is performed when flux CLI is missing.

        The function must fall through to existing rollback path when
        flux CLI is not available, even though the release is Flux-managed.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                _make_completed(returncode=0),
            ]
        )

        mock_subprocess_run.return_value = _make_completed(returncode=0)
        mock_shutil_which.return_value = None

        recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        # Must have called history + rollback via helm_runner
        assert helm_runner.call_count == 3, (
            f"Expected 3 helm_runner calls when flux CLI missing. Got {helm_runner.call_count}."
        )


# ===========================================================================
# AC-7 / P56: Flux reconcile failure logs a warning
# ===========================================================================


class TestFluxReconcileFailureLogging:
    """P56 compliance: flux reconcile failure must log a warning."""

    @pytest.mark.requirement("AC-7")
    def test_logs_warning_on_reconcile_failure(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A warning is logged when flux reconcile returns non-zero.

        P56 requires that best-effort cleanup operations log on failure.
        The log must include the command and returncode for debuggability.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                _make_completed(returncode=0),
            ]
        )

        mock_subprocess_run.side_effect = [
            _make_completed(returncode=0),  # kubectl get helmrelease
            _make_completed(
                returncode=1,
                stderr="error: helmrelease not ready",
            ),  # flux reconcile FAILS
        ]
        mock_shutil_which.return_value = "/usr/local/bin/flux"

        with caplog.at_level(logging.WARNING):
            recover_stuck_helm_release(
                _RELEASE,
                _NAMESPACE,
                helm_runner=helm_runner,
            )

        # Check that a warning was logged about flux reconcile failure
        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) > 0, (
            "No warning logged when flux reconcile failed. "
            "P56 requires logging on failed best-effort operations."
        )

        # The warning should mention flux/reconcile
        combined = " ".join(warning_messages).lower()
        assert "reconcile" in combined or "flux" in combined, (
            f"Warning message should reference flux or reconcile. Got: {warning_messages}"
        )

    @pytest.mark.requirement("AC-7")
    def test_log_includes_returncode(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning log includes the returncode for debuggability.

        Per P56, the log must contain enough information to diagnose the
        failure, including the exit code.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
                _make_completed(returncode=0, stdout=_HISTORY_JSON),
                _make_completed(returncode=0),
            ]
        )

        mock_subprocess_run.side_effect = [
            _make_completed(returncode=0),
            _make_completed(returncode=42, stderr="custom error"),
        ]
        mock_shutil_which.return_value = "/usr/local/bin/flux"

        with caplog.at_level(logging.WARNING):
            recover_stuck_helm_release(
                _RELEASE,
                _NAMESPACE,
                helm_runner=helm_runner,
            )

        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        combined = " ".join(warning_messages)
        assert "42" in combined, (
            f"Warning log should include returncode 42. Got: {warning_messages}"
        )


# ===========================================================================
# AC-6 BEHAVIORAL: Release not stuck (healthy) -- no Flux check
# ===========================================================================


class TestHealthyReleaseNoFluxCheck:
    """When the release is healthy (deployed), no Flux check should occur."""

    @pytest.mark.requirement("AC-6")
    def test_no_flux_check_when_release_healthy(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """No kubectl or flux commands when release is in 'deployed' state.

        Flux delegation is only relevant when the release is stuck.
        A healthy release should short-circuit before any Flux checks.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_DEPLOYED_STATUS_JSON),
            ]
        )

        result = recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        assert result is False, (
            "recover_stuck_helm_release should return False for healthy release."
        )
        mock_subprocess_run.assert_not_called()
        mock_shutil_which.assert_not_called()


# ===========================================================================
# AC-6 BEHAVIORAL: Flux uses subprocess.run, NOT helm_runner
# ===========================================================================


class TestFluxUsesSubprocessNotHelmRunner:
    """Flux commands (kubectl, flux) must use subprocess.run directly,
    not the helm_runner parameter."""

    @pytest.mark.requirement("AC-6")
    def test_kubectl_helmrelease_check_uses_subprocess(
        self,
        mock_subprocess_run: MagicMock,
        mock_shutil_which: MagicMock,
    ) -> None:
        """kubectl get helmrelease goes through subprocess.run, not helm_runner.

        helm_runner is only for helm commands. kubectl and flux commands
        must use subprocess.run directly.
        """
        helm_runner = _make_helm_runner(
            side_effect=[
                _make_completed(returncode=0, stdout=_STUCK_STATUS_JSON),
            ]
        )

        mock_subprocess_run.side_effect = [
            _make_completed(returncode=0),  # kubectl get helmrelease
            _make_completed(returncode=0),  # flux reconcile
        ]
        mock_shutil_which.return_value = "/usr/local/bin/flux"

        recover_stuck_helm_release(
            _RELEASE,
            _NAMESPACE,
            helm_runner=helm_runner,
        )

        # subprocess.run must have been called (for kubectl/flux)
        assert mock_subprocess_run.call_count >= 1, (
            "subprocess.run should be called for kubectl/flux commands. Got 0 calls."
        )

        # The kubectl call should be among subprocess.run calls
        kubectl_calls = [c for c in mock_subprocess_run.call_args_list if "kubectl" in str(c)]
        assert len(kubectl_calls) >= 1, (
            "kubectl get helmrelease should use subprocess.run, not "
            f"helm_runner. subprocess.run calls: {mock_subprocess_run.call_args_list}"
        )
