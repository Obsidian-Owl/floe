"""Helm release recovery utilities for E2E tests.

Provides shared logic for detecting and recovering from stuck Helm release
states (pending-upgrade, pending-install, pending-rollback, failed).

Used by:
    - tests/e2e/conftest.py (session-scoped autouse fixture)
    - tests/e2e/test_helm_upgrade_e2e.py (pre-test recovery)
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

# Helm release states that indicate a stuck release requiring recovery
STUCK_STATES = ("pending-upgrade", "pending-install", "pending-rollback", "failed")

# Default rollback timeout
DEFAULT_ROLLBACK_TIMEOUT = "5m"


def _run_helm(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess[str]:
    """Run helm command with timeout.

    Args:
        args: helm arguments.
        timeout: Command timeout in seconds.

    Returns:
        Completed process result.
    """
    return subprocess.run(
        ["helm"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def parse_helm_status(stdout: str) -> dict[str, Any]:
    """Parse JSON output from ``helm status -o json``.

    Args:
        stdout: Raw stdout from helm status command.

    Returns:
        Parsed JSON as a dictionary.

    Raises:
        ValueError: If stdout is empty or not valid JSON.
    """
    stripped = stdout.strip()
    if not stripped:
        msg = "helm status returned empty output"
        raise ValueError(msg)
    try:
        result: dict[str, Any] = json.loads(stripped)
    except json.JSONDecodeError as exc:
        preview = stripped[:200]
        msg = f"helm status returned invalid JSON: {exc}\nOutput preview: {preview}"
        raise ValueError(msg) from exc
    return result


def recover_stuck_helm_release(
    release: str,
    namespace: str,
    *,
    rollback_timeout: str = DEFAULT_ROLLBACK_TIMEOUT,
    helm_runner: Any = None,
) -> bool:
    """Detect and recover from stuck Helm release states.

    Checks for pending-upgrade, pending-install, pending-rollback, and failed
    states. Scans ``helm history`` to find the most recent revision with status
    "deployed" and rolls back to that revision.

    Args:
        release: Helm release name.
        namespace: K8s namespace.
        rollback_timeout: Timeout for helm rollback (e.g., "5m", "3m").
        helm_runner: Callable that runs helm commands. Signature:
            ``(args: list[str]) -> subprocess.CompletedProcess[str]``.
            Defaults to the internal ``_run_helm`` helper.

    Returns:
        True if recovery was performed, False if release was healthy,
        did not exist, or no deployed revision was found in history.

    Raises:
        RuntimeError: If helm history or rollback fails after detecting stuck state.
        ValueError: If helm status output is not valid JSON.
    """
    run = helm_runner or _run_helm

    status_result = run(["status", release, "-n", namespace, "-o", "json"])
    if status_result.returncode != 0:
        # Release doesn't exist — nothing to recover
        return False

    current = parse_helm_status(status_result.stdout)
    release_status = current.get("info", {}).get("status", "")

    if release_status not in STUCK_STATES:
        return False

    # Flux delegation: try flux reconcile before falling back to Helm rollback
    flux_check = subprocess.run(
        ["kubectl", "get", "helmrelease", release, "-n", namespace],
        capture_output=True,
        text=True,
        check=False,
    )
    if flux_check.returncode == 0 and shutil.which("flux") is not None:
        reconcile_result = subprocess.run(
            ["flux", "reconcile", "helmrelease", release, "-n", namespace],
            capture_output=True,
            text=True,
            check=False,
        )
        if reconcile_result.returncode == 0:
            return True
        logger.warning(
            "flux reconcile helmrelease failed: cmd=%s returncode=%d stderr=%s",
            ["flux", "reconcile", "helmrelease", release, "-n", namespace],
            reconcile_result.returncode,
            reconcile_result.stderr,
        )
    # Fall through to existing Helm rollback logic below...

    current_revision = current.get("version", 1)
    if not isinstance(current_revision, int):
        msg = (
            f"Unexpected 'version' type in helm status: "
            f"{type(current_revision).__name__} (value: {current_revision!r}). "
            f"Expected int."
        )
        raise ValueError(msg)

    # Scan helm history to find the most recent deployed revision
    history_result = run(["history", release, "-n", namespace, "-o", "json"])
    if history_result.returncode != 0:
        msg = (
            f"Helm history failed for release '{release}': {history_result.stderr}\n"
            f"Cannot determine last known good revision. Manual intervention required:\n"
            f"  helm history {release} -n {namespace}"
        )
        raise RuntimeError(msg)

    history_entries: list[dict[str, object]] = json.loads(history_result.stdout)
    rollback_revision: int | None = None
    for entry in reversed(history_entries):
        if entry.get("status") == "deployed":
            rev = entry.get("revision")
            if isinstance(rev, int):
                rollback_revision = rev
                break

    if rollback_revision is None:
        print(
            f"WARNING: Helm release '{release}' stuck in '{release_status}' but "
            f"no deployed revision found in history. Cannot auto-recover.\n"
            f"Manual intervention required: helm uninstall {release} -n {namespace}"
        )
        return False

    print(
        f"WARNING: Helm release '{release}' in '{release_status}' state. "
        f"Rolling back to revision {rollback_revision}..."
    )

    rollback_result = run(
        [
            "rollback",
            release,
            str(rollback_revision),
            "-n",
            namespace,
            "--wait",
            "--timeout",
            rollback_timeout,
        ],
    )
    if rollback_result.returncode != 0:
        msg = (
            f"Helm rollback failed: {rollback_result.stderr}\n"
            f"Release stuck in '{release_status}'. Manual intervention required:\n"
            f"  helm rollback {release} {rollback_revision} -n {namespace}\n"
            f"  # or: helm uninstall {release} -n {namespace} && re-deploy"
        )
        raise RuntimeError(msg)

    print(f"Recovery complete: rolled back to revision {rollback_revision}")
    return True
