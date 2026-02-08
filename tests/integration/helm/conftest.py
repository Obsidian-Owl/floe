"""Helm chart integration test fixtures.

This module provides pytest fixtures for Helm chart testing with Kind cluster.
Fixtures handle:
- Kind cluster availability verification
- Helm chart paths and dependencies
- Temporary namespace management
- Cleanup after tests

Example:
    def test_chart_install(kind_cluster, platform_chart_path, test_namespace):
        result = subprocess.run([
            "helm", "install", "test-release",
            str(platform_chart_path),
            "--namespace", test_namespace,
            "--wait", "--timeout", "5m"
        ])
        assert result.returncode == 0
"""

from __future__ import annotations

import subprocess
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import NoReturn

import pytest


def _fail(message: str) -> NoReturn:
    """Wrapper for pytest.fail with proper type annotation.

    Args:
        message: Failure message.

    Raises:
        pytest.fail: Always.
    """
    pytest.fail(message)
    raise AssertionError("Unreachable")  # For type checker


def _check_kind_cluster() -> bool:
    """Check if Kind cluster is available.

    Returns:
        True if Kind cluster is running and kubectl can connect.
    """
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_helm_available() -> bool:
    """Check if Helm CLI is available.

    Returns:
        True if helm command is available.
    """
    try:
        result = subprocess.run(
            ["helm", "version", "--short"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="session")
def kind_cluster() -> None:
    """Verify Kind cluster is available.

    Session-scoped fixture that fails fast if Kind cluster is not running.
    This ensures all Helm tests have a working cluster.

    Raises:
        pytest.fail: If Kind cluster is not available.
    """
    if not _check_kind_cluster():
        _fail(
            "Kind cluster is not available.\n"
            "Start the cluster with: make kind-up\n"
            "Or: kind create cluster --name floe-test"
        )


@pytest.fixture(scope="session")
def helm_available() -> None:
    """Verify Helm CLI is available.

    Session-scoped fixture that fails fast if Helm is not installed.

    Raises:
        pytest.fail: If Helm CLI is not available.
    """
    if not _check_helm_available():
        _fail("Helm CLI is not available.\nInstall Helm: https://helm.sh/docs/intro/install/")


@pytest.fixture(scope="session")
def charts_dir() -> Path:
    """Get the path to the charts directory.

    Returns:
        Path to the charts directory.

    Raises:
        pytest.fail: If charts directory does not exist.
    """
    # Find project root (contains charts/ directory)
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        charts_path = parent / "charts"
        if charts_path.exists() and charts_path.is_dir():
            return charts_path

    _fail("Could not find charts/ directory.\nEnsure you are running tests from the project root.")


@pytest.fixture(scope="session")
def platform_chart_path(charts_dir: Path) -> Path:
    """Get the path to the floe-platform chart.

    Args:
        charts_dir: Path to charts directory.

    Returns:
        Path to floe-platform chart.

    Raises:
        pytest.fail: If chart does not exist.
    """
    chart_path = charts_dir / "floe-platform"
    if not chart_path.exists():
        _fail(f"floe-platform chart not found at {chart_path}\nCreate the chart first.")
    return chart_path


@pytest.fixture(scope="session")
def jobs_chart_path(charts_dir: Path) -> Path:
    """Get the path to the floe-jobs chart.

    Args:
        charts_dir: Path to charts directory.

    Returns:
        Path to floe-jobs chart.

    Raises:
        pytest.fail: If chart does not exist.
    """
    chart_path = charts_dir / "floe-jobs"
    if not chart_path.exists():
        _fail(f"floe-jobs chart not found at {chart_path}\nCreate the chart first.")
    return chart_path


@pytest.fixture
def test_namespace(kind_cluster: None) -> Generator[str, None, None]:
    """Create a unique test namespace.

    Creates a namespace with a unique suffix for test isolation.
    Cleans up the namespace after the test completes.

    Args:
        kind_cluster: Ensures cluster is available (fixture dependency).

    Yields:
        Namespace name (e.g., "floe-test-abc12345").
    """
    _ = kind_cluster  # Used for fixture ordering
    namespace = f"floe-test-{uuid.uuid4().hex[:8]}"

    # Create namespace
    subprocess.run(
        ["kubectl", "create", "namespace", namespace],
        capture_output=True,
        check=True,
    )

    try:
        yield namespace
    finally:
        # Cleanup namespace (ignore errors if already deleted)
        subprocess.run(
            ["kubectl", "delete", "namespace", namespace, "--ignore-not-found"],
            capture_output=True,
            check=False,
        )


@pytest.fixture
def helm_release_name() -> str:
    """Generate a unique Helm release name.

    Returns:
        Release name (e.g., "test-abc12345").
    """
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def update_helm_dependencies(
    platform_chart_path: Path,
    helm_available: None,
) -> None:
    """Update Helm dependencies for the platform chart.

    Session-scoped fixture that runs `helm dependency update` once.
    This ensures subchart dependencies are available for template tests.

    Args:
        platform_chart_path: Path to platform chart.
        helm_available: Ensures Helm is available (fixture dependency).

    Raises:
        pytest.fail: If dependency update fails.
    """
    _ = helm_available  # Used for fixture ordering
    result = subprocess.run(
        ["helm", "dependency", "update", str(platform_chart_path)],
        capture_output=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode() if result.stderr else "Unknown error"
        _fail(
            f"Failed to update Helm dependencies:\n{stderr}\n"
            "Ensure you have internet access for subchart downloads."
        )
