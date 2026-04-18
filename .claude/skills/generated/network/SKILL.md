---
name: network
description: "Skill for the Network area of floe. 86 symbols across 25 files."
---

# Network

86 symbols | 25 files | Cohesion: 67%

## When to Use

- Working with code in `packages/`
- Understanding how shutdown, startup, shutdown work
- Modifying network-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/network/schemas.py` | PortRule, EgressRule, NetworkPolicyConfig, _validate_namespace, validate_to_namespace (+14) |
| `packages/floe-core/src/floe_core/cli/network/diff.py` | _validate_manifest_dir, _load_kubeconfig, _parse_manifest_file, _load_expected_policies, _compute_diff (+9) |
| `packages/floe-core/src/floe_core/network/generator.py` | NetworkPolicyManifestGenerator, generate, write_manifests, _sanitize_filename_component, _write_summary (+4) |
| `packages/floe-core/src/floe_core/cli/network/validate.py` | _load_manifest_file, _validate_network_policy_schema, _validate_required_labels, _load_all_manifests, validate_command |
| `packages/floe-core/src/floe_core/cli/network/check_cni.py` | _load_kubernetes_client, _detect_cni, _format_text_output, _format_json_output, check_cni_command |
| `packages/floe-core/src/floe_core/network/exceptions.py` | NetworkSecurityError, CIDRValidationError, PortValidationError, NamespaceValidationError |
| `packages/floe-core/src/floe_core/cli/network/audit.py` | _audit_namespace, _check_default_deny_policy, _audit_policy, _is_permissive_rule |
| `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | startup, shutdown |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/sensors.py` | _check_platform_health, _health_check_sensor_impl |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | _asset_fn, sensor_definition |

## Entry Points

Start here when exploring this area:

- **`shutdown`** (Function) — `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py:395`
- **`startup`** (Function) — `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py:134`
- **`shutdown`** (Function) — `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py:181`
- **`shutdown`** (Function) — `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py:240`
- **`sensor_definition`** (Function) — `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:1024`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `WebhookNotifier` | Class | `packages/floe-core/src/floe_core/oci/webhooks.py` | 93 |
| `NetworkPolicyGenerationResult` | Class | `packages/floe-core/src/floe_core/network/result.py` | 26 |
| `NetworkPolicyManifestGenerator` | Class | `packages/floe-core/src/floe_core/network/generator.py` | 136 |
| `PortRule` | Class | `packages/floe-core/src/floe_core/network/schemas.py` | 69 |
| `EgressRule` | Class | `packages/floe-core/src/floe_core/network/schemas.py` | 78 |
| `NetworkPolicyConfig` | Class | `packages/floe-core/src/floe_core/network/schemas.py` | 141 |
| `NetworkSecurityPluginNotFoundError` | Class | `packages/floe-core/src/floe_core/network/generator.py` | 26 |
| `NetworkSecurityError` | Class | `packages/floe-core/src/floe_core/network/exceptions.py` | 9 |
| `CIDRValidationError` | Class | `packages/floe-core/src/floe_core/network/exceptions.py` | 19 |
| `PortValidationError` | Class | `packages/floe-core/src/floe_core/network/exceptions.py` | 32 |
| `NamespaceValidationError` | Class | `packages/floe-core/src/floe_core/network/exceptions.py` | 44 |
| `shutdown` | Function | `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py` | 395 |
| `startup` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | 134 |
| `shutdown` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | 181 |
| `shutdown` | Function | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py` | 240 |
| `sensor_definition` | Function | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | 1024 |
| `shutdown` | Function | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | 205 |
| `run_models` | Function | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/dbt_resource.py` | 193 |
| `discover_all` | Function | `packages/floe-core/src/floe_core/plugins/discovery.py` | 70 |
| `run_models` | Function | `packages/floe-core/src/floe_core/plugins/dbt.py` | 369 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Diff_command → Items` | cross_community | 5 |
| `Check_cni_command → Items` | cross_community | 5 |
| `Coverage → Info` | cross_community | 5 |
| `Reset → Info` | cross_community | 5 |
| `Generate_command → Items` | cross_community | 4 |
| `Generate_command → CompilationException` | cross_community | 4 |
| `Generate_command → CompilationError` | cross_community | 4 |
| `Generate_command → Errors` | cross_community | 4 |
| `Push_command → Info` | cross_community | 4 |
| `Pull_command → Info` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Rbac | 8 calls |
| Platform | 6 calls |
| Schemas | 6 calls |
| Floe_catalog_polaris | 4 calls |
| Floe_core | 3 calls |
| Floe_secrets_infisical | 1 calls |
| Oci | 1 calls |
| Floe_orchestrator_dagster | 1 calls |

## How to Explore

1. `gitnexus_context({name: "shutdown"})` — see callers and callees
2. `gitnexus_query({query: "network"})` — find related execution flows
3. Read key files listed above for implementation details
