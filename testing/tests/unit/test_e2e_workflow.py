"""Structural validation for the dormant Phase E1 E2E workflow.

These tests parse ``.github/workflows/e2e.yml`` directly so the CI gate can be
validated without needing GitHub Actions infrastructure, Kind, or Helm CLI.
They also verify that the workflow contract remains wired into the repo's fast
Specwright unit command.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "e2e.yml"
FAST_UNIT_SLICE = REPO_ROOT / "testing" / "ci" / "test-specwright-unit.sh"

CHECKOUT_SHA = "34e114876b0b11c390a56381ad16ebd13914f8d5"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"
SETUP_UV_SHA = "e4db8464a088ece1b920f60402e813ea4de65b8f"
SETUP_HELM_SHA = "1a275c3b69536ee54be43f2070a358922e12c8d4"
KIND_ACTION_SHA = "a1b0e391336a6ee6713a0583f8c6240d70863de3"
PATHS_FILTER_SHA = "d1c1ffe0248fe513906c8e24db8ea791d46f8590"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"


def _load_workflow() -> dict[object, Any]:
    """Return the parsed E2E workflow YAML."""

    assert E2E_WORKFLOW.exists(), f"Expected E2E workflow at {E2E_WORKFLOW}"
    workflow = yaml.safe_load(E2E_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict), "Workflow YAML must parse to a mapping."
    return cast(dict[object, Any], workflow)


def _workflow_text() -> str:
    """Return the raw workflow text for comment-level contract checks."""

    return E2E_WORKFLOW.read_text(encoding="utf-8")


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


class TestE2EWorkflowPhaseE1:
    """Static validation for Unit E Phase E1 workflow structure."""

    @pytest.mark.requirement("AC-1")
    def test_workflow_exists_with_required_triggers(self) -> None:
        """The workflow must exist and declare the Phase E1 trigger surface."""

        workflow = _load_workflow()
        triggers = _workflow_triggers(workflow)
        permissions = workflow.get("permissions")

        pull_request = triggers.get("pull_request")
        assert isinstance(pull_request, dict), "pull_request trigger must be configured."
        assert pull_request.get("types") == ["opened", "synchronize", "reopened", "labeled"], (
            "pull_request trigger must handle opened, synchronize, reopened, and labeled."
        )
        assert "merge_group" in triggers, "merge_group trigger must be declared."
        assert "workflow_dispatch" in triggers, "workflow_dispatch trigger must be declared."
        assert permissions == {"contents": "read", "pull-requests": "read"}, (
            "Workflow permissions must grant contents: read and pull-requests: read."
        )

    @pytest.mark.requirement("AC-2")
    def test_e2e_job_is_dormant_in_phase_e1(self) -> None:
        """Phase E1 must land with the real E2E job disabled."""

        workflow = _load_workflow()
        e2e = _job(workflow, "e2e")

        assert e2e.get("if") is False, "Phase E1 must ship with `if: false` on the e2e job."

    @pytest.mark.requirement("AC-3")
    def test_changed_files_job_exports_infra_filter_output(self) -> None:
        """The changed-files job must expose the infra filter output to ``needs``."""

        workflow = _load_workflow()
        changed_files = _job(workflow, "changed-files")
        outputs = changed_files.get("outputs", {})

        assert outputs.get("infra") == "${{ steps.filter.outputs.infra }}", (
            "changed-files job must export steps.filter.outputs.infra as the infra output."
        )

        filter_step = _step_by_name(changed_files, "Filter infra changes")
        assert _uses_ref(filter_step) == f"dorny/paths-filter@{PATHS_FILTER_SHA}", (
            "changed-files job must pin dorny/paths-filter to a full commit SHA."
        )

        filters = filter_step.get("with", {}).get("filters")
        assert isinstance(filters, str) and filters.strip(), (
            "paths-filter step must define filters."
        )

        for expected_path in [
            "charts/**",
            "testing/**",
            "plugins/**",
            "packages/floe-core/**",
            "tests/**",
            "pyproject.toml",
            "uv.lock",
            "Makefile",
            "Dockerfile*",
            "**/Dockerfile*",
            ".github/workflows/ci.yml",
            ".github/workflows/e2e.yml",
        ]:
            assert expected_path in filters, f"Missing infra filter path '{expected_path}'."

        e2e = _job(workflow, "e2e")
        assert e2e.get("needs") == ["changed-files"], "e2e job must depend on changed-files."

    @pytest.mark.requirement("AC-4")
    def test_phase_e2_activation_contract_is_recorded_inline(self) -> None:
        """Phase E1 must keep the exact future Phase E2 condition discoverable inline."""

        workflow = _load_workflow()
        e2e = _job(workflow, "e2e")
        workflow_text = _workflow_text()

        assert e2e.get("if") is False, "Phase E1 must keep the live e2e job dormant."
        assert "# Phase E2 activation contract (arm in a follow-on PR):" in workflow_text, (
            "Workflow must explain where the future arming condition lives."
        )
        for expected_line in [
            "# if: |",
            "#   github.event_name == 'merge_group' ||",
            "#   github.event_name == 'workflow_dispatch' ||",
            "#   contains(github.event.pull_request.labels.*.name, 'run-e2e') ||",
            "#   needs.changed-files.outputs.infra == 'true'",
        ]:
            assert expected_line in workflow_text, (
                f"Workflow must keep the Phase E2 activation line '{expected_line}'."
            )

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
        assert _uses_ref(helm_step) == f"azure/setup-helm@{SETUP_HELM_SHA}", (
            "Helm setup must pin azure/setup-helm to a full commit SHA."
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
            "bitnami/postgresql:16.3.0-debian-12-r19",
            "minio/minio:RELEASE.2024-09-13T20-26-02Z",
            "jaegertracing/all-in-one:1.60",
        ]:
            assert image in run, f"Preload step must include pinned image '{image}'."

        assert 'docker pull "$img"' in run, "Preload step must pre-pull each heavy image."
        assert 'kind load docker-image "$img" --name floe-test' in run, (
            "Preload step must load each heavy image into the floe-test Kind cluster."
        )

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

        assert e2e.get("timeout-minutes") == 30, "e2e job must use timeout-minutes: 30."

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
            _step_by_name(e2e, "Install dependencies").get("run")
            == "uv sync --all-extras --dev"
        ), (
            "Install dependencies step must run 'uv sync --all-extras --dev'."
        )
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
