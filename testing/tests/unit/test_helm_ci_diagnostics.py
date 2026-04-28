"""Tests for Helm CI failure diagnostics wiring."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "helm-ci.yaml"
DIAGNOSTICS = ROOT / "testing" / "ci" / "helm_diagnostics.sh"


def _load_workflow() -> dict[str, object]:
    with WORKFLOW.open() as handle:
        return cast(dict[str, object], yaml.safe_load(handle))


def test_helm_ci_invokes_shared_diagnostics_on_install_failure() -> None:
    workflow_text = WORKFLOW.read_text()

    assert "testing/ci/helm_diagnostics.sh floe-test floe-test" in workflow_text
    assert "helm uninstall floe-test --namespace floe-test" in workflow_text
    assert "--cleanup-on-fail" not in workflow_text


@pytest.mark.requirement("9b-FR-084")
def test_helm_ci_invokes_shared_diagnostics_on_helm_test_failure() -> None:
    workflow_text = WORKFLOW.read_text()

    run_helm_tests_section = workflow_text.split("- name: Run Helm tests", maxsplit=1)[1]
    run_helm_tests_section = run_helm_tests_section.split(
        "- name: Get pod status on failure",
        maxsplit=1,
    )[0]

    assert "helm test floe-test --namespace floe-test --timeout 5m" in run_helm_tests_section
    assert "testing/ci/helm_diagnostics.sh floe-test floe-test" in run_helm_tests_section
    assert 'exit "$status"' in run_helm_tests_section


def test_helm_diagnostics_script_collects_dagster_marquez_and_events() -> None:
    script = DIAGNOSTICS.read_text()

    required_fragments = [
        "kubectl get all -n",
        "kubectl get events -n",
        "kubectl describe pods -n",
        "kubectl logs -n",
        "Helm test pod logs",
        "polaris",
        "minio",
        "dagster-webserver",
        "dagster-daemon",
        "marquez",
        "helm status",
        "helm history",
    ]
    for fragment in required_fragments:
        assert fragment in script, f"Missing diagnostic fragment: {fragment}"


def test_helm_ci_has_integration_test_job() -> None:
    workflow = _load_workflow()
    jobs = cast(Mapping[str, Mapping[str, Any]], workflow["jobs"])

    integration_jobs = [
        job for job in jobs.values() if "Integration Test" in str(job.get("name", ""))
    ]
    assert integration_jobs, "helm-ci.yaml must keep the Kind integration test job"
