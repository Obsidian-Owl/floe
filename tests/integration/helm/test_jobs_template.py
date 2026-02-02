"""Helm template rendering tests for floe-jobs chart.

These tests validate the floe-jobs Helm chart templates render correctly
with various value configurations.

Requirements tested:
- 9b-FR-081: Template rendering validation
- 9b-FR-020: Job template
- 9b-FR-021: CronJob template
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


@pytest.fixture(scope="module")
def jobs_chart_path() -> Path:
    """Return path to floe-jobs chart."""
    return Path(__file__).parents[3] / "charts" / "floe-jobs"


def parse_yaml_documents(yaml_output: str) -> list[dict[str, Any]]:
    """Parse multi-document YAML output into list of dicts."""
    docs: list[dict[str, Any]] = []
    for doc in yaml.safe_load_all(yaml_output):
        if doc:
            docs.append(doc)
    return docs


class TestJobsChartTemplate:
    """Test floe-jobs chart template rendering."""

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available")
    def test_template_renders_serviceaccount(self, jobs_chart_path: Path) -> None:
        """Test ServiceAccount is rendered by default."""
        result = subprocess.run(
            [
                "helm",
                "template",
                "test-release",
                str(jobs_chart_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        docs = parse_yaml_documents(result.stdout)
        sa_docs = [d for d in docs if d.get("kind") == "ServiceAccount"]
        assert len(sa_docs) == 1
        assert sa_docs[0]["metadata"]["name"] == "test-release-floe-jobs"

    @pytest.mark.requirement("9b-FR-020")
    @pytest.mark.usefixtures("helm_available")
    def test_template_renders_dbt_job(self, jobs_chart_path: Path) -> None:
        """Test dbt Job is rendered when enabled without schedule."""
        result = subprocess.run(
            [
                "helm",
                "template",
                "test-release",
                str(jobs_chart_path),
                "--set",
                "dbt.enabled=true",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        docs = parse_yaml_documents(result.stdout)
        job_docs = [d for d in docs if d.get("kind") == "Job"]
        assert len(job_docs) == 1
        assert job_docs[0]["metadata"]["name"] == "test-release-floe-jobs-dbt"

        # Verify job spec
        job_spec = job_docs[0]["spec"]
        assert job_spec["backoffLimit"] == 3
        assert job_spec["template"]["spec"]["restartPolicy"] == "Never"

    @pytest.mark.requirement("9b-FR-021")
    @pytest.mark.usefixtures("helm_available")
    def test_template_renders_dbt_cronjob(self, jobs_chart_path: Path) -> None:
        """Test dbt CronJob is rendered when schedule is set."""
        result = subprocess.run(
            [
                "helm",
                "template",
                "test-release",
                str(jobs_chart_path),
                "--set",
                "dbt.enabled=true",
                "--set",
                "dbt.schedule=0 */6 * * *",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        docs = parse_yaml_documents(result.stdout)
        cronjob_docs = [d for d in docs if d.get("kind") == "CronJob"]
        assert len(cronjob_docs) == 1
        assert cronjob_docs[0]["metadata"]["name"] == "test-release-floe-jobs-dbt"

        # Verify cronjob spec
        cronjob_spec = cronjob_docs[0]["spec"]
        assert cronjob_spec["schedule"] == "0 */6 * * *"
        assert cronjob_spec["concurrencyPolicy"] == "Forbid"

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available")
    def test_template_renders_security_context(self, jobs_chart_path: Path) -> None:
        """Test security contexts are applied to jobs."""
        result = subprocess.run(
            [
                "helm",
                "template",
                "test-release",
                str(jobs_chart_path),
                "--set",
                "dbt.enabled=true",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        docs = parse_yaml_documents(result.stdout)
        job_docs = [d for d in docs if d.get("kind") == "Job"]
        assert len(job_docs) == 1

        pod_spec = job_docs[0]["spec"]["template"]["spec"]

        # Pod security context
        assert pod_spec["securityContext"]["runAsNonRoot"] is True
        assert pod_spec["securityContext"]["runAsUser"] == 1000

        # Container security context
        container = pod_spec["containers"][0]
        assert container["securityContext"]["allowPrivilegeEscalation"] is False

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available")
    def test_template_renders_platform_integration(self, jobs_chart_path: Path) -> None:
        """Test platform integration endpoints are injected."""
        result = subprocess.run(
            [
                "helm",
                "template",
                "test-release",
                str(jobs_chart_path),
                "--set",
                "dbt.enabled=true",
                "--set",
                "platform.releaseName=floe",
                "--set",
                "platform.namespace=floe-prod",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        docs = parse_yaml_documents(result.stdout)
        job_docs = [d for d in docs if d.get("kind") == "Job"]
        assert len(job_docs) == 1

        container = job_docs[0]["spec"]["template"]["spec"]["containers"][0]
        env_vars = {e["name"]: e["value"] for e in container.get("env", [])}

        assert "POLARIS_ENDPOINT" in env_vars
        assert "floe-polaris" in env_vars["POLARIS_ENDPOINT"]
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in env_vars
        assert "otel-collector" in env_vars["OTEL_EXPORTER_OTLP_ENDPOINT"]

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available")
    def test_template_renders_custom_job(self, jobs_chart_path: Path) -> None:
        """Test custom jobs are rendered correctly."""
        result = subprocess.run(
            [
                "helm",
                "template",
                "test-release",
                str(jobs_chart_path),
                "--set",
                "customJobs[0].name=my-job",
                "--set",
                "customJobs[0].image.repository=my-image",
                "--set",
                "customJobs[0].image.tag=v1",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        docs = parse_yaml_documents(result.stdout)
        job_docs = [d for d in docs if d.get("kind") == "Job"]
        assert len(job_docs) == 1
        assert job_docs[0]["metadata"]["name"] == "test-release-floe-jobs-my-job"

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available")
    def test_template_no_jobs_when_disabled(self, jobs_chart_path: Path) -> None:
        """Test no jobs are rendered when all are disabled."""
        result = subprocess.run(
            [
                "helm",
                "template",
                "test-release",
                str(jobs_chart_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        docs = parse_yaml_documents(result.stdout)
        job_docs = [d for d in docs if d.get("kind") in ("Job", "CronJob")]
        assert len(job_docs) == 0
