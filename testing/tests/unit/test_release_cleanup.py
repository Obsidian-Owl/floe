from __future__ import annotations

from testing.release.cleanup import CleanupEvidence, cleanup_status, cleanup_summary


def test_cleanup_status_passes_when_all_scopes_are_clean() -> None:
    evidence = CleanupEvidence(
        devpod="passed",
        hetzner="passed",
        aws="passed",
    )

    assert cleanup_status(evidence) == "passed"
    assert cleanup_summary(evidence) == "DevPod: passed; Hetzner: passed; AWS: passed"


def test_cleanup_status_fails_when_any_scope_failed() -> None:
    evidence = CleanupEvidence(
        devpod="passed",
        hetzner="failed: volume still exists",
        aws="passed",
    )

    assert cleanup_status(evidence) == "failed cleanup"
    assert "volume still exists" in cleanup_summary(evidence)


def test_cleanup_status_reports_not_run_before_cleanup_gate() -> None:
    evidence = CleanupEvidence(
        devpod="not-run",
        hetzner="passed",
        aws="passed",
    )

    assert cleanup_status(evidence) == "not-run"
