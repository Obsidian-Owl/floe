---
name: floe-catalog-polaris
description: "Skill for the Floe_catalog_polaris area of floe. 76 symbols across 17 files."
---

# Floe_catalog_polaris

76 symbols | 17 files | Cohesion: 75%

## When to Use

- Working with code in `plugins/`
- Understanding how get_tracer, catalog_span, set_error_attributes work
- Modifying floe_catalog_polaris-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `plugins/floe-catalog-polaris/src/floe_catalog_polaris/errors.py` | _handle_service_unavailable, _handle_server_error, _handle_rest_error, _handle_unknown_error, map_pyiceberg_error (+14) |
| `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | _require_config, connect, load_table_with_client_endpoint, create_namespace, list_namespaces (+10) |
| `plugins/floe-catalog-polaris/src/floe_catalog_polaris/credentials.py` | extract_credentials_from_io_properties, parse_expiration, is_expired, get_expiration_datetime, get_ttl_seconds (+2) |
| `packages/floe-core/src/floe_core/plugin_errors.py` | PluginStartupError, CatalogUnavailableError, CatalogError, ConflictError, NotFoundError (+2) |
| `packages/floe-core/src/floe_core/plugins/lifecycle.py` | activate_plugin, activate_all, shutdown_all, _run_with_timeout, clear (+2) |
| `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py` | get_tracer, catalog_span, _sanitize_uri, set_error_attributes |
| `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py` | health_check, _list_secrets_with_filter, _list_secrets_internal |
| `plugins/floe-catalog-polaris/src/floe_catalog_polaris/retry.py` | create_retry_decorator, with_retry |
| `packages/floe-core/src/floe_core/plugins/catalog.py` | load_table, health_check |
| `testing/base_classes/base_catalog_plugin_tests.py` | test_health_check_returns_health_status, test_health_check_accepts_timeout |

## Entry Points

Start here when exploring this area:

- **`get_tracer`** (Function) — `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py:44`
- **`catalog_span`** (Function) — `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py:63`
- **`set_error_attributes`** (Function) — `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py:167`
- **`create_retry_decorator`** (Function) — `plugins/floe-catalog-polaris/src/floe_catalog_polaris/retry.py:67`
- **`with_retry`** (Function) — `plugins/floe-catalog-polaris/src/floe_catalog_polaris/retry.py:117`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `PluginStartupError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 151 |
| `CatalogUnavailableError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 305 |
| `HealthStatus` | Class | `packages/floe-core/src/floe_core/plugin_metadata.py` | 52 |
| `CatalogError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 285 |
| `ConflictError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 422 |
| `NotFoundError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 456 |
| `AuthenticationError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 338 |
| `NotSupportedError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 378 |
| `get_tracer` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py` | 44 |
| `catalog_span` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py` | 63 |
| `set_error_attributes` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py` | 167 |
| `create_retry_decorator` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/retry.py` | 67 |
| `with_retry` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/retry.py` | 117 |
| `connect` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | 221 |
| `load_table_with_client_endpoint` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | 342 |
| `create_namespace` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | 384 |
| `list_namespaces` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | 460 |
| `delete_namespace` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | 542 |
| `create_table` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | 606 |
| `list_tables` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | 687 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Diff_command → Items` | cross_community | 5 |
| `Diff_command → Items` | cross_community | 5 |
| `Audit_command → Items` | cross_community | 5 |
| `Audit_command → Items` | cross_community | 5 |
| `Check_cni_command → Items` | cross_community | 5 |
| `Verify_command → Items` | cross_community | 5 |
| `Sign_command → Items` | cross_community | 5 |
| `Push_command → Items` | cross_community | 5 |
| `Inspect_command → Items` | cross_community | 5 |
| `Generate_command → Items` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Network | 8 calls |
| Schemas | 5 calls |
| Oci | 4 calls |
| Floe_core | 3 calls |
| Floe_lineage_marquez | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_tracer"})` — see callers and callees
2. `gitnexus_query({query: "floe_catalog_polaris"})` — find related execution flows
3. Read key files listed above for implementation details
