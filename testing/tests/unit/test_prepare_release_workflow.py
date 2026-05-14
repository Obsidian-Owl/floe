from __future__ import annotations

from pathlib import Path
from typing import Any, cast

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


def test_prepare_release_workflow_exists() -> None:
    assert WORKFLOW.exists()


def test_prepare_release_is_manual_only() -> None:
    workflow = _workflow()
    triggers = _triggers(workflow)

    assert "workflow_dispatch" in triggers
    assert "push" not in triggers
    assert "pull_request" not in triggers


def test_prepare_release_has_version_and_dry_run_inputs() -> None:
    dispatch = _triggers(_workflow())["workflow_dispatch"]
    inputs = dispatch["inputs"]

    assert inputs["version"]["required"] is True
    assert inputs["dry_run"]["default"] is True


def test_create_release_job_depends_on_all_gates_and_pushes_tag() -> None:
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
    assert "git tag -a" in text
    assert "git push origin" in text
    assert "softprops/action-gh-release" in text


def test_failure_issue_runs_on_failure_and_has_issue_permission() -> None:
    job = _workflow()["jobs"]["failure-issue"]

    assert job["if"] == "${{ failure() }}"
    assert job["permissions"]["issues"] == "write"
    assert "gh issue list" in WORKFLOW.read_text(encoding="utf-8")


def test_prepare_release_uploads_metadata_for_pypi_publish() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "release-metadata/release-metadata.json" in text
    assert "name: release-metadata" in text
    assert '"tag": os.environ["RELEASE_TAG"]' in text
    assert '"sha": os.environ["RELEASE_SHA"]' in text
