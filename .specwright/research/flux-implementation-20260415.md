# Research Brief: Flux v2 Implementation for Floe Platform

**Topic ID**: flux-implementation
**Date**: 2026-04-15
**Status**: Active
**Confidence**: HIGH (Tracks 1-3, Q1-Q5), MEDIUM (Track 4, DX progressive adoption)

## Triggering Questions

1. How do we implement Flux v2 to stabilize test infrastructure (auto-heal stuck Helm releases)?
2. What are the implications for Floe platform users deploying via GitOps?
3. How does Flux change the `floe compile` → `floe deploy` flow?
4. How do competitors handle K8s deployment and GitOps?

---

## Track 1 — Flux v2 for Test Infrastructure (Kind Cluster)

### Installation

Two paths for Kind:

- **`flux bootstrap github`**: Full GitOps — pushes Flux manifests to Git repo, cluster syncs from Git. Requires live Git connectivity. Idempotent. Kind is explicitly supported in docs.
- **`flux install`**: Dev/testing path — installs controllers without Git source. Appropriate for ephemeral Kind clusters.

**Minimal install** (skip notification + kustomize controllers):
```bash
flux install --components="source-controller,helm-controller"
```
This subset is sufficient for HelmRelease management. Confirmed by `--components` flag in CLI docs. Community-supported but not explicitly documented as a "supported configuration."

**Resource footprint** (from controller deployment manifests):
- source-controller: 50m/64Mi request, 1000m/1Gi limit
- helm-controller: 100m/64Mi request, 1000m/1Gi limit
- **Total minimal**: ~150m CPU / 128Mi memory request

### HelmRelease Remediation (the key value proposition)

**Retry + uninstall sequencing** (from API reference):
> "Retries is the number of retries that should be attempted on failures before bailing. Remediation, using the Strategy, is performed **between each attempt**."

With `strategy: uninstall` and `retries: 3`:
1. Upgrade attempt 1 fails → **uninstall** → attempt 2
2. Attempt 2 fails → **uninstall** → attempt 3
3. Attempt 3 fails → **uninstall** → attempt 4 (final)
4. Attempt 4 fails → bail (unless `remediateLastFailure: true`)

It does NOT rollback N times then uninstall once. It is **uninstall-between-each-retry**.

**`remediateLastFailure`**: Defaults to `true` when `retries > 0`. Controls whether remediation fires after the final exhausted retry.

**PVC behavior during uninstall**: NOT explicitly documented. PVCs created by StatefulSet `volumeClaimTemplates` are NOT Helm-owned → they survive uninstall regardless. Namespace is NOT deleted. Known issue #2299: resources with custom finalizers may not be cleaned up.

**StatefulSet immutable fields**: `strategy: uninstall` sidesteps this entirely — full uninstall+reinstall handles any field change. This is why Flux docs recommend `uninstall` over `rollback` for StatefulSet-containing charts.

### Local Chart Path — NOT Supported

A HelmRelease cannot point to a local filesystem path. Supported sources:
- `HelmRepository` (HTTP/OCI registry)
- `GitRepository` (charts in Git at a relative path)
- `Bucket` (S3-compatible storage)

For Kind dev iteration: use `GitRepository` pointing to the repo, with `chart: "./charts/floe-platform"` as relative path. Changes must be committed before Flux picks them up. For rapid iteration without Git commits, use direct `helm` CLI outside Flux.

### Kind Image Loading Compatibility

Flux does NOT interfere with `kind load docker-image`. Flux has no image-pulling logic of its own (image automation is a separate optional component). Charts setting `imagePullPolicy: IfNotPresent` will use locally-loaded images.

