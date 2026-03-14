"""Shared dbt CLI utilities for E2E tests.

Extracted from conftest.py to avoid the double-import anti-pattern
that occurs when test modules explicitly import from conftest.py
(pytest auto-discovers conftest, and a direct import loads it again).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _purge_seed_namespace(project_dir: Path) -> None:
    """Drop existing Iceberg seed tables so ``dbt seed`` starts clean.

    DuckDB's Iceberg extension does not support ``DROP TABLE CASCADE``,
    which ``dbt seed --full-refresh`` emits.  Instead, we use PyIceberg
    to drop each table individually before dbt runs.  This also handles
    stale metadata from prior runs (HTTP 404 on deleted parquet files).

    Silently does nothing if PyIceberg is not installed or the catalog
    is unreachable — the seed will still attempt to create the tables.

    Args:
        project_dir: Path to the dbt project containing dbt_project.yml.
    """
    import os

    try:
        from pyiceberg import catalog as pyiceberg_catalog
    except ImportError:
        return

    # Derive namespace: {product_name}_raw  (e.g. customer_360_raw)
    product_name = project_dir.name.replace("-", "_")
    namespace = f"{product_name}_raw"

    polaris_url = os.environ.get("POLARIS_URL", "http://localhost:8181")
    default_cred = "demo-admin:demo-secret"  # pragma: allowlist secret

    try:
        catalog = pyiceberg_catalog.load_catalog(
            "polaris",
            **{
                "type": "rest",
                "uri": f"{polaris_url}/api/catalog",
                "credential": os.environ.get("POLARIS_CREDENTIAL", default_cred),
                "scope": "PRINCIPAL_ROLE:ALL",
                "warehouse": os.environ.get("POLARIS_WAREHOUSE", "floe-e2e"),
                "s3.endpoint": os.environ.get("MINIO_URL", "http://localhost:9000"),
                "s3.access-key-id": os.environ.get(  # pragma: allowlist secret
                    "AWS_ACCESS_KEY_ID", "minioadmin"
                ),
                "s3.secret-access-key": os.environ.get(  # pragma: allowlist secret
                    "AWS_SECRET_ACCESS_KEY", "minioadmin123"
                ),
                "s3.region": os.environ.get("AWS_REGION", "us-east-1"),
                "s3.path-style-access": "true",
            },
        )

        tables = catalog.list_tables(namespace)
        for table_id in tables:
            fqn = f"{table_id[0]}.{table_id[1]}"
            try:
                catalog.drop_table(fqn)
                logger.info("Dropped stale seed table %s", fqn)
            except Exception:
                logger.debug("Could not drop table %s (may not exist)", fqn)
    except Exception as exc:
        # Namespace doesn't exist yet or catalog unreachable — fine,
        # dbt seed will create everything from scratch.
        logger.debug("Seed namespace purge skipped: %s", exc)


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

    For ``seed`` commands, existing Iceberg tables in the seed namespace
    are dropped via PyIceberg first, because DuckDB's Iceberg extension
    does not support ``DROP TABLE CASCADE`` (required by ``--full-refresh``).

    Args:
        args: dbt sub-command and flags (e.g. ``["seed"]``, ``["run"]``).
        project_dir: Path to the dbt project directory.
        timeout: Command timeout in seconds.  Defaults to 120.

    Returns:
        Completed process result.  Callers must check ``returncode``.
    """
    # Purge existing seed tables before seeding: Iceberg tables persist
    # across test runs, and prior snapshots may reference deleted data files.
    # We can't use --full-refresh because DuckDB's Iceberg extension does
    # not support DROP TABLE CASCADE.
    if args and args[0] == "seed":
        _purge_seed_namespace(project_dir)

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
