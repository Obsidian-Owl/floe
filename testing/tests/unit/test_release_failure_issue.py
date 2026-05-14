from __future__ import annotations

import pytest

from testing.release.failure_issue import (
    FailureIssue,
    classify_failure,
    issue_comment_body,
    issue_title,
)


@pytest.mark.requirement("REL-GATE-ISSUE")
def test_release_gate_issue_title_is_deterministic() -> None:
    """Release-gate issue titles include version, failed gate, and classification."""
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


@pytest.mark.requirement("REL-GATE-ISSUE")
def test_weekly_issue_title_omits_version() -> None:
    """Weekly validation issue titles omit release version details."""
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


@pytest.mark.requirement("REL-GATE-ISSUE")
def test_issue_comment_body_contains_release_safety_state() -> None:
    """Issue bodies record release safety state and skipped outputs."""
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


@pytest.mark.requirement("REL-GATE-ISSUE")
def test_static_gate_setup_action_failures_are_release_tooling() -> None:
    """Static gate setup/action failures are not product failures."""
    assert (
        classify_failure(
            "static-and-contract-gates",
            "Error: Failed to download Helm from location "
            "https://get.helm.sh/helm-v0.1.0-alpha.1-linux-amd64.tar.gz",
        )
        == "release-tooling"
    )


@pytest.mark.requirement("REL-GATE-ISSUE")
def test_static_gate_test_failures_remain_product_failures() -> None:
    """Actual static or contract test failures stay product-classified."""
    assert (
        classify_failure(
            "static-and-contract-gates",
            "FAILED tests/contract/test_compilation.py::test_contract_roundtrip",
        )
        == "product"
    )
