"""Shared dbt CLI utilities for E2E tests.

Extracted from conftest.py to avoid the double-import anti-pattern
that occurs when test modules explicitly import from conftest.py
(pytest auto-discovers conftest, and a direct import loads it again).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from testing.fixtures.services import ServiceEndpoint

logger = logging.getLogger(__name__)

# Session-scoped catalog cache — persists across calls within a single
# pytest session to avoid repeated OAuth. Cleared on process exit.
_catalog_cache: dict[str, Any] = {}


def _get_polaris_catalog() -> Any:
    """Get or create a cached PyIceberg REST catalog for Polaris.

    Returns:
        PyIceberg catalog instance, or None if unavailable.
    """
    import os

    if "catalog" in _catalog_cache:
        return _catalog_cache["catalog"]

    try:
        from pyiceberg import catalog as pyiceberg_catalog
    except ImportError:
        _catalog_cache["catalog"] = None
        return None

    polaris_url = os.environ.get("POLARIS_URL", ServiceEndpoint("polaris").url)
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
                "s3.endpoint": os.environ.get("MINIO_URL", ServiceEndpoint("minio").url),
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
        _catalog_cache["catalog"] = catalog
        return catalog
    except Exception as exc:
        logger.debug("Could not connect to Polaris catalog: %s", exc)
        _catalog_cache["catalog"] = None
        return None


def _purge_iceberg_namespace(namespace: str) -> None:
    """Drop all Iceberg tables in a namespace via PyIceberg.

    DuckDB's Iceberg extension does not support ``DROP TABLE CASCADE``,
    which dbt emits for ``--full-refresh`` and ``materialized='table'``
    re-runs.  We drop tables individually via PyIceberg before dbt runs.

    Silently does nothing if the catalog is unreachable or the namespace
    doesn't exist — dbt will create everything from scratch.

    Args:
        namespace: Polaris namespace to purge (e.g. ``customer_360_raw``).
    """
    catalog = _get_polaris_catalog()
    if catalog is None:
        return

    try:
        tables = catalog.list_tables(namespace)
        for table_id in tables:
            fqn = f"{table_id[0]}.{table_id[1]}"
            try:
                catalog.drop_table(fqn)
                logger.info("Dropped stale Iceberg table %s", fqn)
            except Exception:
                logger.warning("Could not drop table %s (may not exist)", fqn)
        # Drop the namespace itself so dbt starts completely fresh.
        # DuckDB's Iceberg extension cannot DROP TABLE CASCADE, so stale
        # namespace metadata causes "Not implemented" errors on re-run.
        try:
            catalog.drop_namespace(namespace)
            logger.info("Dropped namespace %s", namespace)
        except Exception:
            logger.debug("Could not drop namespace %s (may not exist)", namespace)
    except Exception as exc:
        logger.debug("Namespace purge skipped for %s: %s", namespace, exc)


def run_dbt(
    args: list[str],
    project_dir: Path,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    """Run a dbt command in the specified project directory.

    Single E2E dbt runner.  Uses ``check=False`` so that **callers**
    control error handling -- no dead-code assertions, no hidden
    CalledProcessError surprises.

    ``--profiles-dir`` is resolved automatically: if a generated profiles
    directory exists at ``tests/e2e/generated_profiles/<product>/``, it is
    used; otherwise ``project_dir`` is used as a fallback.  The
    ``dbt_e2e_profile`` fixture writes profiles to the generated directory.

    For ``seed`` and ``run`` commands, existing Iceberg tables are
    dropped via PyIceberg first, because DuckDB's Iceberg extension
    does not support ``DROP TABLE CASCADE``.

    Args:
        args: dbt sub-command and flags (e.g. ``["seed"]``, ``["run"]``).
        project_dir: Path to the dbt project directory.
        timeout: Command timeout in seconds.  Defaults to 120.

    Returns:
        Completed process result.  Callers must check ``returncode``.
    """
    # Purge existing Iceberg tables before seed/run: DuckDB's Iceberg
    # extension does not support DROP TABLE CASCADE, and tables persist
    # across test runs with potentially stale metadata.
    if args and args[0] == "seed":
        # Purge seed namespace only — model tables may depend on seeds
        product_name = project_dir.name.replace("-", "_")
        _purge_iceberg_namespace(f"{product_name}_raw")
    elif args and args[0] == "run":
        # Purge model namespace only — preserve seed tables as sources
        product_name = project_dir.name.replace("-", "_")
        _purge_iceberg_namespace(product_name)

    # Use the venv's dbt to avoid PATH conflicts with dbt-fusion or other
    # system-installed dbt binaries that may not support the duckdb adapter.
    venv_bin = Path(sys.executable).parent
    dbt_bin = str(venv_bin / "dbt")

    # Profile isolation: prefer generated profiles directory (written by the
    # dbt_e2e_profile fixture) over demo project profiles.  This prevents
    # E2E test profiles from overwriting the demo's checked-in profiles.yml,
    # which would break concurrent ``make demo`` runs.
    generated_profiles = Path(__file__).parent / "generated_profiles" / project_dir.name
    profiles_dir = str(generated_profiles) if generated_profiles.is_dir() else str(project_dir)

    return subprocess.run(
        [
            dbt_bin,
            *args,
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            profiles_dir,
        ],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
