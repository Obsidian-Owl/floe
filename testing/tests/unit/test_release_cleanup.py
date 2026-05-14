from __future__ import annotations

import pytest

from testing.release.cleanup import CleanupEvidence, cleanup_status, cleanup_summary


@pytest.mark.requirement("REL-GATE-CLEANUP")
def test_cleanup_status_passes_when_all_scopes_are_clean() -> None:
    """Cleanup evidence passes only when every provider scope reports passed."""
    evidence = CleanupEvidence(
        devpod="passed",
        hetzner="passed",
        aws="passed",
    )

    assert cleanup_status(evidence) == "passed"
    assert cleanup_summary(evidence) == "DevPod: passed; Hetzner: passed; AWS: passed"


@pytest.mark.requirement("REL-GATE-CLEANUP")
def test_cleanup_status_fails_when_any_scope_failed() -> None:
    """A failed provider cleanup scope fails the collapsed cleanup status."""
    evidence = CleanupEvidence(
        devpod="passed",
        hetzner="failed: volume still exists",
        aws="passed",
    )

    assert cleanup_status(evidence) == "failed cleanup"
    assert "volume still exists" in cleanup_summary(evidence)


@pytest.mark.requirement("REL-GATE-CLEANUP")
def test_cleanup_status_reports_not_run_before_cleanup_gate() -> None:
    """Not-run cleanup evidence is distinguishable from passed cleanup evidence."""
    evidence = CleanupEvidence(
        devpod="not-run",
        hetzner="passed",
        aws="passed",
    )

    assert cleanup_status(evidence) == "not-run"
