from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "prepare-release.yml"


def _workflow() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")))


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    triggers = workflow.get("on")
    if triggers is None:
        triggers = workflow[True]  # PyYAML 1.1 treats unquoted "on" as a boolean.
    return cast(dict[str, Any], triggers)


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_prepare_release_workflow_exists() -> None:
    """The release authority workflow exists in GitHub Actions."""
    assert WORKFLOW.exists()


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_prepare_release_is_manual_only() -> None:
    """Prepare Release must be manually dispatched rather than PR or tag triggered."""
    workflow = _workflow()
    triggers = _triggers(workflow)

    assert "workflow_dispatch" in triggers
    assert "push" not in triggers
    assert "pull_request" not in triggers


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_prepare_release_has_version_and_dry_run_inputs() -> None:
    """Prepare Release exposes explicit version and dry-run controls."""
    dispatch = _triggers(_workflow())["workflow_dispatch"]
    inputs = dispatch["inputs"]

    assert inputs["version"]["required"] is True
    assert inputs["dry_run"]["default"] is True


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_create_release_job_depends_on_all_gates_and_creates_release() -> None:
    """Release creation depends on every gate and owns GitHub Release creation."""
    jobs = _workflow()["jobs"]
    create_release = jobs["create-release"]

    assert create_release["if"] == "${{ success() && inputs.dry_run == false }}"
    assert set(create_release["needs"]) >= {
        "resolve-candidate",
        "static-and-contract-gates",
        "package-build-dry-run",
        "kind-integration",
        "full-e2e",
        "aws-live",
        "cleanup-verify",
        "release-evidence",
    }

    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git tag -a" not in text
    assert "git push origin" not in text
    assert "softprops/action-gh-release" in text


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_github_release_creation_is_tag_authority() -> None:
    """Release creation must not leave an immutable tag without a release."""
    text = WORKFLOW.read_text(encoding="utf-8")
    create_release = _workflow()["jobs"]["create-release"]
    release_steps = create_release["steps"]
    github_release_step = next(
        step for step in release_steps if step.get("name") == "Create GitHub Release"
    )

    assert "git tag -a" not in text
    assert "git push origin" not in text
    assert github_release_step["with"]["target_commitish"] == (
        "${{ needs.resolve-candidate.outputs.release_sha }}"
    )


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_failure_issue_runs_on_failure_and_has_issue_permission() -> None:
    """Failed release preparation creates or updates a GitHub issue."""
    job = _workflow()["jobs"]["failure-issue"]

    assert job["if"] == "${{ failure() }}"
    assert job["permissions"]["issues"] == "write"
    assert "gh issue list" in WORKFLOW.read_text(encoding="utf-8")


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_prepare_release_uploads_metadata_for_pypi_publish() -> None:
    """Successful non-dry-run release preparation uploads PyPI metadata."""
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "release-metadata/release-metadata.json" in text
    assert "name: release-metadata" in text
    assert '"tag": os.environ["RELEASE_TAG"]' in text
    assert '"sha": os.environ["RELEASE_SHA"]' in text


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_prepare_release_pins_candidate_to_dispatch_sha() -> None:
    """The release candidate SHA is the workflow dispatch commit, not moving main."""
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "ref: ${{ github.sha }}" in text
    assert 'release_sha="$(git rev-parse HEAD)"' in text
    assert 'release_sha="$(git rev-parse origin/main)"' not in text


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_cleanup_summary_uses_upstream_job_results() -> None:
    """Cleanup evidence is derived from upstream gate outcomes."""
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "FULL_E2E_RESULT: ${{ needs.full-e2e.result }}" in text
    assert "AWS_LIVE_RESULT: ${{ needs.aws-live.result }}" in text
    assert "--devpod passed" not in text
    assert "--hetzner passed" not in text
    assert "--aws passed" not in text


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_failure_issue_reports_failed_gate_from_needs_results() -> None:
    """Failure issues classify the actual failed gate instead of a constant."""
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'failed_gate="unknown"' in text
    assert '--gate "${failed_gate}"' in text
    assert '--classification "${classification}"' in text
    assert "--gate unknown" not in text


@pytest.mark.requirement("REL-GATE-WORKFLOW")
def test_failure_issue_covers_candidate_and_release_failures() -> None:
    """Failure issues include pre-gate validation and post-gate release failures."""
    job = _workflow()["jobs"]["failure-issue"]
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "resolve-candidate" in job["needs"]
    assert "create-release" in job["needs"]
    assert 'resolve-candidate="${RESOLVE_CANDIDATE_RESULT}"' in text
    assert 'create-release="${CREATE_RELEASE_RESULT}"' in text
    assert "RESOLVE_CANDIDATE_RESULT: ${{ needs.resolve-candidate.result }}" in text
    assert "CREATE_RELEASE_RESULT: ${{ needs.create-release.result }}" in text
