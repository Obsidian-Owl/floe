# Design: E2E Production Bugfixes

## Overview

Fix 2 production bugs causing 8 E2E test failures (7+1). Both are code defects, not test or infrastructure issues.

## Bug 1: Code Generator Template Bypasses Plugin System

### Problem

The `_export_dbt_to_iceberg()` template in `plugin.py:1239-1246` generates code that calls `load_catalog()` directly with hardcoded parameter mapping:

```python
catalog = load_catalog(
    "polaris",
    type="rest",
    uri=catalog_config.get("uri", ""),
    credential=catalog_config.get("credential", ""),  # BUG: key doesn't exist
    warehouse=catalog_config.get("warehouse", ""),
    **{f"s3.{k}": v for k, v in storage_config.items()},
)
```

The compiled artifacts now store OAuth2 config as a nested `oauth2` dict (with `client_id`, `client_secret`, `token_url`), not a flat `credential` string. So `catalog_config.get("credential", "")` returns empty string. Additionally, no `scope` parameter is passed — Polaris requires `PRINCIPAL_ROLE:ALL`.

### Root Cause

The template was written before the plugin config system was complete. It duplicates catalog connection logic that properly belongs in the Polaris plugin's `connect()` method.

### Fix

Replace the direct `load_catalog()` call in the template with the plugin-based approach:

1. Use `get_registry()` to load the catalog plugin
2. Use `registry.configure()` with the compiled config to produce a validated config
3. Re-instantiate with validated config (same T2 pattern)
4. Call `plugin.connect()` to get a PyIceberg `Catalog` object
5. Use the catalog for all DuckDB-to-Iceberg operations (create_namespace, load_table, create_table, overwrite, append)

The `connect()` method (Polaris plugin `plugin.py:220-293`) already handles:
- OAuth2 credential construction (`f"{client_id}:{client_secret}"`)
- Token URL configuration
- Scope parameter (`PRINCIPAL_ROLE:ALL` via config or default)
- Credential vending header
- Retry logic

This eliminates 100% of the duplicated connection logic from the template.

**Storage config**: The S3 storage plugin config must also be passed to the catalog. The `connect()` method accepts a `config` dict parameter — S3-prefixed keys (`s3.endpoint`, `s3.access-key-id`, etc.) can be passed through this parameter, matching what the current template does with the `**{f"s3.{k}": v ...}` spread.

### Alternative Considered

Update the template to manually construct `credential` from `oauth2.client_id:oauth2.client_secret` — **rejected** because it continues to duplicate the Polaris plugin's `connect()` logic and would need updating if the auth mechanism changes. Violates Constitution Principle II (Plugin-First).

## Bug 2: S3StoragePlugin Missing `tracer_name`

### Problem

`S3StoragePlugin` doesn't override `tracer_name` from `PluginMetadata` base class, which returns `None`. The `verify_plugin_instrumentation()` audit (telemetry/audit.py:82) flags this as a warning. The governance enforcement test expects 0 warnings but gets 1.

### Fix

Add `tracer_name` property to `S3StoragePlugin` returning `"floe_storage_s3"`. Define a module-level `TRACER_NAME` constant, following the Polaris plugin pattern.

3 lines of production code + 1 test.

## Blast Radius

| Module | Scope | Impact |
|--------|-------|--------|
| `plugins/floe-orchestrator-dagster/.../plugin.py` | Template only | LOCAL — regenerated definitions.py files |
| `plugins/floe-storage-s3/.../plugin.py` | Property addition | LOCAL — S3 plugin only |
| `demo/*/definitions.py` | Regenerated | LOCAL — auto-generated files |

### What This Design Does NOT Change

- CompiledArtifacts schema
- Plugin ABCs or interfaces
- `create_iceberg_resources()` / `try_create_iceberg_resources()` resource path
- Helm chart or Docker image structure
- Test assertions (tests are correct; code is wrong)
- Any other plugin implementations

## Risks

1. **Template generates new definitions.py** — all demo products must be recompiled before E2E tests. Mitigation: `make compile-demo` is already part of the `build-demo-image` target and the E2E test flow.
2. **Import availability** — the generated code imports from `floe_core.plugin_registry` and uses the catalog plugin indirectly. These are already imported elsewhere in the generated file (`try_create_iceberg_resources`), confirming they're available in the Docker image.

## Architect Review

Convergence: 4+/5 on all dimensions. APPROVED with 2 WARNs resolved:
- **WARN (implementation path)**: Resolved — use registry.get + configure + connect, not a new abstraction.
- **WARN (recompilation)**: Resolved — `make compile-demo` is already part of the build flow.
