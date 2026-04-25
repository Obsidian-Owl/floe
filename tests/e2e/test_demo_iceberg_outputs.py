"""E2E proof that demo Dagster runs produce loadable Iceberg outputs.

The test shells into the deployed Dagster environment and runs the packaged
validation helper there, so catalog/storage endpoints and credentials are the
ones from the deployed compiled artifacts.

Environment overrides:
    FLOE_E2E_NAMESPACE: Kubernetes namespace. Defaults to the existing local
        E2E convention, ``floe-test``.
    FLOE_E2E_DAGSTER_POD_SELECTOR: Pod selector for the Dagster environment.
        Defaults to the webserver labels used by ``testing/ci/test-e2e.sh``.
    FLOE_E2E_DAGSTER_CONTAINER: Optional container name for kubectl exec.
    FLOE_E2E_ARTIFACTS_PATH: In-container compiled_artifacts.json path.
    FLOE_E2E_ICEBERG_EXPECTED_TABLES: Comma-separated table names. Unqualified
        names are resolved by the helper under the compiled product namespace.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import pytest

_DEFAULT_NAMESPACE = "floe-test"
_DEFAULT_DAGSTER_SELECTOR = "app.kubernetes.io/name=dagster,component=dagster-webserver"
_DEFAULT_ARTIFACTS_PATH = "/app/demo/customer_360/compiled_artifacts.json"
_DEFAULT_EXPECTED_TABLES = "mart_customer_360"


def _run_kubectl(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run kubectl with captured output."""
    return subprocess.run(
        ["kubectl", *args],
        capture_output=True,
        check=False,
        text=True,
    )


def _find_dagster_pod(namespace: str, selector: str) -> str:
    """Return the first ready Dagster pod matching the configured selector."""
    result = _run_kubectl(
        [
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            selector,
            "-o",
            "json",
        ]
    )
    assert result.returncode == 0, (
        f"kubectl get pods failed for selector {selector!r} in namespace {namespace!r}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    pod_list: dict[str, Any] = json.loads(result.stdout)
    for item in pod_list.get("items", []):
        status = item.get("status", {})
        phase = status.get("phase")
        conditions = status.get("conditions", [])
        ready = any(
            condition.get("type") == "Ready" and condition.get("status") == "True"
            for condition in conditions
        )
        if phase == "Running" and ready:
            return str(item["metadata"]["name"])

    pod_names = [item.get("metadata", {}).get("name") for item in pod_list.get("items", [])]
    raise AssertionError(
        f"No ready Dagster pod matched selector {selector!r} in namespace {namespace!r}. "
        f"Matched pods: {pod_names}"
    )


@pytest.mark.e2e
@pytest.mark.platform_blackbox
@pytest.mark.requirement("AC-4")
def test_demo_iceberg_outputs_exist_in_deployed_catalog() -> None:
    """Run in-cluster validation for expected demo Iceberg table outputs."""
    namespace = os.environ.get("FLOE_E2E_NAMESPACE", _DEFAULT_NAMESPACE)
    selector = os.environ.get("FLOE_E2E_DAGSTER_POD_SELECTOR", _DEFAULT_DAGSTER_SELECTOR)
    artifacts_path = os.environ.get("FLOE_E2E_ARTIFACTS_PATH", _DEFAULT_ARTIFACTS_PATH)
    expected_tables = os.environ.get(
        "FLOE_E2E_ICEBERG_EXPECTED_TABLES",
        _DEFAULT_EXPECTED_TABLES,
    )

    pod_name = _find_dagster_pod(namespace=namespace, selector=selector)
    command = [
        "exec",
        "-n",
        namespace,
        pod_name,
    ]
    container = os.environ.get("FLOE_E2E_DAGSTER_CONTAINER")
    if container:
        command.extend(["-c", container])
    command.extend(
        [
            "--",
            "python",
            "-m",
            "floe_orchestrator_dagster.validation.iceberg_outputs",
            "--artifacts-path",
            artifacts_path,
            "--expected-table",
            expected_tables,
        ]
    )

    result = _run_kubectl(command)
    assert result.returncode == 0, (
        "In-cluster Iceberg output validation failed.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    validation = json.loads(result.stdout)
    expected_count = len([table for table in expected_tables.split(",") if table.strip()])
    assert validation["tables_validated"] == expected_count
