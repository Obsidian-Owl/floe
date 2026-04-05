"""Shared dbt CLI utilities for E2E tests.

Extracted from conftest.py to avoid the double-import anti-pattern
that occurs when test modules explicitly import from conftest.py
(pytest auto-discovers conftest, and a direct import loads it again).
"""

from __future__ import annotations

import logging
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from testing.fixtures.credentials import get_minio_credentials, get_polaris_credentials
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
    _polaris_id, _polaris_secret = get_polaris_credentials()
    default_cred = f"{_polaris_id}:{_polaris_secret}"  # pragma: allowlist secret
    _minio_access, _minio_secret = get_minio_credentials()

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


def _delete_s3_objects(
    client: httpx.Client,
    endpoint: str,
    bucket: str,
    keys: list[str],
) -> None:
    """Delete a batch of S3 objects via the S3 DeleteObjects API.

    Args:
        client: An active httpx.Client instance (with auth configured).
        endpoint: MinIO/S3 base URL (e.g. ``http://localhost:9000``).
        bucket: S3 bucket name.
        keys: List of object keys to delete.
    """
    if not keys:
        return

    objects_xml = "".join(f"<Object><Key>{k}</Key></Object>" for k in keys)
    body = (
        f'<?xml version="1.0" encoding="UTF-8"?><Delete><Quiet>true</Quiet>{objects_xml}</Delete>'
    )
    url = f"{endpoint.rstrip('/')}/{bucket}"
    try:
        resp = client.post(url, params={"delete": ""}, content=body.encode())
        if resp.status_code not in (200, 204):
            logger.warning(
                "S3 DeleteObjects returned %s for bucket %s",
                resp.status_code,
                bucket,
            )
    except Exception as exc:
        logger.warning("S3 DeleteObjects failed for bucket %s: %s", bucket, type(exc).__name__)


def _purge_iceberg_namespace(namespace: str) -> None:
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
    """
    catalog = _get_polaris_catalog()
    if catalog is None:
        return

    # Collect S3 config from environment (same defaults as _get_polaris_catalog).
    import os

    s3_endpoint = os.environ.get("MINIO_URL", ServiceEndpoint("minio").url)
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")  # pragma: allowlist secret
    secret_key = os.environ.get(
        "AWS_SECRET_ACCESS_KEY", "minioadmin123"
    )  # pragma: allowlist secret

    try:
        tables = catalog.list_tables(namespace)
        for table_id in tables:
            fqn = f"{table_id[0]}.{table_id[1]}"
            # Step 1: purge via catalog (removes metadata + signals data removal)
            try:
                catalog.purge_table(fqn)
                logger.info("Purged Iceberg table %s", fqn)
            except Exception as exc:
                logger.warning("Could not purge table %s: %s", fqn, type(exc).__name__)

            # Step 2: sweep S3 objects under the table's data prefix via httpx.
            # We use IsTruncated/ContinuationToken for paginated listing.
            try:
                table = catalog.load_table(fqn)
                location: str = table.metadata.location  # e.g. s3://warehouse/ns1/t1
                parsed = urlparse(location)
                bucket: str = parsed.netloc
                prefix: str = parsed.path.lstrip("/")

                list_url = f"{s3_endpoint.rstrip('/')}/{bucket}"
                params: dict[str, str] = {
                    "list-type": "2",
                    "prefix": prefix,
                }

                with httpx.Client(auth=httpx.BasicAuth(access_key, secret_key)) as client:
                    while True:
                        resp = client.get(list_url, params=params)
                        root = ET.fromstring(resp.text)
                        # Collect keys from <Contents><Key>…</Key></Contents>
                        keys = [el.text or "" for el in root.iter("Key") if el.text]
                        if keys:
                            _delete_s3_objects(client, s3_endpoint, bucket, keys)

                        # Pagination: check IsTruncated / NextContinuationToken
                        is_truncated_el = root.find("IsTruncated")
                        is_truncated = (
                            is_truncated_el is not None
                            and (is_truncated_el.text or "").lower() == "true"
                        )
                        if not is_truncated:
                            break
                        token_el = root.find("NextContinuationToken")
                        continuation_token = token_el.text if token_el is not None else None
                        if not continuation_token:
                            break
                        params = {
                            "list-type": "2",
                            "prefix": prefix,
                            "continuation-token": continuation_token,
                        }
                        logger.debug("S3 listing page continues with ContinuationToken for %s", fqn)

                logger.info("Deleted S3 objects under %s", location)
            except Exception as exc:
                logger.warning("S3 cleanup failed for table %s: %s", fqn, type(exc).__name__)

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
