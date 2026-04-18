---
name: floe-secrets-infisical
description: "Skill for the Floe_secrets_infisical area of floe. 58 symbols across 9 files."
---

# Floe_secrets_infisical

58 symbols | 9 files | Cohesion: 91%

## When to Use

- Working with code in `plugins/`
- Understanding how get_tracer, secrets_span, health_check work
- Modifying floe_secrets_infisical-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py` | _classify_error, startup, _authenticate, get_secret, set_secret (+10) |
| `plugins/floe-secrets-infisical/src/floe_secrets_infisical/errors.py` | InfisicalAccessDeniedError, InfisicalBackendUnavailableError, __init__, __init__, __init__ (+7) |
| `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | health_check, get_secret, set_secret, list_secrets, get_multi_key_secret (+3) |
| `packages/floe-core/src/floe_core/audit/logger.py` | _get_trace_context, log_event, log_success, log_denied, log_error (+2) |
| `plugins/floe-secrets-k8s/src/floe_secrets_k8s/errors.py` | SecretsPluginError, SecretNotFoundError, SecretAccessDeniedError, SecretBackendUnavailableError, SecretValidationError |
| `packages/floe-core/src/floe_core/schemas/audit.py` | to_log_dict, create_success, create_denied, create_error |
| `plugins/floe-secrets-infisical/src/floe_secrets_infisical/tracing.py` | get_tracer, secrets_span, record_result |
| `plugins/floe-secrets-k8s/src/floe_secrets_k8s/tracing.py` | get_tracer, secrets_span |
| `packages/floe-core/src/floe_core/audit/decorator.py` | wrapper, _get_attr_safe |

## Entry Points

Start here when exploring this area:

- **`get_tracer`** (Function) — `plugins/floe-secrets-k8s/src/floe_secrets_k8s/tracing.py:48`
- **`secrets_span`** (Function) — `plugins/floe-secrets-k8s/src/floe_secrets_k8s/tracing.py:67`
- **`health_check`** (Function) — `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py:187`
- **`get_secret`** (Function) — `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py:224`
- **`set_secret`** (Function) — `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py:333`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `SecretsPluginError` | Class | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/errors.py` | 22 |
| `SecretNotFoundError` | Class | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/errors.py` | 49 |
| `SecretAccessDeniedError` | Class | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/errors.py` | 78 |
| `SecretBackendUnavailableError` | Class | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/errors.py` | 121 |
| `SecretValidationError` | Class | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/errors.py` | 161 |
| `InfisicalAccessDeniedError` | Class | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/errors.py` | 119 |
| `InfisicalBackendUnavailableError` | Class | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/errors.py` | 167 |
| `InfisicalPluginError` | Class | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/errors.py` | 23 |
| `InfisicalAuthError` | Class | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/errors.py` | 50 |
| `InfisicalSecretNotFoundError` | Class | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/errors.py` | 77 |
| `InfisicalValidationError` | Class | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/errors.py` | 209 |
| `get_tracer` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/tracing.py` | 48 |
| `secrets_span` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/tracing.py` | 67 |
| `health_check` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | 187 |
| `get_secret` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | 224 |
| `set_secret` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | 333 |
| `list_secrets` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | 463 |
| `get_multi_key_secret` | Function | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | 563 |
| `get_tracer` | Function | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/tracing.py` | 46 |
| `secrets_span` | Function | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/tracing.py` | 65 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Wrapper → Get_current_span` | cross_community | 5 |
| `Set_secret → InfisicalBackendUnavailableError` | cross_community | 5 |
| `Set_secret → Get_tracer` | cross_community | 5 |
| `Set_secret → Sanitize_error_message` | cross_community | 5 |
| `Wrapper → To_log_dict` | intra_community | 4 |
| `Set_secret → Record_result` | cross_community | 4 |
| `Set_secret → Items` | cross_community | 4 |
| `Get_secret → Get_tracer` | cross_community | 3 |
| `Get_secret → Sanitize_error_message` | cross_community | 3 |
| `Get_secret → SecretBackendUnavailableError` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Schemas | 4 calls |
| Oci | 3 calls |
| Floe_lineage_marquez | 2 calls |
| Floe_catalog_polaris | 2 calls |
| Floe_secrets_k8s | 1 calls |
| Floe_core | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_tracer"})` — see callers and callees
2. `gitnexus_query({query: "floe_secrets_infisical"})` — find related execution flows
3. Read key files listed above for implementation details
