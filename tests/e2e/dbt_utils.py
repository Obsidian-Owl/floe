"""Shared dbt CLI utilities for E2E tests.

Extracted from conftest.py to avoid the double-import anti-pattern
that occurs when test modules explicitly import from conftest.py
(pytest auto-discovers conftest, and a direct import loads it again).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_dbt(
    args: list[str],
    project_dir: Path,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    """Run a dbt command in the specified project directory.

    Single E2E dbt runner.  Uses ``check=False`` so that **callers**
    control error handling -- no dead-code assertions, no hidden
    CalledProcessError surprises.

    Both ``--project-dir`` and ``--profiles-dir`` point to *project_dir*
    because the ``dbt_e2e_profile`` fixture writes profiles.yml there.

    Args:
        args: dbt sub-command and flags (e.g. ``["seed"]``, ``["run"]``).
        project_dir: Path to the dbt project directory.
        timeout: Command timeout in seconds.  Defaults to 120.

    Returns:
        Completed process result.  Callers must check ``returncode``.
    """
    # Auto-add --full-refresh for seed commands: Iceberg tables persist
    # across test runs and prior snapshots may reference deleted data files
    # (HTTP 404 on stale parquet), causing incremental seed to fail.
    if args and args[0] == "seed" and "--full-refresh" not in args:
        args = [*args, "--full-refresh"]

    return subprocess.run(
        [
            "dbt",
            *args,
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(project_dir),
        ],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
