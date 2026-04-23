"""Bootstrap validation fixtures.

Bootstrap tests validate environment bring-up before product E2E tests run.
They may use Kubernetes and Helm readiness checks, but they should not assert
data-platform product behavior.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from testing.fixtures.polling import wait_for_condition

_FLUX_NAMESPACE = "flux-system"
_HELM_RELEASES = ("floe-platform", "floe-jobs-test")
_FLUX_CONTROLLERS = ("source-controller", "helm-controller")


def _run_kubectl(args: list[str], *, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    """Run kubectl for bootstrap environment health checks."""
    try:
        return subprocess.run(
            ["kubectl", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(args=["kubectl", *args], returncode=1, stderr=str(exc))


def _cluster_reachable() -> bool:
    """Return whether kubectl can reach the active cluster."""
    return _run_kubectl(["cluster-info"], timeout=10).returncode == 0


def _flux_installed() -> bool:
    """Return whether Flux appears installed in the active cluster."""
    return _run_kubectl(["get", "namespace", _FLUX_NAMESPACE]).returncode == 0


def _platform_namespace() -> str:
    """Return the namespace containing platform HelmReleases."""
    return os.environ.get("FLOE_E2E_NAMESPACE") or os.environ.get("FLOE_NAMESPACE", "floe-test")


def _check_flux_controllers_running() -> None:
    """Fail if installed Flux controllers are not Running."""
    for controller in _FLUX_CONTROLLERS:
        phases: list[str] = []
        for selector in (f"app={controller}", f"app.kubernetes.io/component={controller}"):
            result = _run_kubectl(
                [
                    "get",
                    "pods",
                    "-n",
                    _FLUX_NAMESPACE,
                    "-l",
                    selector,
                    "-o",
                    "jsonpath={.items[*].status.phase}",
                ]
            )
            if result.returncode == 0 and result.stdout.strip():
                phases = result.stdout.split()
                break
        if "Running" not in phases:
            pytest.fail(
                f"Flux controller {controller} is not Running (observed phases: {phases or 'none'})"
            )


def _resume_suspended_helmreleases(namespace: str) -> None:
    """Resume platform HelmReleases left suspended by interrupted runs."""
    for release in _HELM_RELEASES:
        result = _run_kubectl(
            [
                "get",
                "helmrelease",
                release,
                "-n",
                namespace,
                "-o",
                "jsonpath={.spec.suspend}",
            ]
        )
        if result.returncode != 0:
            continue
        if result.stdout.strip() != "true":
            continue
        if shutil.which("flux") is None:
            pytest.fail(
                f"HelmRelease {release} is suspended in {namespace}, "
                "but the flux CLI is not available to resume it."
            )
        resume = subprocess.run(
            ["flux", "resume", "helmrelease", release, "-n", namespace],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if resume.returncode != 0:
            pytest.fail(f"Failed to resume HelmRelease {release} in {namespace}: {resume.stderr}")


def _check_helmrelease_readiness(namespace: str) -> None:
    """Fail if existing platform HelmReleases are not Ready."""
    for release in _HELM_RELEASES:
        exists = _run_kubectl(["get", "helmrelease", release, "-n", namespace])
        if exists.returncode != 0:
            continue
        ready = _run_kubectl(
            [
                "wait",
                f"helmrelease/{release}",
                "-n",
                namespace,
                "--for=condition=Ready",
                "--timeout=120s",
            ],
            timeout=130,
        )
        if ready.returncode != 0:
            pytest.fail(f"HelmRelease {release} in {namespace} is not Ready: {ready.stderr}")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark all bootstrap tests with the bootstrap boundary marker."""
    bootstrap_dir = Path(__file__).parent
    for item in items:
        if item.path.is_relative_to(bootstrap_dir):
            item.add_marker(pytest.mark.bootstrap)


@pytest.fixture(scope="session", autouse=True)
def flux_helm_reconciliation_health() -> None:
    """Validate minimal Flux/Helm reconciliation health before bootstrap tests."""
    if not _cluster_reachable() or not _flux_installed():
        return

    namespace = _platform_namespace()
    _check_flux_controllers_running()
    _resume_suspended_helmreleases(namespace)
    _check_helmrelease_readiness(namespace)


@pytest.fixture(scope="session")
def wait_for_service() -> Callable[..., None]:
    """Create helper fixture for waiting on HTTP service readiness."""

    def _wait_for_service(
        url: str,
        timeout: float = 60.0,
        description: str | None = None,
        *,
        strict_status: bool = False,
    ) -> None:
        """Wait for an HTTP service to become available."""
        effective_description = description or f"service at {url}"

        def check_http() -> bool:
            try:
                response = httpx.get(url, timeout=5.0)
                if strict_status:
                    return response.status_code == 200
                return response.status_code < 500
            except (httpx.HTTPError, OSError):
                return False

        wait_for_condition(
            check_http,
            timeout=timeout,
            description=effective_description,
        )

    return _wait_for_service
