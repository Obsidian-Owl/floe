# Context: flux-user-gitops

**Parent work**: flux-gitops-implementation
**Baseline commit**: 412b1c4 (origin/main)

## What This Unit Does

Deliver user-facing GitOps artifacts: update the Flux examples to GA API versions,
add `--output-format=configmap` to the `floe compile` CLI, add Cosign keyless signing
to the Helm release workflow, and document SOPS secrets management.

## Key Files

| File | Lines | Role |
|------|-------|------|
| `charts/examples/flux/helmrelease.yaml` | 155 | Existing example, v2beta2 API — **rewrite to v2** |
| `charts/examples/flux/kustomization.yaml` | exists | Multi-env pattern — **add valuesFrom + SOPS** |
| `charts/examples/flux/ocirepository.yaml` | NEW | OCIRepository with Cosign verification |
| `packages/floe-core/src/floe_core/cli/platform/compile.py` | 375 | `floe platform compile` — **add --output-format flag** |
| `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 827 | `to_json_file()`, `to_yaml_file()` — **add to_configmap_file()** |
| `.github/workflows/helm-release.yaml` | ~120 | OCI push workflow — **add Cosign step** |

## Design Decisions

- D5: Hybrid values pattern (inline toggles + ConfigMap compiled values)
- D6: SOPS (Age) default, ESO documented alternative
- D7: Template repo over CLI subcommand (template repo is Phase 2 future work, not this unit)

## CLI Integration

The `floe platform compile` command currently supports `--output` (file path) with
default `target/compiled_artifacts.json`. The new `--output-format` flag controls format:

```
--output-format json    (default, existing behavior)
--output-format yaml    (existing .yaml support)
--output-format configmap  (NEW: Kubernetes ConfigMap wrapping values)
```

The ConfigMap format wraps compiled values in a standard K8s ConfigMap:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: floe-compiled-values    # overridable via --configmap-name
data:
  values.yaml: |
    # compiled platform values
```

This integrates with Flux's `valuesFrom: kind: ConfigMap` pattern.

## OCI Publishing

The `helm-release.yaml` workflow already pushes to GHCR OCI. This unit adds:
- Cosign keyless signing step (Sigstore OIDC, no keys to manage)
- Uses `cosign sign --yes` with GitHub OIDC identity

## Flux Example Modernization

Current state:
- `helmrelease.yaml` uses v2beta2 API (deprecated), HelmRepository source, no remediation strategy
- `kustomization.yaml` has multi-env pattern but no valuesFrom or SOPS

Target state:
- v2 GA API, OCIRepository source, `strategy: uninstall` remediation
- valuesFrom ConfigMap pattern, SOPS decryption example
- New `ocirepository.yaml` with Cosign verification

## Gotchas

- SemVer `>=1.0.0` does NOT match pre-releases — must use `>=1.0.0-0` in examples
- ConfigMap output must produce valid YAML that can be `kubectl apply`'d
- Cosign keyless signing requires `permissions: id-token: write` in GitHub Actions
- SOPS example must reference Age, not GPG (Age is simpler for the target audience)

## Dependencies

- Independent of Units 1 and 2 (test infrastructure)
- Can be built in parallel with Unit 2
