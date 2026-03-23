"""Unit tests for Helm release recovery utilities.

Tests the shared ``recover_stuck_helm_release`` function with mocked
``run_helm`` to exercise all stuck states, rollback scenarios, and
error handling.

Requirement: AC-2.9 (Helm upgrade reliability)
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from testing.fixtures.helm import (
    STUCK_STATES,
    parse_helm_status,
    recover_stuck_helm_release,
)


def _make_completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Create a subprocess.CompletedProcess for testing."""
    return subprocess.CompletedProcess(
        args=["helm"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _make_status_json(
    status: str = "deployed",
    version: int | str = 3,
) -> str:
    """Create JSON output matching ``helm status -o json``."""
    return json.dumps({"info": {"status": status}, "version": version})


def _make_history_json(revisions: list[tuple[int, str]]) -> str:
    """Create JSON output matching ``helm history -o json``.

    Args:
        revisions: List of (revision, status) tuples.
    """
    entries = [{"revision": rev, "status": status} for rev, status in revisions]
    return json.dumps(entries)


class TestParseHelmStatus:
    """Tests for parse_helm_status."""

    @pytest.mark.requirement("AC-2.9")
    def test_valid_json(self) -> None:
        """Parse valid JSON from helm status."""
        result = parse_helm_status('{"info": {"status": "deployed"}, "version": 3}')
        assert result["info"]["status"] == "deployed"
        assert result["version"] == 3

    @pytest.mark.requirement("AC-2.9")
    def test_empty_string_raises_value_error(self) -> None:
        """Empty stdout raises ValueError with descriptive message."""
        with pytest.raises(ValueError, match="empty output"):
            parse_helm_status("")

    @pytest.mark.requirement("AC-2.9")
    def test_whitespace_only_raises_value_error(self) -> None:
        """Whitespace-only stdout raises ValueError."""
        with pytest.raises(ValueError, match="empty output"):
            parse_helm_status("   \n  ")

    @pytest.mark.requirement("AC-2.9")
    def test_invalid_json_raises_value_error(self) -> None:
        """Invalid JSON raises ValueError with preview of output."""
        with pytest.raises(ValueError, match="invalid JSON"):
            parse_helm_status("not json at all{")

    @pytest.mark.requirement("AC-2.9")
    def test_partial_json_raises_value_error(self) -> None:
        """Truncated JSON raises ValueError."""
        with pytest.raises(ValueError, match="invalid JSON"):
            parse_helm_status('{"info": {"status": "deploy')


class TestRecoverStuckHelmRelease:
    """Tests for recover_stuck_helm_release with mocked helm runner."""

    @pytest.mark.requirement("AC-2.9")
    def test_healthy_release_no_recovery(self) -> None:
        """Healthy release (deployed) returns False, no rollback called."""
        mock_runner = MagicMock()
        mock_runner.return_value = _make_completed_process(
            stdout=_make_status_json("deployed", 3),
        )

        result = recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            helm_runner=mock_runner,
        )

        assert result is False
        # Only status call, no rollback
        mock_runner.assert_called_once_with(
            ["status", "floe-platform", "-n", "floe-test", "-o", "json"],
        )

    @pytest.mark.requirement("AC-2.9")
    def test_release_not_found_returns_false(self) -> None:
        """Non-existent release (returncode != 0) returns False."""
        mock_runner = MagicMock()
        mock_runner.return_value = _make_completed_process(
            returncode=1,
            stderr="Error: release not found",
        )

        result = recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            helm_runner=mock_runner,
        )

        assert result is False
        mock_runner.assert_called_once()

    @pytest.mark.requirement("AC-2.9")
    @pytest.mark.parametrize("stuck_state", list(STUCK_STATES))
    def test_recovery_for_each_stuck_state(self, stuck_state: str) -> None:
        """Each stuck state triggers rollback to last deployed revision from history."""
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            # First call: helm status returns stuck state at revision 5
            _make_completed_process(
                stdout=_make_status_json(stuck_state, 5),
            ),
            # Second call: helm history shows revision 4 was deployed
            _make_completed_process(
                stdout=_make_history_json(
                    [
                        (4, "deployed"),
                        (5, stuck_state),
                    ]
                ),
            ),
            # Third call: helm rollback succeeds
            _make_completed_process(returncode=0),
        ]

        result = recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            helm_runner=mock_runner,
        )

        assert result is True
        assert mock_runner.call_count == 3

        # Verify rollback called with correct revision (last deployed = 4)
        rollback_call = mock_runner.call_args_list[2]
        rollback_args = rollback_call[0][0]
        assert "rollback" in rollback_args
        assert "4" in rollback_args
        assert "--wait" in rollback_args

    @pytest.mark.requirement("AC-2.9")
    def test_rollback_failure_raises_runtime_error(self) -> None:
        """Failed rollback raises RuntimeError with diagnostic info."""
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _make_completed_process(
                stdout=_make_status_json("pending-upgrade", 3),
            ),
            # helm history — shows revision 2 deployed
            _make_completed_process(
                stdout=_make_history_json(
                    [
                        (2, "deployed"),
                        (3, "pending-upgrade"),
                    ]
                ),
            ),
            _make_completed_process(
                returncode=1,
                stderr="Error: rollback timed out",
            ),
        ]

        with pytest.raises(RuntimeError, match="Helm rollback failed"):
            recover_stuck_helm_release(
                "floe-platform",
                "floe-test",
                helm_runner=mock_runner,
            )

    @pytest.mark.requirement("AC-2.9")
    def test_malformed_json_raises_value_error(self) -> None:
        """Malformed JSON from helm status raises ValueError."""
        mock_runner = MagicMock()
        mock_runner.return_value = _make_completed_process(
            stdout="partial output{not json",
        )

        with pytest.raises(ValueError, match="invalid JSON"):
            recover_stuck_helm_release(
                "floe-platform",
                "floe-test",
                helm_runner=mock_runner,
            )

    @pytest.mark.requirement("AC-2.9")
    def test_empty_stdout_raises_value_error(self) -> None:
        """Empty stdout from helm status raises ValueError."""
        mock_runner = MagicMock()
        mock_runner.return_value = _make_completed_process(stdout="")

        with pytest.raises(ValueError, match="empty output"):
            recover_stuck_helm_release(
                "floe-platform",
                "floe-test",
                helm_runner=mock_runner,
            )

    @pytest.mark.requirement("AC-2.9")
    def test_missing_info_key_treated_as_healthy(self) -> None:
        """Missing 'info' key in JSON treated as empty status (healthy)."""
        mock_runner = MagicMock()
        mock_runner.return_value = _make_completed_process(
            stdout=json.dumps({"version": 1}),
        )

        result = recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            helm_runner=mock_runner,
        )

        assert result is False

    @pytest.mark.requirement("AC-2.9")
    def test_revision_1_rollback_targets_revision_1(self) -> None:
        """At revision 1 with history showing it was once deployed, rollback targets 1."""
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _make_completed_process(
                stdout=_make_status_json("failed", 1),
            ),
            # helm history — revision 1 was deployed before it failed
            _make_completed_process(
                stdout=_make_history_json(
                    [
                        (1, "deployed"),
                    ]
                ),
            ),
            _make_completed_process(returncode=0),
        ]

        result = recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            helm_runner=mock_runner,
        )

        assert result is True
        rollback_call = mock_runner.call_args_list[2]
        rollback_args = rollback_call[0][0]
        assert "1" in rollback_args  # Rollback to revision 1

    @pytest.mark.requirement("AC-2.9")
    def test_version_as_string_raises_value_error(self) -> None:
        """Non-integer 'version' field raises ValueError."""
        mock_runner = MagicMock()
        mock_runner.return_value = _make_completed_process(
            stdout=json.dumps({"info": {"status": "failed"}, "version": "3"}),
        )

        with pytest.raises(ValueError, match="Unexpected 'version' type"):
            recover_stuck_helm_release(
                "floe-platform",
                "floe-test",
                helm_runner=mock_runner,
            )

    @pytest.mark.requirement("AC-2.9")
    def test_custom_rollback_timeout(self) -> None:
        """Custom rollback_timeout is passed to helm rollback."""
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _make_completed_process(
                stdout=_make_status_json("pending-install", 2),
            ),
            # helm history — revision 1 was deployed
            _make_completed_process(
                stdout=_make_history_json(
                    [
                        (1, "deployed"),
                        (2, "pending-install"),
                    ]
                ),
            ),
            _make_completed_process(returncode=0),
        ]

        recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            rollback_timeout="10m",
            helm_runner=mock_runner,
        )

        rollback_call = mock_runner.call_args_list[2]
        rollback_args = rollback_call[0][0]
        assert "10m" in rollback_args

    @pytest.mark.requirement("AC-2.9")
    def test_superseded_state_not_stuck(self) -> None:
        """Superseded state is not a stuck state — no recovery."""
        mock_runner = MagicMock()
        mock_runner.return_value = _make_completed_process(
            stdout=_make_status_json("superseded", 2),
        )

        result = recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            helm_runner=mock_runner,
        )

        assert result is False
        mock_runner.assert_called_once()

    # ── AC-4: History-scanning recovery tests ──────────────────────────

    @pytest.mark.requirement("AC-2.9")
    def test_recovery_scans_history_for_last_deployed(self) -> None:
        """When multiple failed revisions have accumulated, recovery rolls
        back to the most recent *deployed* revision found via
        ``helm history``, not simply current_revision - 1.

        Scenario: rev 20=deployed, 21=failed, 22=failed, 23=failed.
        Expected rollback target: revision 20.
        Expected calls: status, history, rollback (3 total).
        """
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            # 1) helm status — stuck at revision 23
            _make_completed_process(
                stdout=_make_status_json("failed", 23),
            ),
            # 2) helm history — reveals rev 20 was last deployed
            _make_completed_process(
                stdout=_make_history_json(
                    [
                        (20, "deployed"),
                        (21, "failed"),
                        (22, "failed"),
                        (23, "failed"),
                    ]
                ),
            ),
            # 3) helm rollback — succeeds
            _make_completed_process(returncode=0),
        ]

        result = recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            helm_runner=mock_runner,
        )

        assert result is True
        assert mock_runner.call_count == 3

        # Verify history was called
        history_call = mock_runner.call_args_list[1]
        history_args = history_call[0][0]
        assert "history" in history_args
        assert "-o" in history_args
        assert "json" in history_args

        # Verify rollback targets revision 20, NOT 22
        rollback_call = mock_runner.call_args_list[2]
        rollback_args = rollback_call[0][0]
        assert "rollback" in rollback_args
        assert "20" in rollback_args
        # Must NOT contain "22" as the rollback target
        # (the old implementation would pick current - 1 = 22)
        assert rollback_args[rollback_args.index("rollback") + 2] == "20"

    @pytest.mark.requirement("AC-2.9")
    def test_recovery_no_deployed_revision_returns_false(self) -> None:
        """When history contains NO deployed revision (only failed/pending
        entries), recovery returns False without calling rollback, and
        logs a warning.

        This prevents blind rollback to an unknown state.
        """
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            # 1) helm status — stuck at revision 3
            _make_completed_process(
                stdout=_make_status_json("failed", 3),
            ),
            # 2) helm history — no deployed revision exists
            _make_completed_process(
                stdout=_make_history_json(
                    [
                        (1, "failed"),
                        (2, "pending-upgrade"),
                        (3, "failed"),
                    ]
                ),
            ),
        ]

        result = recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            helm_runner=mock_runner,
        )

        assert result is False
        # Only status + history calls — no rollback
        assert mock_runner.call_count == 2

    @pytest.mark.requirement("AC-2.9")
    def test_recovery_with_single_deployed_revision(self) -> None:
        """When history shows rev 1=deployed, 2=failed, recovery rolls
        back to revision 1.

        This is an edge case where the only good revision is the very first.
        """
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            # 1) helm status — stuck at revision 2
            _make_completed_process(
                stdout=_make_status_json("failed", 2),
            ),
            # 2) helm history — rev 1 is the only deployed
            _make_completed_process(
                stdout=_make_history_json(
                    [
                        (1, "deployed"),
                        (2, "failed"),
                    ]
                ),
            ),
            # 3) helm rollback — succeeds
            _make_completed_process(returncode=0),
        ]

        result = recover_stuck_helm_release(
            "floe-platform",
            "floe-test",
            helm_runner=mock_runner,
        )

        assert result is True
        assert mock_runner.call_count == 3

        # Verify rollback targets revision 1
        rollback_call = mock_runner.call_args_list[2]
        rollback_args = rollback_call[0][0]
        assert "rollback" in rollback_args
        assert rollback_args[rollback_args.index("rollback") + 2] == "1"

    @pytest.mark.requirement("AC-2.9")
    def test_history_command_failure_raises_runtime_error(self) -> None:
        """If ``helm history`` returns non-zero, a RuntimeError is raised.

        Per P37: guard subprocess return codes — silent failures become
        mystery downstream errors.
        """
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            # 1) helm status — stuck at revision 5
            _make_completed_process(
                stdout=_make_status_json("failed", 5),
            ),
            # 2) helm history — fails
            _make_completed_process(
                returncode=1,
                stderr="Error: release: not found",
            ),
        ]

        with pytest.raises(RuntimeError, match="[Hh]elm history"):
            recover_stuck_helm_release(
                "floe-platform",
                "floe-test",
                helm_runner=mock_runner,
            )
