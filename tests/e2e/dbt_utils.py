"""Shared dbt CLI utilities for E2E tests.

Extracted from conftest.py to avoid the double-import anti-pattern
that occurs when test modules explicitly import from conftest.py
(pytest auto-discovers conftest, and a direct import loads it again).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3

from testing.fixtures.credentials import get_minio_credentials, get_polaris_credentials
from testing.fixtures.services import ServiceEndpoint

try:
    from pyiceberg.exceptions import NoSuchNamespaceError as PyIcebergNoSuchNamespaceError
except ImportError:
    PyIcebergNoSuchNamespaceError = None

logger = logging.getLogger(__name__)

# Session-scoped catalog cache — persists across calls within a single
# pytest session to avoid repeated OAuth. Cleared on process exit.
_catalog_cache: dict[str, Any] = {}


class NamespaceResetError(RuntimeError):
    """Raised when an Iceberg namespace cannot be reset to an empty state."""


def _clear_catalog_cache() -> None:
    """Drop cached Polaris catalog state so each reset can re-auth cleanly."""
    _catalog_cache.clear()


def _get_polaris_catalog(*, fresh: bool = False) -> Any:
    """Get or create a cached PyIceberg REST catalog for Polaris.

    Returns:
        PyIceberg catalog instance, or None if unavailable.
    """
    if fresh:
        _clear_catalog_cache()

    if "catalog" in _catalog_cache:
        return _catalog_cache["catalog"]

    try:
        from pyiceberg import catalog as pyiceberg_catalog
    except ImportError:
        _catalog_cache["catalog"] = None
        return None

    polaris_url = os.environ.get("POLARIS_URI", f"{ServiceEndpoint('polaris').url}/api/catalog")
    _polaris_id, _polaris_secret = get_polaris_credentials()
    default_cred = f"{_polaris_id}:{_polaris_secret}"  # pragma: allowlist secret
    _minio_access, _minio_secret = get_minio_credentials()

    try:
        catalog = pyiceberg_catalog.load_catalog(
            "polaris",
            **{
                "type": "rest",
                "uri": polaris_url,
                "credential": os.environ.get("POLARIS_CREDENTIAL", default_cred),
                "scope": "PRINCIPAL_ROLE:ALL",
                "warehouse": os.environ.get("POLARIS_WAREHOUSE", "floe-e2e"),
                "s3.endpoint": os.environ.get("MINIO_ENDPOINT", ServiceEndpoint("minio").url),
                "s3.access-key-id": os.environ.get(  # pragma: allowlist secret
                    "AWS_ACCESS_KEY_ID", _minio_access
                ),
                "s3.secret-access-key": os.environ.get(  # pragma: allowlist secret
                    "AWS_SECRET_ACCESS_KEY", _minio_secret
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


def _delete_s3_prefix(
    s3_client: Any,
    bucket: str,
    prefix: str,
) -> int:
    """Delete all S3 objects under a prefix via boto3.

    Args:
        s3_client: A boto3 S3 client instance.
        bucket: S3 bucket name.
        prefix: Object key prefix to delete under.

    Returns:
        Number of objects deleted.
    """
    deleted = 0
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        contents = page.get("Contents", [])
        if not contents:
            continue
        objects = [{"Key": obj["Key"]} for obj in contents]
        s3_client.delete_objects(Bucket=bucket, Delete={"Objects": objects, "Quiet": True})
        deleted += len(objects)
    return deleted


def _purge_iceberg_namespace(
    namespace: str,
    verify_empty: bool = False,
    retries: int = 3,
) -> None:
    """Purge all Iceberg tables in a namespace and delete their S3 data.

    Uses ``purge_table`` (which removes both catalog metadata and data files)
    then performs an explicit S3 object sweep via the MinIO-compatible
    ListObjectsV2 + DeleteObjects APIs.  This ensures stale Parquet files
    cannot interfere with subsequent dbt runs that use DuckDB's Iceberg
    extension, which does not support ``DROP TABLE CASCADE``.

    Silently does nothing if the catalog is unreachable or the namespace
    doesn't exist — dbt will create everything from scratch.

    Args:
        namespace: Polaris namespace to purge (e.g. ``customer_360_raw``).
        verify_empty: Whether to verify the namespace is empty after purge.
        retries: Number of verification attempts when ``verify_empty`` is true.
    """
    catalog = _get_polaris_catalog(fresh=True)
    if catalog is not None:
        # Collect S3 config from environment (same defaults as _get_polaris_catalog).
        s3_endpoint = os.environ.get("MINIO_ENDPOINT", ServiceEndpoint("minio").url)
        access_key, secret_key = get_minio_credentials()

        try:
            tables = catalog.list_tables(namespace)
            for table_id in tables:
                fqn = f"{table_id[0]}.{table_id[1]}"

                # Step 1: read table location BEFORE purge (purge removes metadata).
                location: str | None = None
                try:
                    table = catalog.load_table(fqn)
                    location = table.metadata.location  # e.g. s3://warehouse/ns1/t1
                except Exception as exc:
                    logger.warning(
                        "Could not load table %s for S3 location: %s",
                        fqn,
                        type(exc).__name__,
                    )

                # Step 2: purge via catalog (removes metadata + signals data removal)
                try:
                    catalog.purge_table(fqn)
                    logger.info("Purged Iceberg table %s", fqn)
                except Exception as exc:
                    logger.warning("Could not purge table %s: %s", fqn, type(exc).__name__)

                # Step 3: sweep S3 objects under the table's data prefix via boto3.
                # boto3 handles AWS Signature V4 required by MinIO.
                if location is not None:
                    try:
                        parsed = urlparse(location)
                        bucket: str = parsed.netloc
                        prefix: str = parsed.path.lstrip("/")

                        s3_client = boto3.client(
                            "s3",
                            endpoint_url=s3_endpoint,
                            aws_access_key_id=access_key,
                            aws_secret_access_key=secret_key,
                            region_name=os.environ.get("AWS_REGION", "us-east-1"),
                        )
                        deleted = _delete_s3_prefix(s3_client, bucket, prefix)
                        logger.info("Deleted %d S3 objects under %s", deleted, location)
                    except Exception as exc:
                        logger.warning(
                            "S3 cleanup failed for table %s: %s",
                            fqn,
                            type(exc).__name__,
                        )

            # Drop the namespace itself so dbt starts completely fresh.
            # DuckDB's Iceberg extension cannot DROP TABLE CASCADE, so stale
            # namespace metadata causes "Not implemented" errors on re-run.
            try:
                catalog.drop_namespace(namespace)
                logger.info("Dropped namespace %s", namespace)
            except Exception as exc:
                logger.warning(
                    "Could not drop namespace %s: %s",
                    namespace,
                    type(exc).__name__,
                )
        except Exception as exc:
            logger.debug("Namespace purge skipped for %s: %s", namespace, exc)
            if not verify_empty:
                return
    elif not verify_empty:
        return

    if not verify_empty:
        return

    remaining: Any = []
    failure_reason = "verification did not complete"
    for attempt in range(1, retries + 1):
        fresh_catalog = _get_polaris_catalog(fresh=True)
        if fresh_catalog is None:
            failure_reason = "verification catalog unavailable"
            logger.warning(
                "Could not verify namespace %s reset on attempt %d/%d: catalog unavailable",
                namespace,
                attempt,
                retries,
            )
            continue

        try:
            remaining = fresh_catalog.list_tables(namespace)
        except Exception as exc:
            if PyIcebergNoSuchNamespaceError is not None and isinstance(
                exc, PyIcebergNoSuchNamespaceError
            ):
                return
            failure_reason = f"verification failed: {type(exc).__name__}"
            logger.warning(
                "Could not verify namespace %s reset on attempt %d/%d: %s",
                namespace,
                attempt,
                retries,
                type(exc).__name__,
            )
            continue

        if not remaining:
            return

        failure_reason = f"remaining tables={remaining}"
        logger.warning(
            "Namespace %s still contains tables on attempt %d/%d: %s",
            namespace,
            attempt,
            retries,
            remaining,
        )

    raise NamespaceResetError(
        f"Namespace reset incomplete for {namespace}: {failure_reason}"
    )


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
        _purge_iceberg_namespace(f"{product_name}_raw", verify_empty=True)
    elif args and args[0] == "run":
        # Purge model namespace only — preserve seed tables as sources
        product_name = project_dir.name.replace("-", "_")
        _purge_iceberg_namespace(product_name, verify_empty=True)

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
