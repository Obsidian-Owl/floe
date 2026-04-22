# GitOps with Flux

This guide describes the supported public Flux workflow for `floe-platform`.
The public path is:

1. Track the published chart with `charts/examples/flux/ocirepository.yaml`
2. Deploy it with `charts/examples/flux/helmrelease.yaml`
3. Keep those manifests in a GitRepository-driven environment overlay like
   `charts/examples/flux/kustomization.yaml`
4. Generate compiled values into a ConfigMap and layer environment-specific
   overrides through `valuesFrom`

## Public Inputs and Knobs

These are the operator-facing controls for the public Flux path:

| Knob | Default | Why it matters |
|------|---------|----------------|
| Chart OCI reference | `oci://ghcr.io/obsidian-owl/charts/floe-platform` | Public release source tracked by Flux |
| Chart version knob | `spec.ref.tag` or `spec.ref.semver` in `ocirepository.yaml` | Controls which published chart version Flux pulls |
| ConfigMap name | `floe-compiled-values` | Name used by `valuesFrom` for compiled values |
| ConfigMap namespace | omitted by default | For Flux, set it to the same namespace as the HelmRelease |
| HelmRelease namespace | `flux-system` in the example | Namespace that stores the source, HelmRelease, ConfigMap, and Secret |
| Workload target namespace | `floe-dev` in the example | Namespace where the chart installs platform workloads |
| Secret override name | `floe-platform-overrides` | Optional second `valuesFrom` layer for environment-specific overrides |

## Recommended Repository Layout

Keep the environment overlay in Git even though the chart itself is pulled from
OCI:

```text
clusters/
  dev/
    floe-platform/
      kustomization.yaml
      ocirepository.yaml
      helmrelease.yaml
      compiled-values-configmap.yaml
      secret.enc.yaml
```

- `compiled-values-configmap.yaml` is rendered by `floe platform compile`
- `secret.enc.yaml` is the default Age/SOPS-encrypted secret example
- If your secrets source of truth lives outside Git, replace the encrypted
  secret with an External Secrets Operator manifest and keep the same
  `valuesFrom` contract

## Generate the Compiled Values ConfigMap

`floe platform compile` supports a public ConfigMap output mode.

```bash
floe platform compile \
  --spec floe.yaml \
  --manifest manifest.yaml \
  --output-format configmap \
  --output clusters/dev/floe-platform/compiled-values-configmap.yaml \
  --configmap-name floe-compiled-values \
  --namespace flux-system
```

Important details:

- `--output-format configmap` switches the CLI to ConfigMap output
- `--configmap-name` defaults to `floe-compiled-values`; override it if you
  need multiple releases in the same namespace
- `--namespace` is optional in the CLI, but for Flux you should set it to the
  same namespace as the HelmRelease so `valuesFrom` resolves the ConfigMap
  without surprises
- If you omit `--output`, the default path is `target/floe-compiled-values.yaml`

## Track the Published Chart

The public chart reference is:

```text
oci://ghcr.io/obsidian-owl/charts/floe-platform
```

Set the version you want Flux to consume in `ocirepository.yaml`:

```yaml
spec:
  ref:
    tag: "0.1.0"
```

Use `ref.tag` for an exact chart version pin. Use `ref.semver` if you want a
range-based update policy.

## Wire valuesFrom for ConfigMap and Secret Data

The supported public `valuesFrom` pattern is:

```yaml
spec:
  valuesFrom:
    - kind: ConfigMap
      name: floe-compiled-values
      valuesKey: values.yaml
    - kind: Secret
      name: floe-platform-overrides
      valuesKey: values.yaml
      optional: true
```

This layering keeps the generated platform values and the environment-specific
secret overrides separate:

- The ConfigMap carries compiled non-secret values
- The Secret carries environment-specific sensitive overrides
- Both objects live in the same namespace as the HelmRelease

## Secret Management Options

The public examples assume Age/SOPS as the default in-repo encrypted-secret
workflow:

```yaml
spec:
  decryption:
    provider: sops
    secretRef:
      name: sops-age
```

If you do not want encrypted secrets in Git, keep the same `valuesFrom` Secret
contract and generate that Secret with External Secrets Operator instead.

## Example Entry Points

- OCI source example: [charts/examples/flux/ocirepository.yaml](../../../charts/examples/flux/ocirepository.yaml)
- HelmRelease example: [charts/examples/flux/helmrelease.yaml](../../../charts/examples/flux/helmrelease.yaml)
- Kustomization example: [charts/examples/flux/kustomization.yaml](../../../charts/examples/flux/kustomization.yaml)
- Helm install guide: [kubernetes-helm.md](./kubernetes-helm.md)
