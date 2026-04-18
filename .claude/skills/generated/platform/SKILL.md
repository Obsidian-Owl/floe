---
name: platform
description: "Skill for the Platform area of floe. 45 symbols across 19 files."
---

# Platform

45 symbols | 19 files | Cohesion: 68%

## When to Use

- Working with code in `packages/`
- Understanding how validate_tag_security, promote_multi, from_registry_config work
- Modifying platform-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/cli/artifact/sign.py` | sign_command, _build_signing_config, _build_key_based_signing_config, _sign_artifact, _build_registry_config |
| `packages/floe-core/src/floe_core/cli/platform/status.py` | _format_status_json, _format_status_yaml, _get_exit_code_from_exception, status_command |
| `packages/floe-core/src/floe_core/cli/platform/rollback.py` | _format_rollback_result, _format_impact_analysis, _get_exit_code_from_exception, rollback_command |
| `packages/floe-core/src/floe_core/cli/platform/lock.py` | _get_operator, _load_platform_manifest, lock_command, unlock_command |
| `packages/floe-core/src/floe_core/cli/artifact/push.py` | push_command, _push_to_registry, _build_registry_config, _sign_artifact |
| `packages/floe-core/src/floe_core/schemas/promotion.py` | EnvironmentConfig, _default_environments, PromotionConfig |
| `packages/floe-core/src/floe_core/oci/promotion.py` | validate_tag_security, PromotionController, promote_multi |
| `packages/floe-core/src/floe_core/cli/platform/promote.py` | _format_promotion_result, _get_exit_code_from_exception, promote_command |
| `packages/floe-core/src/floe_core/cli/artifact/pull.py` | pull_command, _build_registry_config, _pull_from_registry |
| `packages/floe-core/src/floe_core/schemas/oci.py` | RegistryAuth, RegistryConfig |

## Entry Points

Start here when exploring this area:

- **`validate_tag_security`** (Function) — `packages/floe-core/src/floe_core/oci/promotion.py:107`
- **`promote_multi`** (Function) — `packages/floe-core/src/floe_core/oci/promotion.py:2324`
- **`from_registry_config`** (Function) — `packages/floe-core/src/floe_core/oci/client.py:320`
- **`success`** (Function) — `packages/floe-core/src/floe_core/cli/utils.py:130`
- **`status_command`** (Function) — `packages/floe-core/src/floe_core/cli/platform/status.py:203`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `SigningConfig` | Class | `packages/floe-core/src/floe_core/schemas/signing.py` | 33 |
| `SecretReference` | Class | `packages/floe-core/src/floe_core/schemas/secrets.py` | 69 |
| `EnvironmentConfig` | Class | `packages/floe-core/src/floe_core/schemas/promotion.py` | 443 |
| `PromotionConfig` | Class | `packages/floe-core/src/floe_core/schemas/promotion.py` | 533 |
| `RegistryAuth` | Class | `packages/floe-core/src/floe_core/schemas/oci.py` | 71 |
| `RegistryConfig` | Class | `packages/floe-core/src/floe_core/schemas/oci.py` | 262 |
| `PromotionController` | Class | `packages/floe-core/src/floe_core/oci/promotion.py` | 136 |
| `validate_tag_security` | Function | `packages/floe-core/src/floe_core/oci/promotion.py` | 107 |
| `promote_multi` | Function | `packages/floe-core/src/floe_core/oci/promotion.py` | 2324 |
| `from_registry_config` | Function | `packages/floe-core/src/floe_core/oci/client.py` | 320 |
| `success` | Function | `packages/floe-core/src/floe_core/cli/utils.py` | 130 |
| `status_command` | Function | `packages/floe-core/src/floe_core/cli/platform/status.py` | 203 |
| `rollback_command` | Function | `packages/floe-core/src/floe_core/cli/platform/rollback.py` | 202 |
| `promote_command` | Function | `packages/floe-core/src/floe_core/cli/platform/promote.py` | 185 |
| `lock_command` | Function | `packages/floe-core/src/floe_core/cli/platform/lock.py` | 127 |
| `unlock_command` | Function | `packages/floe-core/src/floe_core/cli/platform/lock.py` | 302 |
| `sign_command` | Function | `packages/floe-core/src/floe_core/cli/artifact/sign.py` | 101 |
| `push_command` | Function | `packages/floe-core/src/floe_core/cli/artifact/push.py` | 95 |
| `pull_command` | Function | `packages/floe-core/src/floe_core/cli/artifact/pull.py` | 104 |
| `to_json_file` | Function | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 694 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Push_command → ImmutabilityViolationError` | cross_community | 6 |
| `Compile_command → Get_tracer` | cross_community | 5 |
| `Compile_command → CompilationException` | cross_community | 5 |
| `Compile_command → CompilationError` | cross_community | 5 |
| `Compile_command → Errors` | cross_community | 5 |
| `Sign_command → Items` | cross_community | 5 |
| `Push_command → Items` | cross_community | 5 |
| `Push_command → Record_artifact_size` | cross_community | 5 |
| `Promote_multi → Get_tracer` | cross_community | 5 |
| `Compile_command → Items` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Oci | 13 calls |
| Rbac | 12 calls |
| Network | 11 calls |
| Floe_catalog_polaris | 6 calls |
| Cli | 3 calls |
| Schemas | 2 calls |
| Plugins | 2 calls |
| Compilation | 1 calls |

## How to Explore

1. `gitnexus_context({name: "validate_tag_security"})` — see callers and callees
2. `gitnexus_query({query: "platform"})` — find related execution flows
3. Read key files listed above for implementation details
