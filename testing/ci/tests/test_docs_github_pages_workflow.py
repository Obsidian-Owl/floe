from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs.yml"

UPLOAD_PAGES_ARTIFACT_USES = (
    "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9"
)
DEPLOY_PAGES_USES = "actions/deploy-pages@cd2ce8fcbc39b97be8ca5fce6e763baed58fa128"


def _load_docs_workflow() -> dict[object, Any]:
    workflow = yaml.safe_load(DOCS_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    return cast(dict[object, Any], workflow)


def _workflow_triggers(workflow: dict[object, Any]) -> dict[str, Any]:
    triggers = workflow.get("on")
    if triggers is None and True in workflow:
        triggers = workflow[True]
    assert isinstance(triggers, dict)
    return cast(dict[str, Any], triggers)


def _job(workflow: dict[object, Any], name: str) -> dict[str, Any]:
    jobs = workflow.get("jobs", {})
    assert isinstance(jobs, dict)
    assert name in jobs, f"Expected docs workflow job {name!r}; found {list(jobs)}"
    return cast(dict[str, Any], jobs[name])


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps", [])
    assert isinstance(steps, list)
    return cast(list[dict[str, Any]], steps)


@pytest.mark.requirement("alpha-docs")
def test_docs_workflow_has_pages_permissions_without_broad_token_scope() -> None:
    """Docs deployment uses the minimum GitHub Pages token permissions."""
    workflow = _load_docs_workflow()

    assert workflow.get("permissions") == {"contents": "read"}

    deploy_job = _job(workflow, "deploy-pages")
    assert deploy_job.get("permissions") == {
        "pages": "write",
        "id-token": "write",
    }


@pytest.mark.requirement("alpha-docs")
def test_docs_workflow_uploads_built_starlight_site_on_main_pushes() -> None:
    """The docs build uploads the generated Starlight dist directory for Pages."""
    workflow = _load_docs_workflow()
    docs_job = _job(workflow, "docs")
    steps = _steps(docs_job)

    assert docs_job.get("if") is None
    assert any(step.get("run") == "npm --prefix docs-site run validate" for step in steps)

    upload_steps = [step for step in steps if step.get("uses") == UPLOAD_PAGES_ARTIFACT_USES]
    assert len(upload_steps) == 1
    assert upload_steps[0].get("if") == "github.event_name == 'push'"
    assert upload_steps[0].get("with") == {"path": "docs-site/dist"}


@pytest.mark.requirement("alpha-docs")
def test_docs_workflow_deploys_pages_only_after_main_docs_build() -> None:
    """GitHub Pages deploys from the validated docs artifact, never from PRs."""
    workflow = _load_docs_workflow()
    triggers = _workflow_triggers(workflow)
    deploy_job = _job(workflow, "deploy-pages")
    steps = _steps(deploy_job)

    assert triggers.get("pull_request") is not None
    assert triggers.get("push", {}).get("branches") == ["main"]
    assert deploy_job.get("needs") == "docs"
    assert deploy_job.get("if") == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert deploy_job.get("environment") == {
        "name": "github-pages",
        "url": "${{ steps.deployment.outputs.page_url }}",
    }
    assert any(
        step.get("id") == "deployment" and step.get("uses") == DEPLOY_PAGES_USES for step in steps
    )
