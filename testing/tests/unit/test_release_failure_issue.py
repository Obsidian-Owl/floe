from __future__ import annotations

from testing.release.failure_issue import FailureIssue, issue_comment_body, issue_title


def test_release_gate_issue_title_is_deterministic() -> None:
    issue = FailureIssue(
        lane="release-gate",
        version="v0.1.0-alpha.1",
        gate="full-e2e",
        classification="infrastructure",
        sha="0000000000000000000000000000000000000000",
        run_url="https://github.com/Obsidian-Owl/floe/actions/runs/123",
        log_excerpt="Error in server creation action: action timeout",
        cleanup_status="passed",
        skipped_outputs=("tag", "github-release", "pypi"),
    )

    assert issue_title(issue) == (
        "Release gate failed: v0.1.0-alpha.1 full-e2e infrastructure failure"
    )


def test_weekly_issue_title_omits_version() -> None:
    issue = FailureIssue(
        lane="weekly-validation",
        version=None,
        gate="e2e-tests",
        classification="product",
        sha="0000000000000000000000000000000000000000",
        run_url="https://github.com/Obsidian-Owl/floe/actions/runs/456",
        log_excerpt="assert expected_rows == actual_rows",
        cleanup_status="not-run",
        skipped_outputs=(),
    )

    assert issue_title(issue) == "Weekly validation failed: e2e-tests product failure"


def test_issue_comment_body_contains_release_safety_state() -> None:
    issue = FailureIssue(
        lane="release-gate",
        version="v0.1.0-alpha.1",
        gate="aws-live",
        classification="credential-setup",
        sha="0000000000000000000000000000000000000000",
        run_url="https://github.com/Obsidian-Owl/floe/actions/runs/789",
        log_excerpt="Unable to locate credentials",
        cleanup_status="passed",
        skipped_outputs=("tag", "github-release", "pypi"),
    )

    body = issue_comment_body(issue)

    assert "Workflow run: https://github.com/Obsidian-Owl/floe/actions/runs/789" in body
    assert "Commit: `0000000000000000000000000000000000000000`" in body
    assert "Requested version: `v0.1.0-alpha.1`" in body
    assert "Failed gate: `aws-live`" in body
    assert "Classification: `credential-setup`" in body
    assert "Cleanup status: `passed`" in body
    assert "Skipped outputs: `tag`, `github-release`, `pypi`" in body
    assert "Unable to locate credentials" in body
