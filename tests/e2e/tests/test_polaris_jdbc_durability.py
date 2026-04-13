"""E2E test: Polaris JDBC state survives pod restart.

Covers salvage-branch-wrap-up AC-4: proves that a user-created Iceberg
namespace and table with a unique UUID suffix (and at least one row) are
still present and loadable after `kubectl rollout restart deployment/polaris`.

Why this test is hard to fake (see spec.md AC-4):
    - Unique UUID-suffix namespace cannot be confused with bootstrap state
    - Recorded table_uuid assertion defeats "bootstrap recreated a namespace
      of the same name" failure mode
    - `num_rows >= 1` assertion defeats "metadata points at empty snapshot"
    - Fresh catalog client (not `dbt_utils._catalog_cache`) defeats
      cache-returning-stale-state failure mode

Negative control: verified test FAILS with persistence.type=in-memory on
2026-04-08 against commit f7a2b30 (documented in as-built notes).
"""

from __future__ import annotations

import subprocess
import uuid

import httpx
import pyarrow as pa
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.polaris import PolarisConfig, create_polaris_catalog
from testing.fixtures.polling import wait_for_condition


class TestPolarisJdbcDurability(IntegrationTestBase):
    """E2E: Polaris JDBC state survives pod restart (salvage-wrap-up AC-4)."""

    required_services = ["polaris", "minio", "postgres"]

    @pytest.mark.requirement("salvage-wrap-up-AC-4")
    def test_unique_namespace_and_table_survive_polaris_restart(self) -> None:
        """Create namespace + populated table, restart Polaris, verify survival.

        Steps:
            1. Create unique-UUID namespace `restart_probe_<uuid>`
            2. Create table with schema (id: int, value: string)
            3. Append 1+ rows; record table_uuid
            4. Pre-check: current_snapshot() is not None (W6 guard)
            5. Rollout restart + rollout status (180s timeout)
            6. Poll /q/health/ready (180s timeout)
            7. Open a FRESH PyIceberg catalog client (no dbt_utils import)
            8. Assert namespace present, table loadable, UUID matches, row present
        """
        self.check_infrastructure("polaris")

        # Step 1-2: Create namespace and table with unique UUID suffix
        uid = uuid.uuid4().hex[:12]
        ns_name = f"restart_probe_{uid}"
        table_name = f"probe_{uid}"
        fqn = f"{ns_name}.{table_name}"

        config = PolarisConfig()
        catalog = create_polaris_catalog(config)

        # Create namespace
        catalog.create_namespace(ns_name)

        # Create table with schema
        from pyiceberg.schema import Schema
        from pyiceberg.types import IntegerType, NestedField, StringType

        schema = Schema(
            NestedField(field_id=1, name="id", field_type=IntegerType(), required=False),
            NestedField(field_id=2, name="value", field_type=StringType(), required=False),
        )
        table = catalog.create_table(fqn, schema=schema)
        recorded_table_uuid = table.metadata.table_uuid
        assert recorded_table_uuid is not None, (
            f"PyIceberg did not assign a table_uuid to {fqn} — cannot proceed"
        )

        # Step 3: Append at least one row (ensures at least one snapshot)
        data = pa.table(
            {
                "id": pa.array([1], type=pa.int32()),
                "value": pa.array(["probe-row"], type=pa.string()),
            }
        )
        table.append(data)

        # Step 4: Durability pre-check — snapshot must exist before restart (W6)
        table.refresh()
        assert table.current_snapshot() is not None, (
            f"Snapshot not committed for {fqn} before restart — "
            "PyIceberg deferred-commit guard tripped; AC-4 cannot proceed safely"
        )

        # Step 5: Rollout restart
        # Resolve the Polaris deployment name from POLARIS_HOST env var
        # (set by the Helm chart Job template to the release-prefixed name).
        import os

        polaris_deploy = os.environ.get("POLARIS_HOST", "polaris")
        deploy_ref = f"deployment/{polaris_deploy}"

        restart_result = subprocess.run(
            [
                "kubectl",
                "rollout",
                "restart",
                deploy_ref,
                "-n",
                self.namespace,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert restart_result.returncode == 0, (
            f"kubectl rollout restart failed: {restart_result.stderr}"
        )

        status_result = subprocess.run(
            [
                "kubectl",
                "rollout",
                "status",
                deploy_ref,
                "-n",
                self.namespace,
                "--timeout=180s",
            ],
            capture_output=True,
            text=True,
            timeout=200,
        )
        assert status_result.returncode == 0, (
            f"kubectl rollout status failed: {status_result.stderr}"
        )

        # Step 6: Wait for Polaris readiness via /q/health/ready
        from testing.fixtures.services import get_effective_host, get_effective_port

        health_host = get_effective_host("polaris")
        health_port = get_effective_port("polaris", default=8182)
        health_url = f"http://{health_host}:{health_port}/q/health/ready"

        def _is_ready() -> bool:
            try:
                r = httpx.get(health_url, timeout=2.0)
                return r.status_code == 200
            except Exception:
                return False

        wait_for_condition(
            _is_ready,
            timeout=180.0,
            interval=2.0,
            description=f"Polaris /q/health/ready at {health_url}",
        )

        # Step 7: Fresh catalog client — do NOT import dbt_utils (D-7)
        fresh_catalog = create_polaris_catalog(PolarisConfig())

        # Step 8: Assertions
        existing_namespaces = [
            ns[0] if isinstance(ns, tuple) else ns
            for ns in fresh_catalog.list_namespaces()
        ]
        assert ns_name in existing_namespaces, (
            f"Namespace {ns_name!r} missing after restart — JDBC persistence "
            f"did not survive. Observed: {existing_namespaces}"
        )

        loaded = fresh_catalog.load_table(fqn)
        assert loaded.metadata.table_uuid == recorded_table_uuid, (
            f"table_uuid mismatch after restart: "
            f"expected {recorded_table_uuid}, got {loaded.metadata.table_uuid}. "
            "A fresh bootstrap may have recreated the namespace — "
            "this indicates state DID NOT survive restart."
        )
        scanned = loaded.scan().to_arrow()
        assert scanned.num_rows >= 1, (
            f"Expected >= 1 row in {fqn} after restart, got {scanned.num_rows}. "
            "Metadata points at an empty snapshot — data loss after restart."
        )

        # Cleanup (best-effort)
        try:
            fresh_catalog.drop_table(fqn)
            fresh_catalog.drop_namespace(ns_name)
        except Exception as exc:
            # Non-fatal — test already passed; cleanup is courtesy
            import logging

            logging.getLogger(__name__).warning(
                "Best-effort cleanup failed for %s: %s", fqn, type(exc).__name__
            )


# Negative control: verified test FAILS with persistence.type=in-memory on
# 2026-04-08 against commit f7a2b30. See plan.md As-Built Notes for details.
