---
name: rbac
description: "Skill for the Rbac area of floe. 86 symbols across 21 files."
---

# Rbac

86 symbols | 21 files | Cohesion: 71%

## When to Use

- Working with code in `packages/`
- Understanding how has_differences, diffs_by_change_type, has_critical_findings work
- Modifying rbac-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/cli/rbac/audit.py` | audit_command, _validate_audit_inputs, _setup_kubernetes_client, _load_kubeconfig, _output_report (+7) |
| `packages/floe-core/src/floe_core/cli/rbac/diff.py` | _validate_required_options, _load_kubeconfig, _parse_manifest_file, _load_expected_manifests, _output_diff_as_text (+6) |
| `packages/floe-core/src/floe_core/cli/network/audit.py` | audit_command, _validate_audit_inputs, _resolve_namespaces, _setup_kubernetes_client, _load_kubeconfig (+5) |
| `packages/floe-core/src/floe_core/rbac/generator.py` | _get_tracer, write_manifests, _generate_manifests_for_type, generate, _generate_impl (+5) |
| `packages/floe-core/src/floe_core/rbac/audit.py` | to_log_dict, create_success, create_validation_error, create_write_error, create_disabled (+3) |
| `packages/floe-core/src/floe_core/rbac/diff.py` | _normalize_resource, _compare_values, compute_resource_diff, compute_rbac_diff, resource_key |
| `packages/floe-core/src/floe_core/schemas/rbac_diff.py` | has_differences, diffs_by_change_type, ResourceDiff, RBACDiffResult |
| `packages/floe-core/src/floe_core/cli/utils.py` | error_exit, validate_file_exists, validate_directory_writable, sanitize_k8s_api_error |
| `packages/floe-core/src/floe_core/schemas/rbac_audit.py` | has_critical_findings, AuditFinding, RBACAuditReport |
| `packages/floe-core/src/floe_core/cli/artifact/push.py` | _load_artifacts, _handle_push_error |

## Entry Points

Start here when exploring this area:

- **`has_differences`** (Function) — `packages/floe-core/src/floe_core/schemas/rbac_diff.py:161`
- **`diffs_by_change_type`** (Function) — `packages/floe-core/src/floe_core/schemas/rbac_diff.py:169`
- **`has_critical_findings`** (Function) — `packages/floe-core/src/floe_core/schemas/rbac_audit.py:279`
- **`from_json_file`** (Function) — `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py:742`
- **`error_exit`** (Function) — `packages/floe-core/src/floe_core/cli/utils.py:85`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `GenerationResult` | Class | `packages/floe-core/src/floe_core/rbac/result.py` | 25 |
| `ValidationIssue` | Class | `packages/floe-core/src/floe_core/schemas/rbac_validation.py` | 88 |
| `RBACValidationResult` | Class | `packages/floe-core/src/floe_core/schemas/rbac_validation.py` | 142 |
| `ResourceDiff` | Class | `packages/floe-core/src/floe_core/schemas/rbac_diff.py` | 52 |
| `RBACDiffResult` | Class | `packages/floe-core/src/floe_core/schemas/rbac_diff.py` | 106 |
| `AuditFinding` | Class | `packages/floe-core/src/floe_core/schemas/rbac_audit.py` | 87 |
| `RBACConfig` | Class | `packages/floe-core/src/floe_core/schemas/security.py` | 26 |
| `SecurityConfig` | Class | `packages/floe-core/src/floe_core/schemas/security.py` | 86 |
| `RBACManifestGenerator` | Class | `packages/floe-core/src/floe_core/rbac/generator.py` | 340 |
| `RBACAuditReport` | Class | `packages/floe-core/src/floe_core/schemas/rbac_audit.py` | 213 |
| `has_differences` | Function | `packages/floe-core/src/floe_core/schemas/rbac_diff.py` | 161 |
| `diffs_by_change_type` | Function | `packages/floe-core/src/floe_core/schemas/rbac_diff.py` | 169 |
| `has_critical_findings` | Function | `packages/floe-core/src/floe_core/schemas/rbac_audit.py` | 279 |
| `from_json_file` | Function | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 742 |
| `error_exit` | Function | `packages/floe-core/src/floe_core/cli/utils.py` | 85 |
| `validate_file_exists` | Function | `packages/floe-core/src/floe_core/cli/utils.py` | 157 |
| `validate_directory_writable` | Function | `packages/floe-core/src/floe_core/cli/utils.py` | 181 |
| `sanitize_k8s_api_error` | Function | `packages/floe-core/src/floe_core/cli/utils.py` | 395 |
| `diff_command` | Function | `packages/floe-core/src/floe_core/cli/rbac/diff.py` | 342 |
| `audit_command` | Function | `packages/floe-core/src/floe_core/cli/rbac/audit.py` | 67 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Diff_command → Items` | cross_community | 5 |
| `Diff_command → Items` | cross_community | 5 |
| `Audit_command → Items` | cross_community | 5 |
| `Audit_command → Items` | cross_community | 5 |
| `Audit_command → AuditFinding` | cross_community | 5 |
| `Check_cni_command → Items` | cross_community | 5 |
| `Verify_command → Items` | cross_community | 5 |
| `Sign_command → Items` | cross_community | 5 |
| `Push_command → Items` | cross_community | 5 |
| `Inspect_command → Items` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Network | 10 calls |
| Platform | 6 calls |
| Floe_core | 4 calls |
| Schemas | 2 calls |
| Oci | 2 calls |
| Floe_catalog_polaris | 2 calls |
| Floe_lineage_marquez | 1 calls |
| Compilation | 1 calls |

## How to Explore

1. `gitnexus_context({name: "has_differences"})` — see callers and callees
2. `gitnexus_query({query: "rbac"})` — find related execution flows
3. Read key files listed above for implementation details
