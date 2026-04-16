# Spec: flux-user-gitops

**Unit**: 3 of 3
**Parent**: flux-gitops-implementation
**Purpose**: Deliver user-facing GitOps artifacts: updated examples, ConfigMap CLI output, OCI signing

## Acceptance Criteria

### AC-1: Flux example HelmRelease uses v2 GA API [tier: unit]

`charts/examples/flux/helmrelease.yaml` is rewritten with:
- `apiVersion: helm.toolkit.fluxcd.io/v2` (not v2beta2)
- `spec.chart.spec.sourceRef` referencing an OCIRepository (not HelmRepository)
- `spec.upgrade.remediation.strategy: rollback` (Flux default — safe for production)
  with `retries: 3` and `remediateLastFailure: true`
- `spec.upgrade.cleanupOnFail: true`
- A comment block explaining the `uninstall` strategy as an alternative for test/dev
  environments: "# For test environments, use `strategy: uninstall` for aggressive recovery"
- `spec.valuesFrom` with a ConfigMap example (commented, with inline instructions)
- Each top-level `spec` field has an inline comment explaining its purpose

Note: The test infrastructure (Unit 1) uses `strategy: uninstall` for aggressive
auto-healing. The user-facing example defaults to `rollback` because `uninstall` is
destructive — on upgrade failure, the entire release is deleted and reinstalled,
causing downtime.

### AC-2: OCIRepository example with Cosign verification [tier: unit]

`charts/examples/flux/ocirepository.yaml` (NEW) contains:
- `apiVersion: source.toolkit.fluxcd.io/v1` (GA — promoted from v1beta2 in Flux 2.6)
- `metadata.name: floe-platform` in namespace `flux-system`
- `spec.url: oci://ghcr.io/floe-platform/charts/floe-platform`
- `spec.interval: 5m`
- `spec.verify.provider: cosign` with keyless verification config
- SemVer range using `>=1.0.0-0` (not `>=1.0.0`) with a comment explaining the `-0`
  suffix: "# -0 suffix matches pre-release versions (e.g., 1.0.0-rc.1)"

### AC-3: Kustomization example with valuesFrom and SOPS [tier: unit]

`charts/examples/flux/kustomization.yaml` is updated to include:
- A `valuesFrom` ConfigMap reference pattern (showing how `floe compile --output-format=configmap`
  output integrates)
- A SOPS decryption example using Age (not GPG), presented as **commented-out YAML** with
  step-by-step setup instructions in comments:
  ```
  # To enable SOPS decryption:
  # 1. Generate an Age key: age-keygen -o age.agekey
  # 2. Create .sops.yaml with age recipient
  # 3. Create K8s secret: kubectl create secret generic sops-age --from-file=age.agekey
  # 4. Uncomment the decryption block below:
  # decryption:
  #   provider: sops
  #   secretRef:
  #     name: sops-age
  ```
- ESO mentioned as an enterprise alternative in comments

### AC-4: `floe platform compile --output-format=configmap` produces valid ConfigMap [tier: unit]

`floe platform compile --output-format=configmap` writes a file containing:
- Valid Kubernetes ConfigMap YAML (`apiVersion: v1`, `kind: ConfigMap`)
- `metadata.name` defaulting to `floe-compiled-values`
- `data.values.yaml` containing the full compiled platform values as a YAML block scalar
  (`|`), preserving newlines and indentation. When parsed, the embedded YAML is
  semantically equivalent to `to_yaml_file()` output.
- The output is valid YAML that can be applied via `kubectl apply -f`

**Output path behavior**: When `--output-format=configmap` is specified and `--output`
is NOT provided, the default output path is `target/floe-compiled-values.yaml` (not the
json default). When `--output` IS provided, it is used as-is regardless of format.
The Click option's default is computed dynamically based on `--output-format`.

### AC-5: `--configmap-name` flag overrides ConfigMap metadata.name [tier: unit]

`floe platform compile --output-format=configmap --configmap-name=my-values` produces
a ConfigMap with `metadata.name: my-values`. When `--output-format` is not `configmap`
and `--configmap-name` is provided, a warning is logged ("--configmap-name is only
used with --output-format=configmap") and the flag is ignored.

### AC-6: Existing output formats unchanged [tier: unit]

`floe platform compile --output-format=json` produces a JSON file containing the
Pydantic model dump with `mode="json"` and `by_alias=True` — identical to the current
`to_json_file()` behavior. `floe platform compile --output-format=yaml` produces
the same YAML output as `to_yaml_file()`. No existing behavior is changed. The default
`--output-format` is `json`.

### AC-7: ConfigMap output includes namespace metadata [tier: unit]

The ConfigMap YAML output includes `metadata.namespace` only when `--namespace` is
provided. When omitted, the `namespace` key is entirely absent from the output YAML
(not null, not empty string — absent). Follows kubectl convention for namespace-less
manifests that inherit from the apply context.

### AC-8: Cosign keyless signing in helm-release workflow [tier: unit]

`.github/workflows/helm-release.yaml` includes a step after OCI push that:
- Uses `sigstore/cosign-installer` action to install cosign
- Runs `cosign sign --yes` with the chart's full OCI reference (including digest from
  the push step output, not just tag — digest-based signing is more secure)
- The job has `permissions: id-token: write, packages: write`
- The signing step uses `continue-on-error: true` (GitHub Actions mechanism for
  best-effort — the step can fail without failing the workflow)
- Signing applies to all charts pushed in the workflow (both `floe-platform` and
  `floe-jobs` if present), not just `floe-platform`

This AC is tested as a structural YAML check (parse workflow YAML, assert step exists
with expected properties). Full signing validation requires a real GitHub Actions run.

### AC-9: CompiledArtifacts has to_configmap_yaml method [tier: unit]

`CompiledArtifacts` class in `compiled_artifacts.py` has a new method:
```python
def to_configmap_yaml(
    self,
    name: str = "floe-compiled-values",
    namespace: str | None = None,
) -> str:
```
That:
- Returns a string containing valid ConfigMap YAML
- Uses `yaml.safe_dump` with the same `model_dump(mode="json", by_alias=True)` as
  `to_yaml_file()` for the values content
- Embeds the values as a YAML block scalar (`|`) under `data.values.yaml`
- Includes `metadata.namespace` only when `namespace` is not None
- Does NOT add a `to_configmap_file()` — the CLI handles file I/O

## WARNs from Spec Review (Accepted)

- WARN-4: AC-8 revised to specify `continue-on-error: true` mechanism
- WARN-5: AC-1 revised to specify "each top-level spec field has an inline comment"
- WARN-6: AC-3 revised to specify commented-out YAML with setup instructions
- WARN-7: AC-4/AC-9 revised to specify YAML block scalar and semantic equivalence
- WARN-8: ACs 1/2/3/8 are structural YAML checks tested as unit tests (parse + assert)
- INFO-9: AC-6 revised with positive specification of json format
- INFO-10: AC-5 revised to emit warning when flag is ignored
- INFO-12: AC-2 revised to include comment explaining `-0` suffix
- INFO-13: AC-9 revised with explicit type annotation for namespace parameter
