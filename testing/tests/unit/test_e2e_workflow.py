"""Structural validation for the active E2E workflow.

These tests parse ``.github/workflows/e2e.yml`` directly so the CI gate can be
validated without needing GitHub Actions infrastructure, Kind, or Helm CLI.
They also verify that standalone E2E remains manually dispatched while weekly
and release workflows own scheduled and release-blocking validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "e2e.yml"
FAST_UNIT_SLICE = REPO_ROOT / "testing" / "ci" / "test-specwright-unit.sh"

CHECKOUT_SHA = "de0fac2e4500dabe0009e67214ff5f5447ce83dd"  # pragma: allowlist secret
SETUP_PYTHON_SHA = "a309ff8b426b58ec0e2a45f0f869d46889d02405"  # pragma: allowlist secret
SETUP_UV_SHA = "08807647e7069bb48b6ef5acd8ec9567f424441b"  # pragma: allowlist secret
SETUP_HELM_SHA = "dda3372f752e03dde6b3237bc9431cdc2f7a02a2"  # pragma: allowlist secret
KIND_ACTION_SHA = "ef37e7f390d99f746eb8b610417061a60e82a6cc"  # pragma: allowlist secret
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"  # pragma: allowlist secret


def _load_workflow() -> dict[object, Any]:
    """Return the parsed E2E workflow YAML."""

    assert E2E_WORKFLOW.exists(), f"Expected E2E workflow at {E2E_WORKFLOW}"
    workflow = yaml.safe_load(E2E_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict), "Workflow YAML must parse to a mapping."
    return cast(dict[object, Any], workflow)


def _workflow_triggers(workflow: dict[object, Any]) -> dict[str, Any]:
    """Return the workflow trigger mapping, handling YAML 1.1 ``on`` parsing."""

    triggers = workflow.get("on")
    if triggers is None and True in workflow:
        triggers = workflow[True]
    assert isinstance(triggers, dict), "Workflow triggers must parse to a mapping."
    return cast(dict[str, Any], triggers)


def _job(workflow: dict[object, Any], job_name: str) -> dict[str, Any]:
    """Return one named job from the workflow."""

    jobs = workflow.get("jobs", {})
    assert isinstance(jobs, dict), "Workflow jobs must parse to a mapping."
    assert job_name in jobs, f"Missing '{job_name}' job. Found jobs: {list(jobs.keys())}"
    job = jobs[job_name]
    assert isinstance(job, dict), f"Job '{job_name}' must parse to a mapping."
    return cast(dict[str, Any], job)


def _job_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the step list for one job."""

    steps = job.get("steps", [])
    assert isinstance(steps, list), "Workflow job steps must be a list."
    return [step for step in steps if isinstance(step, dict)]


def _step_by_name(job: dict[str, Any], name: str) -> dict[str, Any]:
    """Return one step by its ``name`` field."""

    steps = _job_steps(job)
    for step in steps:
        if step.get("name") == name:
            return step
    raise AssertionError(
        f"Missing step named '{name}'. Found: {[step.get('name') for step in steps]}"
    )


def _uses_ref(step: dict[str, Any]) -> str:
    """Return the ``uses`` field for one step."""

    uses = step.get("uses")
    assert isinstance(uses, str) and uses, f"Step must declare a non-empty uses: {step}"
    return uses


