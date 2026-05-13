from __future__ import annotations

from pathlib import Path

from testing.release.ci_inventory import classify_workflows, workflow_files

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_workflow_inventory_includes_release_and_live_validation_lanes() -> None:
    files = workflow_files(REPO_ROOT / ".github" / "workflows")
    names = {path.name for path in files}

    assert "ci.yml" in names
    assert "e2e.yml" in names
    assert "release.yml" in names
    assert "pypi-publish.yml" in names
    assert "helm-release.yaml" in names


def test_workflow_classification_separates_pr_release_live_and_scheduled() -> None:
    classes = classify_workflows(REPO_ROOT / ".github" / "workflows")

    assert classes["ci.yml"] == "fast-pr"
    assert classes["release.yml"] == "release"
    assert classes["pypi-publish.yml"] == "release"
    assert classes["helm-release.yaml"] == "release"
    assert classes["e2e.yml"] == "live-validation"
    assert classes["weekly.yml"] == "scheduled-maintenance"
