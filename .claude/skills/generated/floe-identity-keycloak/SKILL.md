---
name: floe-identity-keycloak
description: "Skill for the Floe_identity_keycloak area of floe. 45 symbols across 6 files."
---

# Floe_identity_keycloak

45 symbols | 6 files | Cohesion: 93%

## When to Use

- Working with code in `plugins/`
- Understanding how validate, refresh_jwks, get_tracer work
- Modifying floe_identity_keycloak-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py` | UserInfo, TokenValidationResult, validate, _validate_token_internal, _validate_token_header (+9) |
| `plugins/floe-identity-keycloak/src/floe_identity_keycloak/errors.py` | KeycloakPluginError, KeycloakConfigError, KeycloakAuthError, KeycloakTokenError, KeycloakUnavailableError (+8) |
| `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py` | startup, authenticate, _do_authenticate, validate_token, _validate_and_convert (+6) |
| `packages/floe-core/src/floe_core/plugins/identity.py` | TokenValidationResult, UserInfo, OIDCConfig |
| `plugins/floe-identity-keycloak/src/floe_identity_keycloak/tracing.py` | get_tracer, identity_span |
| `plugins/floe-identity-keycloak/src/floe_identity_keycloak/config.py` | _is_localhost, validate_server_url |

## Entry Points

Start here when exploring this area:

- **`validate`** (Function) — `plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py:120`
- **`refresh_jwks`** (Function) — `plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py:396`
- **`get_tracer`** (Function) — `plugins/floe-identity-keycloak/src/floe_identity_keycloak/tracing.py:45`
- **`identity_span`** (Function) — `plugins/floe-identity-keycloak/src/floe_identity_keycloak/tracing.py:64`
- **`startup`** (Function) — `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py:112`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `UserInfo` | Class | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py` | 28 |
| `TokenValidationResult` | Class | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py` | 58 |
| `TokenValidator` | Class | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py` | 72 |
| `TokenValidationResult` | Class | `packages/floe-core/src/floe_core/plugins/identity.py` | 56 |
| `KeycloakPluginError` | Class | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/errors.py` | 18 |
| `KeycloakConfigError` | Class | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/errors.py` | 54 |
| `KeycloakAuthError` | Class | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/errors.py` | 70 |
| `KeycloakTokenError` | Class | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/errors.py` | 111 |
| `KeycloakUnavailableError` | Class | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/errors.py` | 152 |
| `UserInfo` | Class | `packages/floe-core/src/floe_core/plugins/identity.py` | 27 |
| `OIDCConfig` | Class | `packages/floe-core/src/floe_core/plugins/identity.py` | 80 |
| `validate` | Function | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py` | 120 |
| `refresh_jwks` | Function | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py` | 396 |
| `get_tracer` | Function | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/tracing.py` | 45 |
| `identity_span` | Function | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/tracing.py` | 64 |
| `startup` | Function | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py` | 112 |
| `authenticate` | Function | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py` | 174 |
| `validate_token` | Function | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py` | 293 |
| `validate_token_for_realm` | Function | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py` | 380 |
| `get_user_info` | Function | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py` | 252 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Oci | 3 calls |
| Floe_lineage_marquez | 1 calls |

## How to Explore

1. `gitnexus_context({name: "validate"})` — see callers and callees
2. `gitnexus_query({query: "floe_identity_keycloak"})` — find related execution flows
3. Read key files listed above for implementation details