class TestE2EWorkflow:
    """Static validation for the E2E workflow structure."""

    @pytest.mark.requirement("AC-1")
    def test_workflow_exists_as_manual_only_trigger(self) -> None:
        """Standalone E2E must not run automatically for PRs or merge queues."""

        workflow = _load_workflow()
        triggers = _workflow_triggers(workflow)
        permissions = workflow.get("permissions")

        assert "workflow_dispatch" in triggers, "workflow_dispatch trigger must be declared."
        assert "pull_request" not in triggers, "PRs must not trigger standalone E2E."
        assert "merge_group" not in triggers, "Merge queues must not trigger standalone E2E."
        assert permissions == {"contents": "read"}, "Workflow only needs repository read access."

    @pytest.mark.requirement("AC-2")
    def test_e2e_job_has_no_auto_trigger_condition(self) -> None:
        """The E2E job must not opt back into PR, label, or path-based runs."""

        workflow = _load_workflow()
        e2e = _job(workflow, "e2e")
        workflow_text = E2E_WORKFLOW.read_text(encoding="utf-8")

        assert "if" not in e2e
        assert "github.event_name == 'merge_group'" not in workflow_text
        assert "contains(github.event.pull_request.labels.*.name, 'run-e2e')" not in workflow_text
        assert "needs.changed-files.outputs.infra" not in workflow_text

    @pytest.mark.requirement("AC-3")
    def test_workflow_has_no_changed_files_path_filter_gate(self) -> None:
        """Changed-file filters must not promote PR changes into full E2E."""

        workflow = _load_workflow()
        jobs = workflow.get("jobs", {})
        workflow_text = E2E_WORKFLOW.read_text(encoding="utf-8")
        e2e = _job(workflow, "e2e")

        assert "changed-files" not in jobs
        assert "dorny/paths-filter" not in workflow_text
        assert "needs" not in e2e

    @pytest.mark.requirement("AC-5")
    def test_workflow_has_non_cancelling_ref_scoped_concurrency(self) -> None:
        """Concurrency must serialize by ref without cancelling in-flight E2E runs."""

        workflow = _load_workflow()
        concurrency = workflow.get("concurrency", {})

        assert concurrency.get("group") == "e2e-${{ github.ref }}", (
            "Workflow concurrency group must scope E2E runs to the current ref."
        )
        assert concurrency.get("cancel-in-progress") is False, (
            "Workflow must not cancel in-progress E2E runs."
        )

    @pytest.mark.requirement("AC-6")
    def test_e2e_job_pins_kind_and_helm_versions(self) -> None:
        """Kind creation and Helm setup must be pinned for reproducibility."""

        workflow = _load_workflow()
        e2e = _job(workflow, "e2e")

        kind_step = _step_by_name(e2e, "Set up Kind")
        assert _uses_ref(kind_step) == f"helm/kind-action@{KIND_ACTION_SHA}", (
            "Kind setup must pin helm/kind-action to a full commit SHA."
        )
        assert kind_step.get("with", {}).get("version") == "v0.24.0", (
            "Kind setup must pin the Kind version."
        )
        assert kind_step.get("with", {}).get("node_image") == "kindest/node:v1.31.0", (
            "Kind setup must pin the node image."
        )

        helm_step = _step_by_name(e2e, "Set up Helm")
        assert _uses_ref(helm_step) == f"Azure/setup-helm@{SETUP_HELM_SHA}", (
            "Helm setup must pin Azure/setup-helm to a full commit SHA."
        )
        assert helm_step.get("with", {}).get("version") == "v3.16.0", (
            "Helm setup must pin Helm 3.16 explicitly."
        )

    @pytest.mark.requirement("AC-7")
    def test_e2e_job_preloads_heavy_images_into_kind(self) -> None:
        """The workflow must pre-pull and kind-load heavy images before deploy."""

        workflow = _load_workflow()
        e2e = _job(workflow, "e2e")
        preload_step = _step_by_name(e2e, "Pre-pull and load heavy images into Kind")
        run = preload_step.get("run", "")

        assert isinstance(run, str) and run.strip(), "Preload step must define a run script."

        for image in [
            "apache/polaris:1.2.0-incubating",
            "postgres:16-alpine",
            "minio/minio:RELEASE.2024-09-13T20-26-02Z",
            "jaegertracing/all-in-one:1.60",
        ]:
            assert image in run, f"Preload step must include pinned image '{image}'."

        assert 'docker pull "$img"' in run, "Preload step must pre-pull each heavy image."
        assert 'kind load docker-image "$img" --name floe-test' in run, (
            "Preload step must load each heavy image into the floe-test Kind cluster."
        )

    @pytest.mark.requirement("AC-7")
    def test_e2e_job_installs_flux_before_deploying_platform(self) -> None:
        """setup-cluster.sh requires the Flux CLI before platform deployment."""

        workflow = _load_workflow()
        e2e = _job(workflow, "e2e")
        steps = _job_steps(e2e)
        step_names = [step.get("name") for step in steps]

        flux_index = step_names.index("Install Flux CLI")
        deploy_index = step_names.index("Deploy floe-platform")
        flux_run = steps[flux_index].get("run", "")

        assert flux_index < deploy_index, "Flux CLI must be installed before setup-cluster.sh."
        assert 'FLUX_VERSION="2.5.1"' in flux_run
        assert 'FLUX_ARCHIVE="flux_${FLUX_VERSION}_linux_amd64.tar.gz"' in flux_run
        assert '-o "/tmp/${FLUX_ARCHIVE}"' in flux_run
        assert "sha256sum -c -" in flux_run
        assert "sudo install /tmp/flux /usr/local/bin/flux" in flux_run
        assert "flux --version" in flux_run

    @pytest.mark.requirement("AC-8")
    def test_e2e_job_collects_failure_diagnostics_and_uploads_artifacts(self) -> None:
        """The workflow must collect debug info on failure and upload artifacts always."""

        workflow = _load_workflow()
        e2e = _job(workflow, "e2e")

        failure_step = _step_by_name(e2e, "Collect debug artifacts on failure")
        assert failure_step.get("if") == "failure()", (
            "Failure diagnostics step must only run when the job fails."
        )
        failure_run = failure_step.get("run", "")
        assert isinstance(failure_run, str) and failure_run.strip(), (
            "Failure diagnostics step must define a run script."
        )
        for command in [
            "kubectl get pods,jobs,events -A -o wide",
            "kubectl logs -n floe-test -l app.kubernetes.io/component=test-runner --tail=200",
            "kubectl logs -n floe-test deployment/floe-platform-polaris --tail=100",
        ]:
            assert command in failure_run, f"Failure diagnostics step missing '{command}'."

        upload_step = _step_by_name(e2e, "Upload test artifacts")
        assert upload_step.get("if") == "always()", "Artifact upload must run unconditionally."
        assert _uses_ref(upload_step) == f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", (
            "Artifact upload must pin actions/upload-artifact to a full commit SHA."
        )
        upload_with = upload_step.get("with", {})
        assert upload_with.get("name") == "e2e-results", (
            "Artifact upload must use the e2e-results artifact name."
        )
        upload_path = upload_with.get("path", "")
        assert isinstance(upload_path, str) and upload_path.strip(), (
            "Artifact upload must define a non-empty path list."
        )
        for artifact_path in [
            "test-artifacts/",
            "/tmp/floe-*.log",
            "e2e-results.xml",
            "e2e-destructive-results.xml",
        ]:
            assert artifact_path in upload_path, f"Artifact upload must include '{artifact_path}'."

    @pytest.mark.requirement("AC-9")
    def test_e2e_job_has_timeout_and_expected_core_steps(self) -> None:
        """The e2e job must have the expected timeout and execution steps."""

        workflow = _load_workflow()
        e2e = _job(workflow, "e2e")

        assert e2e.get("timeout-minutes") == 60, (
            "e2e job must allow enough time for setup, standard, developer, "
            "and destructive validation lanes."
        )

        expected_uses = {
            "actions/checkout": CHECKOUT_SHA,
            "actions/setup-python": SETUP_PYTHON_SHA,
            "astral-sh/setup-uv": SETUP_UV_SHA,
        }
        for step_name, action_prefix in {
            "Checkout code": "actions/checkout",
            "Set up Python": "actions/setup-python",
            "Install uv": "astral-sh/setup-uv",
        }.items():
            step = _step_by_name(e2e, step_name)
            assert _uses_ref(step) == f"{action_prefix}@{expected_uses[action_prefix]}", (
                f"Step '{step_name}' must pin {action_prefix} to the repo-standard SHA."
            )

        assert (
            _step_by_name(e2e, "Install dependencies").get("run") == "uv sync --all-extras --dev"
        ), "Install dependencies step must run 'uv sync --all-extras --dev'."
        assert (
            _step_by_name(e2e, "Deploy floe-platform").get("run")
            == "./testing/k8s/setup-cluster.sh"
        ), "Deploy step must run './testing/k8s/setup-cluster.sh'."
        assert (
            _step_by_name(e2e, "Run E2E (standard + destructive)").get("run")
            == "make test-e2e-full"
        ), "E2E run step must invoke 'make test-e2e-full'."

    @pytest.mark.requirement("AC-10")
    def test_workflow_contract_is_wired_into_fast_specwright_unit_slice(self) -> None:
        """The workflow contract test must stay in the configured fast unit command."""

        assert FAST_UNIT_SLICE.exists(), f"Expected fast unit command at {FAST_UNIT_SLICE}"
        script_text = FAST_UNIT_SLICE.read_text(encoding="utf-8")

        assert "testing/tests/unit/test_e2e_workflow.py" in script_text, (
            "Fast Specwright unit command must include the workflow contract test."
        )
