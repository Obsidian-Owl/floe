---
name: oci
description: "Skill for the Oci area of floe. 339 symbols across 31 files."
---

# Oci

339 symbols | 31 files | Cohesion: 72%

## When to Use

- Working with code in `packages/`
- Understanding how values, is_expired, touch work
- Modifying oci-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/oci/client.py` | from_manifest, promote_to_environment, _with_circuit_breaker, _push_internal, _upload_to_registry (+42) |
| `packages/floe-core/src/floe_core/oci/errors.py` | DigestMismatchError, RegistryUnavailableError, SignatureVerificationError, __init__, __init__ (+28) |
| `packages/floe-core/src/floe_core/oci/promotion.py` | _store_promotion_record, _store_rollback_record, _verify_signature, _get_artifact_digest, _create_env_tag (+25) |
| `packages/floe-core/src/floe_core/oci/verification.py` | VerificationClient, enforcement, verify, _verify_sbom_present, _handle_unsigned (+22) |
| `packages/floe-core/src/floe_core/oci/signing.py` | _get_tracer, _trace_span, wrapper, SigningError, OIDCTokenError (+20) |
| `packages/floe-core/src/floe_core/oci/resilience.py` | wrap, wrapper, __init__, state, _emit_state_metric (+17) |
| `packages/floe-core/src/floe_core/oci/auth.py` | Credentials, get_credentials, get_credentials, get_credentials, get_credentials (+17) |
| `packages/floe-core/src/floe_core/oci/cache.py` | get, get_by_digest, get_with_content, remove, clear (+13) |
| `packages/floe-core/src/floe_core/schemas/oci.py` | _utc_now, is_expired, touch, CacheIndex, add_entry (+9) |
| `packages/floe-core/src/floe_core/oci/layers.py` | find_artifacts_file, deserialize_artifacts, build_target_ref, TagClassifier, get_tag_classifier (+9) |

## Entry Points

Start here when exploring this area:

- **`values`** (Function) — `packages/floe-core/src/floe_core/plugin_registry.py:108`
- **`is_expired`** (Function) — `packages/floe-core/src/floe_core/schemas/oci.py:626`
- **`touch`** (Function) — `packages/floe-core/src/floe_core/schemas/oci.py:650`
- **`add_entry`** (Function) — `packages/floe-core/src/floe_core/schemas/oci.py:687`
- **`remove_entry`** (Function) — `packages/floe-core/src/floe_core/schemas/oci.py:697`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `CacheIndex` | Class | `packages/floe-core/src/floe_core/schemas/oci.py` | 655 |
| `DigestMismatchError` | Class | `packages/floe-core/src/floe_core/oci/errors.py` | 296 |
| `CycleDetectionResult` | Class | `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py` | 44 |
| `ArtifactLayer` | Class | `packages/floe-core/src/floe_core/schemas/oci.py` | 358 |
| `ArtifactManifest` | Class | `packages/floe-core/src/floe_core/schemas/oci.py` | 403 |
| `ArtifactTag` | Class | `packages/floe-core/src/floe_core/schemas/oci.py` | 499 |
| `RegistryUnavailableError` | Class | `packages/floe-core/src/floe_core/oci/errors.py` | 260 |
| `Subject` | Class | `packages/floe-core/src/floe_core/schemas/signing.py` | 426 |
| `AttestationManifest` | Class | `packages/floe-core/src/floe_core/schemas/signing.py` | 435 |
| `AttestationError` | Class | `packages/floe-core/src/floe_core/oci/attestation.py` | 37 |
| `SyftNotFoundError` | Class | `packages/floe-core/src/floe_core/oci/attestation.py` | 43 |
| `CosignNotFoundError` | Class | `packages/floe-core/src/floe_core/oci/attestation.py` | 53 |
| `SBOMGenerationError` | Class | `packages/floe-core/src/floe_core/oci/attestation.py` | 63 |
| `AttestationAttachError` | Class | `packages/floe-core/src/floe_core/oci/attestation.py` | 75 |
| `VerificationResult` | Class | `packages/floe-core/src/floe_core/schemas/signing.py` | 386 |
| `VerificationAuditEvent` | Class | `packages/floe-core/src/floe_core/schemas/signing.py` | 472 |
| `VerificationClient` | Class | `packages/floe-core/src/floe_core/oci/verification.py` | 195 |
| `SignatureVerificationError` | Class | `packages/floe-core/src/floe_core/oci/errors.py` | 370 |
| `SigningError` | Class | `packages/floe-core/src/floe_core/oci/signing.py` | 147 |
| `OIDCTokenError` | Class | `packages/floe-core/src/floe_core/oci/signing.py` | 153 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `List → _emit_state_metric` | cross_community | 7 |
| `Sign → _emit_state_metric` | cross_community | 7 |
| `Push_command → ImmutabilityViolationError` | cross_community | 6 |
| `Generate_values_from_config → Values` | cross_community | 6 |
| `Compile_command → Get_tracer` | cross_community | 5 |
| `Wrapper → Get_current_span` | cross_community | 5 |
| `Set_secret → Sanitize_error_message` | cross_community | 5 |
| `Push_command → Record_artifact_size` | cross_community | 5 |
| `Inspect_command → Record_artifact_size` | cross_community | 5 |
| `Promote_multi → Get_tracer` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Network | 8 calls |
| Schemas | 6 calls |
| Platform | 5 calls |
| Artifact | 3 calls |
| Floe_core | 2 calls |
| Telemetry | 2 calls |
| Floe_lineage_marquez | 2 calls |
| Floe_catalog_polaris | 1 calls |

## How to Explore

1. `gitnexus_context({name: "values"})` — see callers and callees
2. `gitnexus_query({query: "oci"})` — find related execution flows
3. Read key files listed above for implementation details
