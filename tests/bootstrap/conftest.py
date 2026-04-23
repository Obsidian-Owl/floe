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


def _platform_namespace() -> str:
    """Return the namespace containing platform HelmReleases."""
    return os.environ.get("FLOE_E2E_NAMESPACE") or os.environ.get("FLOE_NAMESPACE", "floe-test")


def _kubectl_error(result: subprocess.CompletedProcess[str]) -> str:
    """Return normalized kubectl output for error classification."""
    return f"{result.stderr}\n{result.stdout}".lower()


def _is_forbidden(result: subprocess.CompletedProcess[str]) -> bool:
    """Return whether kubectl failed because RBAC denied the request."""
    output = _kubectl_error(result)
    return (
        "forbidden" in output or "cannot get resource" in output or "cannot list resource" in output
    )


def _is_not_found(result: subprocess.CompletedProcess[str]) -> bool:
    """Return whether kubectl failed because a resource or namespace is absent."""
    output = _kubectl_error(result)
    return (
        "notfound" in output
        or "not found" in output
        or "the server doesn't have a resource type" in output
    )


def _fail_forbidden(resource: str, result: subprocess.CompletedProcess[str]) -> None:
    """Fail bootstrap with an actionable message for missing test-runner RBAC."""
    pytest.fail(
        f"Bootstrap Flux/Helm safeguard cannot read {resource}: {result.stderr.strip()}. "
        "The standard test runner ServiceAccount is missing required RBAC."
    )


def _flux_controller_phases(controller: str) -> list[str] | None:
    """Return Flux controller pod phases, or None when Flux is absent."""
    saw_not_found = False
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
        if result.returncode == 0:
            phases = result.stdout.split()
            if phases:
                return phases
            continue
        if _is_forbidden(result):
            _fail_forbidden(f"pods in namespace {_FLUX_NAMESPACE}", result)
        if _is_not_found(result):
            saw_not_found = True
            continue
        pytest.fail(f"Failed to inspect Flux controller {controller}: {result.stderr.strip()}")
    if saw_not_found:
        return None
    return []


def _check_flux_controllers_running() -> bool:
    """Fail if installed Flux controllers are not Running.

    Returns:
        True when Flux controllers were observed, False when Flux is absent.
    """
    for controller in _FLUX_CONTROLLERS:
        phases = _flux_controller_phases(controller)
        if phases is None:
            return False
        if "Running" not in phases:
            pytest.fail(
                f"Flux controller {controller} is not Running (observed phases: {phases or 'none'})"
            )
    return True


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
            if _is_forbidden(result):
                _fail_forbidden(f"HelmRelease {release} in namespace {namespace}", result)
            if not _is_not_found(result):
                pytest.fail(f"Failed to inspect HelmRelease {release}: {result.stderr.strip()}")
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
            if _is_forbidden(resume):
                _fail_forbidden(f"HelmRelease {release} in namespace {namespace}", resume)
            pytest.fail(f"Failed to resume HelmRelease {release} in {namespace}: {resume.stderr}")


def _check_helmrelease_readiness(namespace: str) -> None:
    """Fail if existing platform HelmReleases are not Ready."""
    for release in _HELM_RELEASES:
        exists = _run_kubectl(["get", "helmrelease", release, "-n", namespace])
        if exists.returncode != 0:
            if _is_forbidden(exists):
                _fail_forbidden(f"HelmRelease {release} in namespace {namespace}", exists)
            if not _is_not_found(exists):
                pytest.fail(f"Failed to inspect HelmRelease {release}: {exists.stderr.strip()}")
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
            if _is_forbidden(ready):
                _fail_forbidden(f"HelmRelease {release} readiness in namespace {namespace}", ready)
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
    if not _cluster_reachable():
        return

    namespace = _platform_namespace()
    if not _check_flux_controllers_running():
        return
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
