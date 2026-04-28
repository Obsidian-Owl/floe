"""Kubernetes test utilities for pod recovery, kubectl, and helm operations.

Provides shared helpers for E2E tests that interact with K8s clusters.
All kubectl/helm calls use subprocess with shell=False for security.

Functions:
    run_kubectl: Execute kubectl commands with optional namespace.
    run_helm: Execute helm commands with extended timeout.
    get_pod_uid: Get the UID of a pod matching a label selector.
    check_pod_ready: Check if pods matching a selector are Ready.
    assert_pod_recovery: Delete a pod and assert K8s replaces it.

Types:
    PodRecoveryResult: NamedTuple with original_uid, new_uid, recovery_seconds.
    PodRecoveryError: Raised when pod recovery fails.

Example:
    from testing.fixtures.kubernetes import assert_pod_recovery

    result = assert_pod_recovery(
        label_selector="app.kubernetes.io/name=minio",
        service_name="MinIO",
        namespace="floe-test",
        timeout=30.0,
    )
    assert result.original_uid != result.new_uid
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any, NamedTuple

import yaml

from testing.fixtures.polling import wait_for_condition

logger = logging.getLogger(__name__)


class PodRecoveryResult(NamedTuple):
    """Result of a pod recovery operation."""

    original_uid: str
    new_uid: str
    recovery_seconds: float


class PodRecoveryError(Exception):
    """Raised when pod recovery fails."""


def run_kubectl(
    args: list[str],
    namespace: str | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Run kubectl command with optional namespace.

    Args:
        args: kubectl arguments (e.g., ["get", "pods"]).
        namespace: K8s namespace to target. If provided, adds -n flag.
        timeout: Command timeout in seconds. Defaults to 60.

    Returns:
        Completed process result with stdout, stderr, and returncode.
    """
    cmd = ["kubectl"]
    if namespace:
        cmd.extend(["-n", namespace])
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def run_helm(
    args: list[str],
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    """Run helm command with timeout.

    Args:
        args: helm arguments (e.g., ["status", "floe-platform"]).
        timeout: Command timeout in seconds. Defaults to 900.

    Returns:
        Completed process result with stdout, stderr, and returncode.
    """
    return subprocess.run(
        ["helm"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _chart_dependency_repositories(chart_path: Path) -> list[tuple[str, str]]:
    """Return Helm repository aliases and URLs declared by a chart's dependencies."""
    chart_yaml = chart_path / "Chart.yaml"
    if not chart_yaml.exists():
        return []

    raw_chart: Any = yaml.safe_load(chart_yaml.read_text()) or {}
    if not isinstance(raw_chart, dict):
        return []

    raw_dependencies = raw_chart.get("dependencies", [])
    if not isinstance(raw_dependencies, list):
        return []

    repositories: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    used_names: set[str] = set()
    for index, dependency in enumerate(raw_dependencies):
        if not isinstance(dependency, dict):
            continue
        repository = dependency.get("repository")
        if not isinstance(repository, str) or not repository.startswith(("http://", "https://")):
            continue
        if repository in seen_urls:
            continue

        raw_name = dependency.get("alias") or dependency.get("name") or f"dependency-{index}"
        name = str(raw_name).strip() or f"dependency-{index}"
        repo_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or f"dependency-{index}"
        if repo_name in used_names:
            repo_name = f"{repo_name}-{index}"

        repositories.append((repo_name, repository))
        seen_urls.add(repository)
        used_names.add(repo_name)

    return repositories


def _ensure_helm_chart_dependencies(
    chart_path: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str] | None:
    """Add chart-declared Helm repos and build dependencies before rendering."""
    for repo_name, repository in _chart_dependency_repositories(chart_path):
        repo_result = run_helm(
            ["repo", "add", repo_name, repository, "--force-update"],
            timeout=timeout,
        )
        if repo_result.returncode != 0:
            return repo_result

    dependency_result = run_helm(["dependency", "build", str(chart_path)], timeout=timeout)
    if dependency_result.returncode != 0:
        return dependency_result
    return None


def run_helm_template(
    release: str,
    chart_path: Path,
    values_path: Path | None = None,
    set_values: dict[str, str] | None = None,
    skip_schema_validation: bool = False,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Render a Helm chart after ensuring chart dependencies are available.

    E2E tests run inside a purpose-built test-runner image where vendored
    subcharts may not be present. Build dependencies from Chart.yaml before
    rendering so tests validate chart metadata instead of relying on stale
    checked-out artifacts.
    """
    dependency_result = _ensure_helm_chart_dependencies(chart_path, timeout=timeout)
    if dependency_result is not None:
        return dependency_result

    args = ["template", release, str(chart_path)]
    if skip_schema_validation:
        args.append("--skip-schema-validation")
    if values_path is not None:
        args.extend(["-f", str(values_path)])
    if set_values:
        for key, value in set_values.items():
            args.extend(["--set", f"{key}={value}"])
    return run_helm(args, timeout=timeout)


def get_pod_uid(label_selector: str, namespace: str) -> str | None:
    """Get the UID of the first pod matching the selector.

    Note: assumes a single-replica deployment. For multi-replica workloads,
    this returns only ``items[0]`` and may miss additional pods.

    Args:
        label_selector: K8s label selector string.
        namespace: K8s namespace to query.

    Returns:
        Pod UID string, or None if no pod found or kubectl fails.
    """
    try:
        result = run_kubectl(
            [
                "get",
                "pods",
                "-l",
                label_selector,
                "-o",
                "jsonpath={.items[0].metadata.uid}",
            ],
            namespace=namespace,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    uid = result.stdout.strip()
    return uid if uid else None


def check_pod_ready(label_selector: str, namespace: str) -> bool:
    """Check if pods matching selector are Ready.

    Args:
        label_selector: K8s label selector string.
        namespace: K8s namespace to query.

    Returns:
        True if all matching pods are Ready. False on kubectl failure or timeout.
    """
    try:
        result = run_kubectl(
            [
                "get",
                "pods",
                "-l",
                label_selector,
                "-o",
                "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}",
            ],
            namespace=namespace,
        )
    except subprocess.TimeoutExpired:
        return False
    if result.returncode != 0:
        return False
    statuses = result.stdout.strip().split()
    return bool(statuses and all(s == "True" for s in statuses))


def assert_pod_recovery(
    label_selector: str,
    service_name: str,
    namespace: str,
    timeout: float = 30.0,
) -> PodRecoveryResult:
    """Delete a pod and assert that K8s replaces it with a new one.

    Uses UID-change detection instead of downtime polling. This is
    deterministic -- pod replacement always produces a new UID, regardless
    of how fast the replacement happens.

    Args:
        label_selector: K8s label selector for the pod.
        service_name: Human-readable service name for error messages.
        namespace: K8s namespace containing the pod.
        timeout: Maximum seconds to wait for recovery (default 30.0).

    Returns:
        PodRecoveryResult with original_uid, new_uid, and recovery_seconds.

    Raises:
        PodRecoveryError: If pod is not found, deletion fails, or recovery
            times out.
    """
    # 1. Record original pod UID
    original_uid = get_pod_uid(label_selector, namespace=namespace)
    if not original_uid:
        raise PodRecoveryError(
            f"{service_name} pod not found before deletion "
            f"(selector: {label_selector}). "
            f"Check: kubectl get pods -n {namespace} -l {label_selector}"
        )

    # 2. Delete the pod (timer includes delete + recovery for total wall-clock)
    start = time.monotonic()
    result = run_kubectl(
        [
            "delete",
            "pod",
            "-l",
            label_selector,
            "--grace-period=0",
            "--force",
        ],
        namespace=namespace,
        timeout=30,
    )
    if result.returncode != 0:
        stderr_snippet = (result.stderr or "")[:500]
        raise PodRecoveryError(f"Failed to delete {service_name} pod: {stderr_snippet}")

    # 3. Wait for new pod with different UID to become Ready
    def _pod_replaced_and_ready() -> bool:
        new = get_pod_uid(label_selector, namespace=namespace)
        if not new or new == original_uid:
            return False
        return check_pod_ready(label_selector, namespace=namespace)

    recovered = wait_for_condition(
        _pod_replaced_and_ready,
        timeout=timeout,
        interval=1.0,
        description=f"{service_name} pod replacement (UID != {original_uid[:8]})",
        raise_on_timeout=False,
    )

    recovery_seconds = time.monotonic() - start

    if not recovered:
        raise PodRecoveryError(
            f"{service_name} pod recovery timeout after {timeout}s. "
            f"Original UID: {original_uid[:8]}. "
            f"Check: kubectl get pods -n {namespace} -l {label_selector}"
        )

    # 4. Get the new UID
    new_uid = get_pod_uid(label_selector, namespace=namespace)
    if new_uid is None:
        raise PodRecoveryError(f"{service_name} new pod UID is None after recovery")

    logger.info(
        "%s pod replaced: %s -> %s in %.1fs",
        service_name,
        original_uid[:8],
        new_uid[:8],
        recovery_seconds,
    )

    return PodRecoveryResult(
        original_uid=original_uid,
        new_uid=new_uid,
        recovery_seconds=recovery_seconds,
    )
