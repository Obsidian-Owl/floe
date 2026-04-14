"""E2E test: _purge_iceberg_namespace cleans S3 data prefix (N→0 delta).

Covers salvage-branch-wrap-up AC-5: proves that calling
`_purge_iceberg_namespace(namespace)` on a populated Iceberg table causes
the corresponding S3 data prefix to go from N > 0 objects to 0 objects.

Why this test is hard to fake (see spec.md AC-5):
    - Pre-assertion `before_count > 0` defeats the "never-populated prefix"
      failure mode
    - N→0 delta defeats "silent exception swallow" — purge must actually
      delete objects to pass
    - Imports `_purge_iceberg_namespace` via importlib with a UNIQUE module
      name (`dbt_utils_e2e_ac5`) to avoid sys.modules collision and to
      guarantee a fresh `_catalog_cache` dict (B2 resolution / D-7)

Negative control: verified test FAILS with `catalog.purge_table(fqn)` line
commented out on 2026-04-08 against commit 767ff90 (documented in as-built
notes).
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from urllib.parse import urlparse

import boto3
import pyarrow as pa
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.polaris import PolarisConfig, create_polaris_catalog

# --- Import isolation (B2 / D-7) ---------------------------------------------
# Load dbt_utils.py under a UNIQUE module name to avoid sys.modules collision
# with any other importer of the same file. This guarantees our own
# `_catalog_cache` dict — no cross-test pollution.
_DBT_UTILS_PATH = Path(__file__).resolve().parents[1] / "dbt_utils.py"
assert _DBT_UTILS_PATH.exists(), f"dbt_utils.py not found at {_DBT_UTILS_PATH}"

_spec = importlib.util.spec_from_file_location(
    "dbt_utils_e2e_ac5",  # unique name — NOT "dbt_utils"
    _DBT_UTILS_PATH,
)
assert _spec is not None and _spec.loader is not None, (
    f"Failed to build import spec for {_DBT_UTILS_PATH}"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
# Defensive belt-and-braces — clear the cache even though the module instance
# is fresh. Catches accidental pre-population during module init.
_mod._catalog_cache.clear()


class TestIcebergPurgeE2E(IntegrationTestBase):
    """E2E: _purge_iceberg_namespace N→0 S3 delta (salvage-wrap-up AC-5)."""

    required_services = ["polaris", "minio"]

    @pytest.mark.requirement("salvage-wrap-up-AC-5")
    def test_purge_removes_s3_data_objects_n_to_zero(self) -> None:
        """Populate namespace with 10 rows, purge, verify S3 prefix emptied.

        Steps:
            1. Create unique namespace + table via fresh PyIceberg catalog
            2. Append 10 rows (ensures data files exist, not just metadata)
            3. List S3 under data prefix → before_count
            4. Assert before_count > 0
            5. Call _mod._purge_iceberg_namespace(namespace)
            6. List S3 under same prefix → after_count
            7. Assert before_count > 0 and after_count == 0 (N→0 delta)
        """
        self.check_infrastructure("polaris")
        self.check_infrastructure("minio")

        # Step 1: Create unique namespace and table
        uid = uuid.uuid4().hex[:12]
        ns_name = f"purge_probe_{uid}"
        table_name = f"probe_{uid}"
        fqn = f"{ns_name}.{table_name}"

        # Fresh catalog client — NOT _mod._get_polaris_catalog() — so test
        # setup is independent of the module under test.
        setup_catalog = create_polaris_catalog(PolarisConfig())
        setup_catalog.create_namespace(ns_name)

        from pyiceberg.schema import Schema
        from pyiceberg.types import IntegerType, NestedField, StringType

        schema = Schema(
            NestedField(field_id=1, name="id", field_type=IntegerType(), required=False),
            NestedField(field_id=2, name="value", field_type=StringType(), required=False),
        )
        table = setup_catalog.create_table(fqn, schema=schema)

        # Step 2: Append 10 rows — both metadata AND data files must exist
        data = pa.table(
            {
                "id": pa.array(list(range(10)), type=pa.int32()),
                "value": pa.array([f"row-{i}" for i in range(10)], type=pa.string()),
            }
        )
        table.append(data)
        table.refresh()
        assert table.current_snapshot() is not None, (
            f"Snapshot not committed for {fqn} — cannot proceed to purge assertion"
        )

        # Step 3: Resolve the S3 location and list objects under the prefix
        location: str = table.metadata.location
        parsed = urlparse(location)
        bucket: str = parsed.netloc
        prefix: str = parsed.path.lstrip("/")

        import os

        from testing.fixtures.credentials import get_minio_credentials
        from testing.fixtures.services import get_effective_host, get_effective_port

        access_key, secret_key = get_minio_credentials()
        minio_host = get_effective_host("minio")
        minio_port = get_effective_port("minio", default=9000)
        s3_endpoint = os.environ.get("MINIO_ENDPOINT", f"http://{minio_host}:{minio_port}")

        s3_client = boto3.client(
            "s3",
            endpoint_url=s3_endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )

        def _list_object_count(target_prefix: str) -> int:
            """Count S3 objects under a prefix via boto3 ListObjectsV2."""
            paginator = s3_client.get_paginator("list_objects_v2")
            count = 0
            for page in paginator.paginate(Bucket=bucket, Prefix=target_prefix):
                count += page.get("KeyCount", 0)
            return count

        before_count = _list_object_count(prefix)
        assert before_count > 0, (
            f"Pre-purge S3 prefix {prefix!r} has zero objects — "
            "table was never populated. Test cannot prove the N→0 delta."
        )

        # Step 5: Call the isolated module's _purge_iceberg_namespace
        _mod._purge_iceberg_namespace(ns_name)

        # Step 6: Re-list S3 objects under the same prefix
        after_count = _list_object_count(prefix)

        # Step 7: Combined N→0 assertion — single expression for report clarity
        assert before_count > 0 and after_count == 0, (
            f"S3 purge delta failed: before={before_count}, after={after_count} "
            f"(prefix={prefix!r}). Expected N>0 before, 0 after. "
            "If before==0 the test is too weak; if after>0 the purge did not "
            "actually delete objects."
        )


# Negative control: verified test FAILS with catalog.purge_table(fqn) commented
# out on 2026-04-08 against commit 767ff90. See plan.md As-Built Notes.
