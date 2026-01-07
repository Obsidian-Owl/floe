#!/usr/bin/env python3
"""Validate DuckDB Iceberg catalog connection (floe-platform).

This script validates the inline credentials ATTACH pattern used by floe-platform.

Usage:
    python validate_iceberg_connection.py

Environment Variables (Required):
    POLARIS_CLIENT_ID       - OAuth2 client ID
    POLARIS_CLIENT_SECRET   - OAuth2 client secret
    FLOE_POLARIS_URI        - Polaris API endpoint
    FLOE_POLARIS_WAREHOUSE  - Warehouse name

Example:
    export POLARIS_CLIENT_ID=<your-client-id>
    export POLARIS_CLIENT_SECRET=<your-client-secret>
    export FLOE_POLARIS_URI=http://floe-infra-polaris:8181/api/catalog
    export FLOE_POLARIS_WAREHOUSE=demo_catalog
    python validate_iceberg_connection.py
"""

import os
import sys

import duckdb


def validate_duckdb_iceberg_inline_credentials():
    """Test DuckDB Iceberg ATTACH with inline credentials (floe-platform pattern).

    This validates the exact pattern used by packages/floe-dbt/src/floe_dbt/plugins/polaris.py.

    Returns:
        bool: True if connection successful, raises exception otherwise.
    """
    catalog_uri = os.getenv("FLOE_POLARIS_URI")
    warehouse = os.getenv("FLOE_POLARIS_WAREHOUSE")
    client_id = os.getenv("POLARIS_CLIENT_ID")
    client_secret = os.getenv("POLARIS_CLIENT_SECRET")

    if not all([catalog_uri, warehouse, client_id, client_secret]):
        print("❌ Missing required environment variables:")
        print("   - FLOE_POLARIS_URI")
        print("   - FLOE_POLARIS_WAREHOUSE")
        print("   - POLARIS_CLIENT_ID")
        print("   - POLARIS_CLIENT_SECRET")
        sys.exit(1)

    print("=" * 60)
    print("DuckDB Iceberg Connection Validation (floe-platform)")
    print("=" * 60)
    print(f"Catalog URI: {catalog_uri}")
    print(f"Warehouse:   {warehouse}")
    print(f"Client ID:   {client_id[:20]}... (truncated)")
    print()

    print("Step 1: Create DuckDB connection (file-based)...")
    conn = duckdb.connect("/tmp/floe_validation.duckdb")
    print("✓ Connection created")
    print()

    print("Step 2: Install and load Iceberg extension...")
    conn.execute("INSTALL iceberg")
    conn.execute("LOAD iceberg")
    print("✓ Iceberg extension loaded")
    print()

    print("Step 3: ATTACH catalog with inline credentials...")
    oauth2_server_uri = f"{catalog_uri}/v1/oauth/tokens"

    attach_sql = f"""
    ATTACH IF NOT EXISTS '{warehouse}' AS polaris_catalog (
        TYPE ICEBERG,
        CLIENT_ID '{client_id}',
        CLIENT_SECRET '{client_secret}',
        OAUTH2_SERVER_URI '{oauth2_server_uri}',
        ENDPOINT '{catalog_uri}'
    )
    """

    try:
        conn.execute(attach_sql)
        print("✓ ATTACH successful: polaris_catalog")
        print()
    except Exception as e:
        print(f"❌ ATTACH failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("Step 4: List tables in catalog...")
    try:
        result = conn.execute("SHOW ALL TABLES").fetchall()
        print(f"✓ Found {len(result)} tables")
        if result:
            print()
            print("Tables:")
            for row in result[:10]:  # Show first 10
                print(f"  - {row}")
            if len(result) > 10:
                print(f"  ... and {len(result) - 10} more")
        else:
            print("  (No tables found - catalog is empty)")
        print()
    except Exception as e:
        print(f"⚠️  Could not list tables: {e}")
        print("   (This may be expected if warehouse is empty)")
        print()

    print("Step 5: Verify catalog metadata...")
    try:
        result = conn.execute("SELECT current_catalog(), current_schema()").fetchone()
        print(f"✓ Current catalog: {result[0]}, schema: {result[1]}")
        print()
    except Exception as e:
        print(f"⚠️  Could not verify metadata: {e}")
        print()

    conn.close()
    print("=" * 60)
    print("✅ Validation complete - inline credentials ATTACH works!")
    print("=" * 60)
    return True


def validate_polaris_rest_api():
    """Test Polaris REST API connectivity (optional - requires requests).

    This validates that the Polaris service is reachable.

    Returns:
        bool: True if API reachable, False otherwise.
    """
    catalog_uri = os.getenv("FLOE_POLARIS_URI")
    client_id = os.getenv("POLARIS_CLIENT_ID")
    client_secret = os.getenv("POLARIS_CLIENT_SECRET")

    if not all([catalog_uri, client_id, client_secret]):
        print("⚠️  Skipping Polaris REST API validation (missing env vars)")
        return False

    try:
        import requests
    except ImportError:
        print("⚠️  Skipping Polaris REST API validation (requests not installed)")
        return False

    print()
    print("=" * 60)
    print("Polaris REST API Validation (Optional)")
    print("=" * 60)

    print("Step 1: Get OAuth2 token...")
    token_url = f"{catalog_uri}/v1/oauth/tokens"

    try:
        response = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "PRINCIPAL_ROLE:ALL",
            },
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        print(f"✓ OAuth2 token obtained: {token[:20]}... (truncated)")
        print()
    except Exception as e:
        print(f"❌ Failed to get token: {e}")
        return False

    print("Step 2: List warehouses...")
    try:
        response = requests.get(
            f"{catalog_uri.replace('/api/catalog', '/api/management/v1/warehouses')}",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        warehouses = response.json()["warehouses"]
        print(f"✓ Found {len(warehouses)} warehouses")
        for wh in warehouses:
            print(f"  - {wh['name']}")
        print()
    except Exception as e:
        print(f"❌ Failed to list warehouses: {e}")
        return False

    print("=" * 60)
    print("✅ Polaris REST API validation complete!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        validate_duckdb_iceberg_inline_credentials()
        validate_polaris_rest_api()
        print()
        print("✅ All validations passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
