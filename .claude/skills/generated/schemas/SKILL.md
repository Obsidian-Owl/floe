---
name: schemas
description: "Skill for the Schemas area of floe. 76 symbols across 30 files."
---

# Schemas

76 symbols | 30 files | Cohesion: 76%

## When to Use

- Working with code in `packages/`
- Understanding how validate_labels, callback, items work
- Modifying schemas-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/schemas/validation.py` | SecurityPolicyViolationError, validate_security_policy_not_weakened, _validate_pii_encryption, _validate_audit_logging, _validate_policy_enforcement_level (+6) |
| `packages/floe-core/src/floe_core/schemas/rbac.py` | to_pod_security_context, to_container_security_context, to_volume_mounts, to_volumes, WritableVolumeMount (+1) |
| `packages/floe-core/src/floe_core/schemas/secrets.py` | to_env_var_syntax, resolve_secret_references, _check_string_for_secret_pattern, _collect_secret_warnings, validate_no_secrets_in_artifacts |
| `packages/floe-core/src/floe_core/schemas/manifest.py` | PlatformManifest, _validate_endpoint, validate_endpoint_url, validate_endpoint_url |
| `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | CompilationMetadata, ProductIdentity, ObservabilityConfig, CompiledArtifacts |
| `packages/floe-core/src/floe_core/schemas/json_schema.py` | export_json_schema, export_json_schema_to_file, JsonSchemaValidationError, validate_against_schema |
| `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py` | _create_or_update_secret, _create_secret, _update_secret |
| `plugins/floe-dbt-core/src/floe_dbt_core/callbacks.py` | DBTEvent, callback, _parse_level |
| `packages/floe-core/src/floe_core/schemas/plugins.py` | PluginsConfig, PluginWhitelistError, validate_domain_plugin_whitelist |
| `packages/floe-core/src/floe_core/schemas/inheritance.py` | merge_manifests, CircularInheritanceError, detect_circular_inheritance |

## Entry Points

Start here when exploring this area:

- **`validate_labels`** (Function) — `plugins/floe-secrets-k8s/src/floe_secrets_k8s/config.py:123`
- **`callback`** (Function) — `plugins/floe-dbt-core/src/floe_dbt_core/callbacks.py:116`
- **`items`** (Function) — `packages/floe-core/src/floe_core/plugin_registry.py:112`
- **`activate_all`** (Function) — `packages/floe-core/src/floe_core/plugin_registry.py:395`
- **`to_env_var_syntax`** (Function) — `packages/floe-core/src/floe_core/schemas/secrets.py:127`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `DBTEvent` | Class | `plugins/floe-dbt-core/src/floe_dbt_core/callbacks.py` | 46 |
| `PluginsConfig` | Class | `packages/floe-core/src/floe_core/schemas/plugins.py` | 230 |
| `PlatformManifest` | Class | `packages/floe-core/src/floe_core/schemas/manifest.py` | 332 |
| `SecurityPolicyViolationError` | Class | `packages/floe-core/src/floe_core/schemas/validation.py` | 25 |
| `ResourceAttributes` | Class | `packages/floe-core/src/floe_core/schemas/telemetry.py` | 31 |
| `TelemetryConfig` | Class | `packages/floe-core/src/floe_core/schemas/telemetry.py` | 336 |
| `CompilationMetadata` | Class | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 33 |
| `ProductIdentity` | Class | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 70 |
| `ObservabilityConfig` | Class | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 400 |
| `CompiledArtifacts` | Class | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 549 |
| `EnvironmentStatus` | Class | `packages/floe-core/src/floe_core/schemas/promotion.py` | 910 |
| `PromotionHistoryEntry` | Class | `packages/floe-core/src/floe_core/schemas/promotion.py` | 951 |
| `PromotionStatusResponse` | Class | `packages/floe-core/src/floe_core/schemas/promotion.py` | 1018 |
| `WritableVolumeMount` | Class | `packages/floe-core/src/floe_core/schemas/rbac.py` | 464 |
| `ValidationResult` | Class | `packages/floe-core/src/floe_core/schemas/quality_validation.py` | 20 |
| `PluginWhitelistError` | Class | `packages/floe-core/src/floe_core/schemas/plugins.py` | 45 |
| `RetryConfig` | Class | `packages/floe-core/src/floe_core/schemas/oci.py` | 124 |
| `JsonSchemaValidationError` | Class | `packages/floe-core/src/floe_core/schemas/json_schema.py` | 16 |
| `CircularInheritanceError` | Class | `packages/floe-core/src/floe_core/schemas/inheritance.py` | 23 |
| `validate_labels` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/config.py` | 123 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run_checks → Items` | cross_community | 6 |
| `Diff_command → Items` | cross_community | 5 |
| `Diff_command → Items` | cross_community | 5 |
| `Audit_command → Items` | cross_community | 5 |
| `Audit_command → Items` | cross_community | 5 |
| `Check_cni_command → Items` | cross_community | 5 |
| `Verify_command → Items` | cross_community | 5 |
| `Set_secret → InfisicalBackendUnavailableError` | cross_community | 5 |
| `Set_secret → Get_tracer` | cross_community | 5 |
| `Set_secret → Sanitize_error_message` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Oci | 3 calls |
| Floe_rbac_k8s | 2 calls |
| Floe_secrets_infisical | 1 calls |
| Floe_catalog_polaris | 1 calls |

## How to Explore

1. `gitnexus_context({name: "validate_labels"})` — see callers and callees
2. `gitnexus_query({query: "schemas"})` — find related execution flows
3. Read key files listed above for implementation details
