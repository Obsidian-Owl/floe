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

import os
import subprocess
import uuid
from pathlib import Path

import httpx
import pyarrow as pa
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.credentials import get_minio_credentials
from testing.fixtures.polaris import (
    PolarisConfig,
    create_polaris_catalog,
    rewrite_table_io_for_host_access,
)
from testing.fixtures.polling import wait_for_condition
from testing.fixtures.services import ServiceEndpoint


def _minio_base_url() -> str:
    return os.environ.get("MINIO_URL", ServiceEndpoint("minio").url)


def _durability_polaris_config() -> PolarisConfig:
    return PolarisConfig(warehouse=os.environ.get("POLARIS_WAREHOUSE", "floe-e2e"))


def _validated_identifier(value: str, label: str) -> str:
    if not value or not all(ch.isalnum() or ch in "-_" for ch in value):
        pytest.fail(f"{label} contains characters outside [a-zA-Z0-9_-]: {value!r}")
    return value


def _request_oauth_token(config: PolarisConfig) -> str:
    client_id, client_secret = config.credential.get_secret_value().split(":", 1)
    response = httpx.post(
        f"{config.api_base_url}/api/catalog/v1/oauth/tokens",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": config.scope,
        },
        timeout=10.0,
    )
    response_body = _safe_response_body(response)
    assert response.status_code == 200, (
        f"Polaris OAuth token request failed: HTTP {response.status_code} body={response_body!r}"
    )
    access_token = response.json().get("access_token")
    assert isinstance(access_token, str) and access_token, (
        f"Polaris OAuth token response missing a non-empty access_token field: {response_body!r}"
    )
    return access_token


def _safe_response_body(response: httpx.Response) -> object:
    """Return a log-safe response body with token-like fields redacted."""
    try:
        body = response.json()
    except ValueError:
        return response.text

    if isinstance(body, dict):
        return {key: ("***" if "token" in key.lower() else value) for key, value in body.items()}
    return body


def _assert_seeded_catalog_lookup(config: PolarisConfig, access_token: str) -> None:
    catalog_name = _validated_identifier(config.warehouse, "Polaris warehouse")
    response = httpx.get(
        f"{config.api_base_url}/api/management/v1/catalogs/{catalog_name}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10.0,
    )
    assert response.status_code == 200, (
        f"Seeded Polaris catalog lookup failed for {catalog_name!r}: "
        f"HTTP {response.status_code} body={response.text!r}"
    )


def _ensure_iceberg_bucket() -> None:
    bucket_name = os.environ.get("MINIO_BUCKET", "floe-iceberg")
    minio_user, minio_pass = get_minio_credentials()
    ensure_bucket_script = (
        Path(__file__).resolve().parents[3] / "testing" / "ci" / "ensure-bucket.py"
    )
    result = subprocess.run(
        ["uv", "run", "python3", str(ensure_bucket_script), _minio_base_url(), bucket_name],
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "MINIO_USER": os.environ.get("MINIO_USER", minio_user),
            "MINIO_PASS": os.environ.get("MINIO_PASS", minio_pass),
        },
    )
    assert result.returncode == 0, (
        f"Failed to ensure MinIO bucket {bucket_name!r}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def _polaris_deployment_ref(namespace: str) -> str:
    explicit_name = os.environ.get("POLARIS_HOST")
    if explicit_name:
        if not all(c.isalnum() or c == "-" for c in explicit_name):
            pytest.fail("POLARIS_HOST env var contains characters outside [a-zA-Z0-9-]")
        return f"deployment/{explicit_name}"

    result = subprocess.run(
        [
            "kubectl",
            "get",
            "deployments",
            "-n",
            namespace,
            "-l",
            "app.kubernetes.io/component=polaris",
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    deployment_name = result.stdout.strip()
    assert result.returncode == 0 and deployment_name, (
        "Unable to resolve the Polaris deployment by label. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    return f"deployment/{deployment_name}"


class TestPolarisJdbcDurability(IntegrationTestBase):
    """E2E: Polaris JDBC state survives pod restart (salvage-wrap-up AC-4)."""

    required_services = ["polaris", "minio", "postgresql"]

    @pytest.mark.requirement("RAC-7")
    @pytest.mark.requirement("RAC-8")
    def test_oauth_and_seeded_catalog_lookup_succeed(self) -> None:
        """Verify Polaris issues OAuth tokens and exposes the seeded catalog.

        This gives RAC-7 and RAC-8 durable proof in a Polaris-named test class,
        instead of relying only on build-time shell probes.
        """
        self.check_infrastructure("polaris")

        config = _durability_polaris_config()
        access_token = _request_oauth_token(config)
        _assert_seeded_catalog_lookup(config, access_token)

        catalog = create_polaris_catalog(config)
        namespaces = catalog.list_namespaces()
        assert isinstance(namespaces, list), (
            "Expected Polaris catalog client to list namespaces successfully after "
            "the seeded catalog lookup passed."
        )

    @pytest.mark.requirement("salvage-wrap-up-AC-4")
    @pytest.mark.requirement("RAC-9")
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
        self.check_infrastructure("postgresql")

        # Step 1-2: Create namespace and table with unique UUID suffix
        uid = uuid.uuid4().hex[:12]
        ns_name = f"restart_probe_{uid}"
        table_name = f"probe_{uid}"
        fqn = f"{ns_name}.{table_name}"

        config = _durability_polaris_config()
        catalog = create_polaris_catalog(config)
        _ensure_iceberg_bucket()

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
        rewrite_table_io_for_host_access(table)
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
        deploy_ref = _polaris_deployment_ref(self.namespace)

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

        restart_token = _request_oauth_token(config)
        _assert_seeded_catalog_lookup(config, restart_token)

        logs_result = subprocess.run(
            [
                "kubectl",
                "logs",
                deploy_ref,
                "-n",
                self.namespace,
                "--since=10m",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert logs_result.returncode == 0, (
            f"kubectl logs failed for {deploy_ref}: {logs_result.stderr}"
        )
        assert "already been bootstrapped" not in logs_result.stdout, (
            "Polaris restart logs still contain the duplicate-bootstrap crash-loop "
            f"signature.\nLogs:\n{logs_result.stdout}"
        )

        # Step 7: Fresh catalog client — do NOT import dbt_utils (D-7)
        fresh_catalog = create_polaris_catalog(_durability_polaris_config())

        # Step 8: Assertions
        existing_namespaces = [
            ns[0] if isinstance(ns, tuple) else ns for ns in fresh_catalog.list_namespaces()
        ]
        assert ns_name in existing_namespaces, (
            f"Namespace {ns_name!r} missing after restart — JDBC persistence "
            f"did not survive. Found {len(existing_namespaces)} namespaces."
        )

        loaded = fresh_catalog.load_table(fqn)
        rewrite_table_io_for_host_access(loaded)
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
            fresh_catalog.purge_table(fqn)
            fresh_catalog.drop_namespace(ns_name)
        except Exception as exc:
            # Non-fatal — test already passed; cleanup is courtesy
            import logging

            logging.getLogger(__name__).warning(
                "Best-effort cleanup failed for %s: %s", fqn, type(exc).__name__
            )


# Negative control: verified test FAILS with persistence.type=in-memory on
# 2026-04-08 against commit f7a2b30. See plan.md As-Built Notes for details.
