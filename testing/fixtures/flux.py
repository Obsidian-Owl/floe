"""Flux v2 GitOps pytest fixtures for E2E tests.

Provides helpers to suspend and resume Flux HelmRelease reconciliation
during tests that perform direct Helm operations. All Flux interactions
use subprocess CLI calls -- no Flux-specific Python packages are imported,
so this module is importable on systems without Flux installed.

P56: All best-effort cleanup operations log failures rather than silencing
them with bare except/pass blocks.

Functions:
    is_flux_managed: Check whether a HelmRelease exists in the cluster.
    suspend_helmrelease: Suspend Flux reconciliation for a HelmRelease.
    resume_helmrelease: Resume Flux reconciliation for a HelmRelease.

Fixtures:
    flux_suspended: Suspend a HelmRelease for the duration of a test and
        resume it on teardown.

Example:
    @pytest.mark.usefixtures("flux_suspended")
    def test_helm_upgrade() -> None:
        ...
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

import pytest

logger = logging.getLogger(__name__)


def is_flux_managed(name: str, namespace: str) -> bool:
    """Check whether a Flux HelmRelease resource exists in the cluster.

    Runs ``kubectl get helmrelease {name} -n {namespace}`` with check=False
    and interprets the returncode. Returns True when the resource exists
    and is accessible, False in all other cases (CRD not installed, resource
    not found, API server unreachable).

    Args:
        name: Name of the HelmRelease resource.
        namespace: Kubernetes namespace to query.

    Returns:
        True if the HelmRelease exists, False otherwise.
    """
    result = subprocess.run(
        ["kubectl", "get", "helmrelease", name, "-n", namespace],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _patch_helmrelease_suspend(name: str, namespace: str, suspend: bool) -> bool:
    """Patch Flux HelmRelease ``spec.suspend`` using kubectl.

    Args:
        name: Name of the HelmRelease to patch.
        namespace: Kubernetes namespace containing the HelmRelease.
        suspend: Desired ``spec.suspend`` value.

    Returns:
        True if the patch command succeeded, False otherwise.
    """
    action = "suspend" if suspend else "resume"
    payload = '{"spec":{"suspend":true}}' if suspend else '{"spec":{"suspend":false}}'
    cmd = [
        "kubectl",
        "patch",
        "helmrelease",
        name,
        "-n",
        namespace,
        "--type=merge",
        "-p",
        payload,
    ]
    logger.info(
        "flux CLI not found on PATH; using kubectl patch to %s HelmRelease %s/%s",
        action,
        namespace,
        name,
    )
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        logger.warning(
            "kubectl patch helmrelease failed: cmd=%s returncode=%d stderr=%s",
            cmd,
            result.returncode,
            result.stderr,
        )
        return False

    return True


def suspend_helmrelease(name: str, namespace: str) -> bool:
    """Suspend Flux reconciliation for a HelmRelease.

    First checks that the ``flux`` CLI is available on PATH via
    ``shutil.which``. If the CLI is not found, falls back to patching
    ``spec.suspend=true`` through ``kubectl`` so in-cluster test runners do
    not need to ship the Flux CLI binary.

    On non-zero returncode, logs a warning that includes the command,
    returncode, and stderr (P56 compliance) and returns False.

    Args:
        name: Name of the HelmRelease to suspend.
        namespace: Kubernetes namespace containing the HelmRelease.

    Returns:
        True if the suspend command succeeded, False otherwise.
    """
    if shutil.which("flux") is None:
        return _patch_helmrelease_suspend(name, namespace, suspend=True)

    cmd = ["flux", "suspend", "helmrelease", name, "-n", namespace]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        logger.warning(
            "flux suspend helmrelease failed: cmd=%s returncode=%d stderr=%s",
            cmd,
            result.returncode,
            result.stderr,
        )
        return False

    return True


def resume_helmrelease(name: str, namespace: str) -> bool:
    """Resume Flux reconciliation for a HelmRelease.

    Best-effort finalizer operation: never raises, always returns a bool.
    On non-zero returncode, logs a warning that includes the command,
    returncode, and stderr (P56 compliance).

    Args:
        name: Name of the HelmRelease to resume.
        namespace: Kubernetes namespace containing the HelmRelease.

    Returns:
        True if the resume command succeeded, False otherwise.
    """
    if shutil.which("flux") is None:
        return _patch_helmrelease_suspend(name, namespace, suspend=False)

    cmd = ["flux", "resume", "helmrelease", name, "-n", namespace]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        logger.warning(
            "flux resume helmrelease failed: cmd=%s returncode=%d stderr=%s",
            cmd,
            result.returncode,
            result.stderr,
        )
        return False

    return True


def _flux_suspended_impl(request: pytest.FixtureRequest) -> None:
    """Implementation of flux_suspended — callable directly in unit tests.

    Reads the release name from the ``FLOE_RELEASE_NAME`` environment variable
    (default: ``floe-platform``) and the namespace from ``FLOE_E2E_NAMESPACE``
    (default: ``floe-test``).

    If the release is not Flux-managed (``is_flux_managed`` returns False),
    the function returns immediately without suspending or registering a
    finalizer. Likewise, if ``suspend_helmrelease`` returns False (flux CLI
    missing or command failed), no finalizer is registered because there is
    nothing to resume.

    Args:
        request: pytest FixtureRequest providing addfinalizer.

    Returns:
        None. Side effects only.
    """
    name = os.environ.get("FLOE_RELEASE_NAME", "floe-platform")
    namespace = os.environ.get("FLOE_E2E_NAMESPACE", "floe-test")

    if not is_flux_managed(name, namespace):
        return None

    suspended = suspend_helmrelease(name, namespace)
    if not suspended:
        return None

    request.addfinalizer(lambda: resume_helmrelease(name, namespace))
    return None


@pytest.fixture(scope="module")
def flux_suspended(request: pytest.FixtureRequest) -> None:
    """Suspend a Flux HelmRelease for the test module and resume on teardown.

    Pytest fixture wrapper around ``_flux_suspended_impl``. The split allows
    unit tests to call the implementation directly (pytest 9 blocks direct
    calls to ``@pytest.fixture``-decorated functions).

    Args:
        request: pytest FixtureRequest providing addfinalizer.

    Returns:
        None. Side effects only.
    """
    _flux_suspended_impl(request)
