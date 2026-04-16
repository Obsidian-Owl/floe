# Plan: flux-user-gitops

**Unit**: 3 of 3
**Parent**: flux-gitops-implementation

## Task Breakdown

### Task 1: Rewrite Flux examples (helmrelease, ocirepository, kustomization)

**Files:**
- MODIFY `charts/examples/flux/helmrelease.yaml` — Rewrite: v2beta2 -> v2, add OCIRepository ref, add remediation strategy
- CREATE `charts/examples/flux/ocirepository.yaml` — OCIRepository with Cosign verification
- MODIFY `charts/examples/flux/kustomization.yaml` — Add valuesFrom ConfigMap pattern, SOPS decryption example

**Acceptance criteria covered:** AC-1, AC-2, AC-3

**Approach:**
- HelmRelease: restructure from HelmRepository source to OCIRepository, add remediation block
- OCIRepository: v1beta2 API (OCIRepository is still beta in Flux), Cosign keyless verify
- Kustomization: add decryption spec for SOPS with Age, add valuesFrom ConfigMap reference
- Each file includes user-facing comments explaining setup steps
- Tests: YAML structure validation (unit tier)

### Task 2: Add to_configmap_yaml to CompiledArtifacts

**Files:**
- MODIFY `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` — Add `to_configmap_yaml()` method

**Acceptance criteria covered:** AC-9

**Approach:**
- Add method after existing `to_yaml_file()` (~line 740)
- Signature: `to_configmap_yaml(name: str = "floe-compiled-values", namespace: str | None = None) -> str`
- Uses `yaml.dump()` for the values content (same serialization as `to_yaml_file()`)
- Wraps in ConfigMap structure with `apiVersion: v1`, `kind: ConfigMap`
- Tests: unit tests verifying ConfigMap YAML structure and content

### Task 3: Add --output-format flag to floe platform compile

**Files:**
- MODIFY `packages/floe-core/src/floe_core/cli/platform/compile.py` — Add `--output-format` and `--configmap-name` flags, wire to `to_configmap_yaml()`

**Acceptance criteria covered:** AC-4, AC-5, AC-6, AC-7

**Approach:**
- Add `--output-format` click option with choices `["json", "yaml", "configmap"]`, default `"json"`
- Add `--configmap-name` click option, default `"floe-compiled-values"`
- Add `--namespace` click option (optional, for ConfigMap metadata)
- In the output section (~line 173): branch on format, call appropriate method
- Default output filename changes to `floe-compiled-values.yaml` when format is configmap
- Tests: unit tests for each format, verify existing formats unchanged

### Task 4: Add Cosign signing step to helm-release workflow

**Files:**
- MODIFY `.github/workflows/helm-release.yaml` — Add Cosign install + sign step after OCI push

**Acceptance criteria covered:** AC-8

**Approach:**
- Add `sigstore/cosign-installer` action step before the signing step
- Add `cosign sign --yes` step after existing OCI push step
- Add `permissions: id-token: write` to the job
- Mark signing step with `continue-on-error: true` (best-effort)
- Tests: YAML structure validation (unit tier — workflow syntax)

## File Change Map

| File | Action | Lines Changed (est.) |
|------|--------|---------------------|
| `charts/examples/flux/helmrelease.yaml` | REWRITE | ~100 (was 155) |
| `charts/examples/flux/ocirepository.yaml` | CREATE | ~30 |
| `charts/examples/flux/kustomization.yaml` | MODIFY | +25 |
| `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | MODIFY | +35 |
| `packages/floe-core/src/floe_core/cli/platform/compile.py` | MODIFY | +40 |
| `.github/workflows/helm-release.yaml` | MODIFY | +15 |

## Dependencies

- Independent of Units 1 and 2
- Can be built in parallel with Unit 2

## Risks

- CompiledArtifacts is the sole cross-package contract — changes must be additive only
- The existing `to_yaml_file()` serialization must be reused exactly (no format drift)
- GitHub Actions workflow changes can only be fully tested on push (no local test runner)
- Cosign keyless signing requires GitHub OIDC — cannot be tested in forks without setup

## As-Built Notes

- Task 1: OCIRepository uses GA `source.toolkit.fluxcd.io/v1` (not v1beta2 as plan noted).
  Flux 2.6+ promoted OCIRepository to GA v1. Tests verify this.
- Task 2: `to_configmap_yaml()` uses a custom `_BlockDumper` (subclass of SafeDumper) to
  render the embedded values as YAML block scalar (`|`). Without it, PyYAML double-quotes
  multi-line strings making the output unreadable.
- Task 3: Default output path is computed dynamically when `--output` matches the Click
  default (`target/compiled_artifacts.json`). This avoids a Click callback which would
  complicate the option interdependency.
- Task 4: Cosign sign step uses env vars (`OCI_REGISTRY`, `OCI_REGISTRY_PATH`) rather than
  direct `${{ env.X }}` interpolation in `run:` to follow GitHub Actions security best
  practices (avoid expression injection in shell commands).