**Source**: [Flux Installation](https://fluxcd.io/flux/installation/), [Helm API v2](https://fluxcd.io/flux/components/helm/api/v2/), [flux install CLI](https://fluxcd.io/flux/cmd/flux_install/)

---

## Track 2 — Flux as Deployment Model for Floe Platform Users

### Config Flow Change

**Current**: `floe compile` → `CompiledArtifacts` → `floe deploy` (runs `helm upgrade`)
**With Flux**: `floe compile` → writes HelmRelease manifest (or ConfigMap with values) → Git commit → Flux reconciles

Two patterns for version-controlling compiled output:

**Pattern A (Direct)**: `floe compile` writes `clusters/<env>/floe-platform/helmrelease.yaml` with computed `spec.values`. CI commits. Flux reconciles.

**Pattern B (ConfigMap, recommended by Flux maintainer Stefan Prodan)**:
- `floe compile` writes a `values.yaml` file
- Kustomize `configMapGenerator` wraps it into a ConfigMap with content hash
- HelmRelease references via `spec.valuesFrom: kind: ConfigMap`
- Hash change triggers immediate reconciliation
- Separates "who owns config" from "who owns release definition"

### Multi-Environment Promotion

**Directory-based (recommended)**: All environments on one branch, directory per env:
```
clusters/
  staging/floe-platform/helmrelease.yaml
  production/floe-platform/helmrelease.yaml
```

**Production gate**: CI detects successful staging deploy → opens PR against production config → human reviews and merges → Flux reconciles production.

### Secrets Management

Flux does NOT recommend one approach. Three documented options:
- **SOPS**: Encrypts secrets in Git, Flux decrypts. Supports AWS KMS, GCP KMS, Azure KeyVault, HashiCorp Vault, Age, PGP.
- **Sealed Secrets**: Encrypted K8s resources, in-cluster controller decrypts.
- **External Secrets Operator (ESO)**: Syncs from external stores (Vault, AWS SM).

All three can feed into `spec.valuesFrom: kind: Secret` — HelmRelease injects credentials without storing them in Git.

### OCI Chart Distribution

**Recommended since Flux v2.3**: Use `OCIRepository` + `chartRef` (not `HelmRepository`):
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: floe-platform-chart
spec:
  url: oci://ghcr.io/floe-platform/charts/floe-platform
  ref:
    semver: ">=1.0.0"
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
spec:
  chartRef:
    kind: OCIRepository
    name: floe-platform-chart
```

Charts published via standard `helm push chart.tgz oci://...`.

### Drift Detection

**Opt-in** (disabled by default). When `mode: enabled`:
- Manual `kubectl` edits are reverted on next reconciliation
- Selective disable via `ignore` rules (e.g., skip `/spec/replicas` for HPA-managed)
- Per-resource annotation `helm.toolkit.fluxcd.io/driftDetection: disabled` (had a bug in early versions, now fixed)

**Source**: [Flux for Helm Users](https://fluxcd.io/flux/use-cases/helm/), [Repository Structure](https://fluxcd.io/flux/guides/repository-structure/), [Secrets Management](https://fluxcd.io/flux/security/secrets-management/), [OCI cheatsheet](https://fluxcd.io/flux/cheatsheets/oci-artifacts/)

---

## Track 3 — Architecture Implications for Floe

### Plugin System Compatibility

Fully compatible. `spec.values` is a plain Helm values map — the existing `condition:` pattern (`dagster.enabled`, `polaris.enabled`, etc.) works unchanged. For multi-plugin values, `spec.valuesFrom` supports ordered list (later entries override earlier):
```yaml
spec:
  valuesFrom:
    - kind: ConfigMap
      name: floe-base-values        # platform defaults
    - kind: ConfigMap
      name: floe-plugin-s3-values   # storage plugin
    - kind: ConfigMap
      name: floe-plugin-polaris-values  # catalog plugin
    - kind: Secret
      name: floe-secrets            # credentials (highest priority)
```

### Plugin Dependencies

`spec.dependsOn` enforces inter-release ordering. Catalog can depend on storage:
```yaml
spec:
  dependsOn:
    - name: floe-minio
```

**Limitation**: `dependsOn` is primarily enforced during initial install. After all releases are installed, they reconcile independently. For runtime dependency, use init containers / liveness probes.

### Helm Hooks (Polaris Bootstrap)

Flux executes Helm hooks by default (`disableHooks: false`). Wait-for-job is also enabled by default.

**Critical caveat**: Polaris bootstrap uses post-install hooks (Jobs). If application pods have init-containers that wait for hook Jobs, the `--wait` creates a deadlock. Fix: set `disableWait: true` on install/upgrade.

### No Chart Changes Required

Flux is transparent to chart authors. No `flux.enabled` value needed. No required annotations. The Helm SDK is called identically to `helm install`/`helm upgrade`.

One consideration: the existing example at `charts/examples/flux/helmrelease.yaml` uses API version `v2beta2`. The current GA version is `v2` (promoted in Flux v2.3). Should be updated.

### E2E Testing with Flux

**Suspend/resume pattern** for upgrade path tests:
```bash
flux suspend helmrelease floe-platform -n floe-test
helm upgrade ...  # manual upgrade for testing
# run assertions
flux resume helmrelease floe-platform -n floe-test
```

**Caveat**: CLI `suspend` is not persisted to Git. If Kustomize controller reconciles during test, it overwrites `suspend: true` from Git. Must also suspend the parent Kustomization or commit `suspend: true`.

**Flux's built-in test support**: `spec.test.enable: true` runs `helm test` after each install/upgrade. Results in HelmRelease status.

**Source**: [Helm Releases](https://fluxcd.io/flux/components/helm/helmreleases/), [Helm API v2](https://fluxcd.io/flux/components/helm/api/v2/), [flux suspend](https://fluxcd.io/flux/cmd/flux_suspend_helmrelease/)

---

## Track 4 — Competitive Landscape

### Data Platform Deployment Patterns

| Platform | Helm Chart | GitOps Guidance | CRDs | Notes |
|----------|-----------|----------------|------|-------|
| **Airbyte** | Yes (V2, Oct 2025) | None | No | Connectors configured via API, not Helm |
| **Astronomer/Airflow** | Yes (two charts) | None official | No | Community ArgoCD guides exist |
| **Dagster** | Yes (two charts: infra + user code) | None official | No | Two-chart model maps to Flux `dependsOn` |
| **Meltano** | Community only | None | No | CLI tool, not a K8s platform |
| **Floe** | Yes (umbrella) | **Flux + ArgoCD examples** | No | Ahead of all competitors |

**Key insight**: No competitor provides official GitOps guidance or examples. Floe is uniquely positioned by already having Flux/ArgoCD templates. Making these production-ready would be a differentiator.

**Common pattern**: All use standard K8s resources (no CRDs), conditional subchart toggles, Helm as primary deployment mechanism. GitOps is left to operators.

**Dagster's two-chart model**: Infrastructure chart + user code chart with separate lifecycle. Maps cleanly to two Flux HelmReleases with `dependsOn`. Relevant because Floe embeds Dagster.

**Confidence**: HIGH for Airbyte/Dagster (official docs), MEDIUM for Astronomer (repo found, docs 404), LOW for Meltano (no K8s docs).

**Source**: [Airbyte Docs](https://docs.airbyte.com/platform/deploying-airbyte), [Dagster K8s Docs](https://docs.dagster.io/deployment/oss/deployment-options/kubernetes/customizing-your-deployment), [Meltano Production Guide](https://docs.meltano.com/guide/production/)

---

## Resolved Questions (Deepened Research)

### Q1: HelmRelease Manifests vs ConfigMaps for `floe deploy`

**Recommendation: Hybrid approach (Pattern C)**

Neither pure Pattern A (inline `spec.values`) nor pure Pattern B (ConfigMap) alone. Use both:

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
spec:
  values:
    # Plugin toggles — static, rarely change
    dagster:
      enabled: true
    polaris:
      enabled: true
  valuesFrom:
    - kind: ConfigMap
      name: floe-compiled-values  # Hash in name triggers reconcile
    - kind: Secret
      name: floe-secrets
      optional: true
```

**Why hybrid wins:**
- Plugin toggles (`dagster.enabled`, `polaris.enabled`) belong inline — they define the release shape and are version-controlled alongside the HelmRelease
- Compiled output from `floe compile` goes in ConfigMap — hash-based names trigger immediate reconciliation on config change
- Secrets always via `valuesFrom: kind: Secret` — never inline
- `spec.valuesFrom` ordering provides clean precedence: base → compiled → secrets

**ConfigMap hash mechanism (Kustomize):**
```yaml
# kustomization.yaml
configMapGenerator:
  - name: floe-compiled-values
    files:
      - values.yaml=compiled-values.yaml
    options:
      disableNameSuffixHash: false  # default: hash appended
```
Kustomize appends content hash to name (e.g., `floe-compiled-values-abc123`). The HelmRelease `valuesFrom` reference is rewritten automatically via `kustomizeconfig.yaml` `nameReference` transformer.

**Confidence**: HIGH — this is the pattern Flux maintainer Stefan Prodan recommends and what production users converge on.

---

### Q2: Ephemeral Namespaces vs Flux for Test Isolation

**Recommendation: Complementary — Flux for steady-state, ephemeral for CI isolation**

Three isolation tiers:

| Tier | Mechanism | Use Case | Startup |
|------|-----------|----------|---------|
| **Dev** | Single Flux-managed namespace | Local Kind cluster, `floe-test` | Already running |
| **CI** | Ephemeral namespace per CI run | GitHub Actions, parallel PRs | ~30s (namespace create + Helm install) |
| **Heavy isolation** | vCluster per CI run | Multi-tenant, security-sensitive | ~10s (virtual control plane) |

**Flux's own CI pattern**: Flux project itself uses ephemeral Kind clusters per CI run — not Flux-in-Flux. Tests deploy Flux from scratch, run assertions, tear down. This avoids the complexity of managing Flux per-namespace.

**vCluster for test isolation**: Virtual K8s clusters inside a host cluster. Starts in seconds (vs minutes for Kind). Each vCluster gets its own API server, scheduler, controller-manager. Resources sync to host cluster as namespaced resources. Good for testing multi-cluster scenarios.

**For Floe's E2E tests**: Current approach (single `floe-test` namespace with Helm) is appropriate for dev. For CI, use ephemeral namespaces with unique release names per run. Flux is NOT needed inside CI — it's for production steady-state.

**Confidence**: HIGH — validated against Flux's own CI, vCluster docs, and community patterns.

---

### Q3: `floe flux bootstrap` CLI Subcommand vs Template Repo

**Recommendation: Forkable template repo (not a CLI subcommand)**

**Why template repo wins over CLI:**
- `flux create helmrelease --export` already generates HelmRelease YAML — a CLI wrapper adds marginal value
- Template repo includes directory structure, Kustomize overlays, CI workflows, secrets config — things a CLI can't maintain
- Users `git clone` → customize → push → Flux reconciles
- Template stays current via GitHub template repo mechanism
- No Floe CLI dependency for GitOps users

**Template repo structure:**
```
floe-gitops-template/
├── clusters/
│   ├── dev/
│   │   ├── kustomization.yaml
│   │   └── floe-platform/
│   │       ├── helmrelease.yaml
│   │       ├── values.yaml
│   │       └── kustomizeconfig.yaml
│   ├── staging/
│   │   └── floe-platform/
│   │       ├── kustomization.yaml  # patches over dev
│   │       └── values-override.yaml
│   └── production/
│       └── floe-platform/
│           ├── kustomization.yaml
│           └── values-override.yaml
├── infrastructure/
│   ├── flux-system/        # Flux controllers
│   ├── sources/            # OCIRepository, HelmRepository
│   └── secrets/            # SOPS-encrypted or ESO templates
├── scripts/
│   └── setup.sh            # One-liner: flux bootstrap + apply
└── README.md
```

**What Floe CLI SHOULD provide**: `floe compile --output-format=configmap` — writes compiled values as a ConfigMap-ready YAML that drops into the template repo. This is the natural integration point.

**Confidence**: HIGH — aligns with Flux community pattern. ArgoCD also uses template repos (e.g., `argocd-example-apps`).

---

### Q4: SOPS vs External Secrets Operator (ESO)

**Recommendation: Support both, default to SOPS (Age), document ESO as enterprise option**

| Dimension | SOPS (Age) | ESO |
|-----------|-----------|-----|
| **Dependencies** | None (built into kustomize-controller) | 3 extra pods (operator + webhook + cert-controller) |
| **Key management** | Age key in K8s Secret or KMS | Cloud KMS / Vault / AWS SM |
| **Rotation** | Manual re-encrypt | Auto-sync (configurable interval) |
| **Multi-env** | One Age key per environment | One SecretStore per env, one ExternalSecret per secret |
| **Complexity** | Low (encrypt file, commit) | Medium (CRDs, stores, sync policies) |
| **Flux integration** | Native (decryption built in) | External (ESO controller manages K8s Secrets, Flux consumes them) |
| **Enterprise fit** | Small/medium teams | Large teams with existing Vault/AWS SM |

**SOPS workflow:**
```bash
# One-time: generate Age key
age-keygen -o age.key
# Encrypt
sops --encrypt --age age1... values-secrets.yaml > values-secrets.enc.yaml
# Flux decrypts automatically via kustomize-controller decryption config
```

**ESO workflow:**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
  data:
    - secretKey: polaris-credential
      remoteRef:
        key: floe/production/polaris
```

**Floe integration**: Add `secrets.provider` field to `manifest.yaml`:
```yaml
secrets:
  provider: sops  # or "eso" or "sealed-secrets"
  sops:
    ageRecipients: age1...
```
`floe compile` generates the appropriate secret reference format based on provider.

**Confidence**: HIGH for SOPS, MEDIUM for ESO (ESO API is stable but more complex to validate).

---

### Q5: OCI Chart Publishing Pipeline

**Recommendation: GHCR (GitHub Container Registry) with Cosign keyless signing**

**Why GHCR:**
- Free for public repos (Floe is open source)
- No rate limits for authenticated pulls (unlike Docker Hub's 100 pulls/6h)
- Native GitHub Actions integration (`docker/login-action` + `helm push`)
- Same auth as source code (`GITHUB_TOKEN`)

**Publishing pipeline (GitHub Actions):**
```yaml
name: Release Chart
on:
  push:
    tags: ['v*']
jobs:
  publish:
    steps:
      - uses: azure/setup-helm@v4
        with:
          version: v3.14.0
      - run: helm package charts/floe-platform
      - run: helm push floe-platform-*.tgz oci://ghcr.io/floe-platform/charts
      - uses: sigstore/cosign-installer@v3
      - run: cosign sign --yes ghcr.io/floe-platform/charts/floe-platform:$TAG
```

**Cosign keyless signing**: Uses Sigstore OIDC — no key management. GitHub Actions identity is the signing key. Flux verifies via:
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
spec:
  verify:
    provider: cosign
    matchOIDCIdentity:
      - issuer: https://token.actions.githubusercontent.com
        subject: https://github.com/floe-platform/floe/.github/workflows/release.yml@refs/tags/*
```

**SemVer pre-release trap**: `>=1.0.0` does NOT match pre-releases like `1.0.0-rc.1`. Must use `>=1.0.0-0` (the `-0` is the lowest pre-release identifier). This is critical for alpha/beta users.

**Consumer-side (Flux user):**
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: floe-platform-chart
spec:
  url: oci://ghcr.io/floe-platform/charts/floe-platform
  ref:
    semver: ">=1.0.0-0"  # Include pre-releases
  verify:
    provider: cosign
    matchOIDCIdentity:
      - issuer: https://token.actions.githubusercontent.com
        subject: https://github.com/floe-platform/floe/*
```

**Confidence**: HIGH — GHCR + Cosign is the standard for open-source Helm charts. Used by Flux itself, Cilium, Crossplane.

---

### Developer Experience Analysis

**Progressive GitOps adoption path** (critical for DX):

1. **Day 0 — Imperative** (current): `floe compile && floe deploy` runs `helm upgrade` directly. No Flux.
2. **Day 1 — GitOps-aware**: `floe compile --output-format=configmap` writes values. User commits. Flux reconciles.
3. **Day 2 — Full GitOps**: Template repo with multi-env, SOPS secrets, OCI chart source, drift detection.

Flux auto-adopts existing Helm releases — users don't need to uninstall and reinstall. The HelmRelease CRD takes over management of the existing release by matching release name and namespace.

**`flux debug helmrelease`** (preview/experimental in Flux v2.5): Surfaces reconciliation failures, source fetch errors, and remediation history. Useful but not yet stable enough to recommend as primary debugging tool.

**Key DX insight**: The biggest friction point is NOT Flux itself — it's the gap between "I have a `floe.yaml`" and "I have a GitOps-managed deployment." The template repo + `floe compile --output-format=configmap` bridges this gap.

---

## Synthesis: Dual-Purpose Value

Flux solves two problems simultaneously:

1. **Test infrastructure** (immediate): Auto-heals stuck Helm releases via `strategy: uninstall`. Eliminates the cascading 306-error failure mode. Lightweight footprint (~128Mi) fits Kind.

2. **Platform deployment** (strategic): Positions Floe as the only data platform with first-class GitOps support. `floe compile` → Git commit → Flux reconcile is a clean, auditable deployment model. Multi-environment promotion, drift detection, and secrets management come for free.

### Recommended Implementation Sequence

| Phase | Scope | Effort | Value |
|-------|-------|--------|-------|
| **1. Test infra** | Flux in Kind, HelmRelease with `strategy: uninstall` | 1-2 days | Eliminates stuck release cascading failures |
| **2. OCI publishing** | GHCR + Cosign in GitHub Actions release workflow | 1 day | Enables Flux users to consume chart |
| **3. Template repo** | `floe-gitops-template` with multi-env, SOPS | 2-3 days | DX for GitOps users |
| **4. CLI integration** | `floe compile --output-format=configmap` | 1 day | Bridges imperative → GitOps |
| **5. Docs + examples** | Update `charts/examples/flux/` (v2beta2 → v2), secrets guide | 1 day | Competitive differentiator |

### Key Design Decisions (for `/sw-design`)

1. **Values pattern**: Hybrid (inline toggles + ConfigMap compiled values)
2. **Secrets**: SOPS (Age) default, ESO documented as enterprise option
3. **Distribution**: Template repo (not CLI subcommand)
4. **Chart registry**: GHCR with Cosign keyless signing
5. **Test isolation**: Flux for dev steady-state, ephemeral namespaces for CI
6. **Progressive adoption**: Imperative → GitOps-aware → Full GitOps

---

**⚠️ Research directory at 13 briefs (cap 10). Suggest cleanup of oldest briefs:**
- `alpha-remaining-bugs-20260328.md` (18 days old)
- `dagster-materialization-failure-20260328.md` (18 days old)
- `helm-v4-upgrade-20260328.md` (18 days old)
- `tunnel-stability-20260329.md` (17 days old)
