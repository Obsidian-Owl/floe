from __future__ import annotations

from pathlib import Path


def workflow_files(workflows_dir: Path) -> list[Path]:
    return sorted(
        [*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")],
        key=lambda path: path.name,
    )


def classify_workflows(workflows_dir: Path) -> dict[str, str]:
    classes: dict[str, str] = {}
    for path in workflow_files(workflows_dir):
        name = path.name
        if name == "ci.yml":
            classes[name] = "fast-pr"
        elif name in {"release.yml", "pypi-publish.yml", "helm-release.yaml"}:
            classes[name] = "release"
        elif name == "e2e.yml":
            classes[name] = "live-validation"
        elif name in {"weekly.yml", "codspeed.yml", "security.yml"}:
            classes[name] = "scheduled-maintenance"
        else:
            classes[name] = "supporting"
    return classes
