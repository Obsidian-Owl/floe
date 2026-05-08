# Identity And Secret Composition Design

Status: Approved for planning
Date: 2026-05-07
Author: Codex

## Summary

Floe should implement PCU-005 by making credential delivery a typed
composition contract instead of an implicit string convention. The immediate
goal is to connect current storage and catalog credential bindings to selected
secrets and identity plugins, while preserving the working MinIO plus Polaris
Kubernetes Secret path.

The design extends the storage composition model rather than creating a
separate security subsystem:

```text
selected plugins
  -> plugin capabilities and requirements
  -> composition resolver
  -> secret-free deployment bindings
  -> Helm, RBAC, network, and runtime renderers
```

Credential composition has two distinct concerns:

- Secret projection: how sensitive material reaches Kubernetes or runtime
  consumers.
- Workload identity: how a pod, service, catalog, or compute engine gets
  authority without static credentials.

Keeping these concerns separate lets Floe support Kubernetes Secrets, external
secret managers, CSI-mounted secrets, AWS IRSA, EKS Pod Identity, GKE Workload
Identity, Azure Workload ID, managed identities, OIDC federation, and future
data-platform identity models without forcing every provider into one generic
credential mode.

## Research Validation

The approved contract was checked against common customer data-platform
patterns and official provider behavior:

- Kubernetes Secrets remain the common baseline for Kubernetes-native
  deployments. They can be created independently of consuming pods and consumed
  by reference, which matches Floe's secret-free artifact rule.
  Source: https://kubernetes.io/docs/concepts/configuration/secret/
- AWS customers commonly use both secret projection and identity federation.
  Amazon EKS supports IRSA and EKS Pod Identity, both mapping IAM authority to
  Kubernetes service accounts rather than distributing long-lived credentials.
  External Secrets Operator also supports AWS Secrets Manager and SSM Parameter
  Store with service-account-token based authentication.
  Sources:
  https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html,
  https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html,
  https://external-secrets.io/latest/provider/aws-access/
- GKE Workload Identity Federation is the recommended GKE mechanism for
  Kubernetes workloads accessing Google Cloud APIs without static service
  account key files. External Secrets Operator supports Google Secret Manager
  through Workload Identity Federation.
  Sources:
  https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity,
  https://external-secrets.io/v0.20.3/provider/google-secrets-manager/
- AKS commonly uses Microsoft Entra Workload ID or managed identity. Azure Key
  Vault can be projected through the Secrets Store CSI Driver, and the CSI
  driver can also sync mounted objects into Kubernetes Secrets.
  Sources:
  https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview,
  https://learn.microsoft.com/en-us/azure/aks/csi-secrets-store-driver,
  https://learn.microsoft.com/en-us/azure/aks/csi-secrets-store-identity-access
- Vault and Infisical validate the provider-owned translation boundary. Vault
  supports Kubernetes and JWT/OIDC authentication modes. Infisical's Kubernetes
  operator syncs external secrets into managed Kubernetes Secret resources
  through CRDs.
  Sources:
  https://developer.hashicorp.com/vault/docs/auth/kubernetes,
  https://docs.hashicorp.com/vault/docs/auth/jwt,
  https://infisical.com/docs/integrations/platforms/kubernetes/infisical-secret-crd
- Databricks and Snowflake validate identity as a data-platform concern, not
  only a Kubernetes concern. Unity Catalog uses storage credentials and
  external locations backed by cloud identity mechanisms, while Snowflake
  supports workload identity federation to avoid long-lived passwords, API
  keys, key pairs, or access tokens for service-to-service authentication.
  Sources:
  https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/s3/s3-external-location-manual,
  https://learn.microsoft.com/en-us/azure/databricks/connect/unity-catalog/cloud-storage/storage-credentials,
  https://docs.snowflake.com/en/en/user-guide/workload-identity-federation

## Current Problem

The storage composition closeout introduced useful building blocks:

- `StorageCredentialBinding` is secret-free.
- `CredentialRef` lets catalog and Helm projections reference credential
  identity without raw values.
- `StorageCapabilities.credential_modes` describes the current storage-side
  credential mode.
- `CompositionResolver` already rejects incompatible storage and catalog
  protocol or credential-mode combinations.
- `floe helm generate` renders MinIO and Polaris values from deployment
  bindings, not from plugin config.

The remaining PCU-005 gap is that credential modes are still self-contained
strings on storage/catalog. There is no selected secrets or identity provider
that can validate whether a mode is actually supported in the customer
platform.

Examples:

- `kubernetes-secret` currently works, but the resolver does not know whether
  the platform chose native Kubernetes Secrets, Infisical sync, Vault sync, or
  an implicit Kubernetes baseline.
- `workload-identity` can appear as a generic mode, but AWS IRSA, EKS Pod
  Identity, GKE Workload Identity, Azure Workload ID, and generic OIDC
  federation have different provider constraints.
- External secret and CSI-volume modes are not representable as first-class
  capabilities, so future chart/RBAC/network work would have to infer behavior
  from provider-specific config.
- `CompiledArtifacts.plugins` currently omits `secrets` and `identity`, even
  though both are first-class platform manifest plugin categories.

## Goals

- Add `secrets` and `identity` to `ResolvedPlugins` so compiled artifacts show
  the selected providers without rereading the platform manifest.
- Keep `CompiledArtifacts` secret-free: no raw credentials in artifacts,
  generated chart values, logs, or tests.
- Separate secret projection modes from workload identity modes.
- Preserve the current MinIO plus Polaris Kubernetes Secret path.
- Make unsupported credential combinations fail in the resolver with
  actionable composition issues.
- Keep provider-specific translation in provider plugins, not in Helm or the
  generic resolver.
- Give future RBAC, network policy, and deployment renderers a typed surface
  they can consume.
- Update architecture docs when public contracts change.

## Non-Goals

- Do not implement native AWS S3, GCS, Azure Blob, Glue, Databricks, or
  Snowflake providers in this branch.
- Do not add `deployment.secrets` or `deployment.identity` renderer bindings
  yet. Those belong with RBAC, network, and deployment rendering follow-up.
- Do not make external secret managers retrieve secret values during compile.
- Do not make Helm rediscover plugin config.
- Do not require explicit `secrets:k8s` for the existing MinIO plus Polaris
  Kubernetes Secret path.
- Do not turn local `environment` credentials into a production default.

## Architecture Decision

Use typed provider capability surfaces plus generic credential requirements.

### Resolved Plugin Contract

Extend `ResolvedPlugins` with two optional fields:

```python
class ResolvedPlugins(BaseModel):
    compute: PluginRef
    orchestrator: PluginRef
    catalog: PluginRef | None = None
    storage: PluginRef | None = None
    ingestion: PluginRef | None = None
    semantic: PluginRef | None = None
    lineage_backend: PluginRef | None = None
    secrets: PluginRef | None = None
    identity: PluginRef | None = None
```

The compiler already resolves manifest plugin selections through
`resolve_plugins()`. That function should pass through `manifest.plugins.secrets`
and `manifest.plugins.identity` the same way it passes through storage,
catalog, and lineage backend selections.

### Composition Vocabulary

Extend composition models with typed capability and requirement fields that are
specific enough for validation but neutral enough for providers:

```python
SecretProjectionMode = Literal[
    "kubernetes-secret",
    "external-secret-sync",
    "csi-secret-volume",
    "environment",
]

IdentityMode = Literal[
    "aws-irsa",
    "aws-pod-identity",
    "gcp-workload-identity",
    "azure-workload-identity",
    "azure-managed-identity",
    "oidc-federation",
]

CredentialMode = Literal[
    "kubernetes-secret",
    "external-secret-sync",
    "csi-secret-volume",
    "environment",
    "workload-identity",
    "none",
]
```

`credential_modes` remains for backward compatibility and for storage/catalog
matching. New fields disambiguate how a credential mode is realized:

```python
class CapabilitySet(BaseModel):
    protocols: list[str] = Field(default_factory=list)
    credential_modes: list[str] = Field(default_factory=list)
    secret_projection_modes: list[str] = Field(default_factory=list)
    identity_modes: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    path_style_access: bool | None = None
    sts: bool | None = None


class RequirementSet(BaseModel):
    protocols: list[str] = Field(default_factory=list)
    credential_modes: list[str] = Field(default_factory=list)
    secret_projection_modes: list[str] = Field(default_factory=list)
    identity_modes: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    requires_server_side_storage_access: bool | None = None
    supports_no_sts: bool | None = None
    supports_path_style_access: bool | None = None
```

Provider labels are coarse compatibility scopes such as `kubernetes`, `aws`,
`gcp`, `azure`, `vault`, and `infisical`. Provider-specific fields such as IAM
role ARN, GCP service account email, Azure client ID, Vault role, or Infisical
identity ID remain in provider-owned config or future provider-owned deployment
bindings.

### Secrets Plugin Capabilities

`SecretsPlugin` should expose a side-effect-free capability method:

```python
def get_secret_capabilities(self) -> PluginCapabilities:
    """Return secret projection capabilities for composition validation."""
```

Reference behavior:

- `floe-secrets-k8s` supports provider `kubernetes` and projection mode
  `kubernetes-secret`.
- `floe-secrets-infisical` supports provider `infisical` and projection mode
  `external-secret-sync`; if it renders managed Kubernetes Secrets, it may also
  support `kubernetes-secret` as a projection output.
- Future Vault or ESO plugins can declare `external-secret-sync`,
  `csi-secret-volume`, or both.

The default base method may return no capabilities to preserve compatibility
for plugins that have not adopted composition yet.

### Identity Plugin Capabilities

`IdentityPlugin` should expose a side-effect-free capability method:

```python
def get_identity_capabilities(self) -> PluginCapabilities:
    """Return workload identity capabilities for composition validation."""
```

Reference behavior:

- `floe-identity-keycloak` supports provider `oidc` and identity mode
  `oidc-federation` if it can supply OIDC issuer/JWKS information without raw
  client secret material.
- Future AWS, GCP, or Azure identity plugins declare cloud-native identity
  modes such as `aws-irsa`, `aws-pod-identity`, `gcp-workload-identity`,
  `azure-workload-identity`, or `azure-managed-identity`.

Identity plugins should validate and translate their own provider-specific
details. Core should not know IAM trust policy shape, GCP annotation names, or
Azure federated credential fields beyond the typed mode vocabulary.

### Resolver Rules

The resolver should validate the selected graph in these steps:

1. Continue validating storage protocols and storage/catalog credential mode
   compatibility.
2. If a selected storage or catalog binding uses `kubernetes-secret`, accept it
   when either:
   - no explicit secrets plugin is selected, using the implicit Kubernetes
     baseline; or
   - a selected secrets plugin declares `kubernetes-secret`.
3. If a selected requirement uses `external-secret-sync`, require a selected
   secrets plugin with `external-secret-sync`.
4. If a selected requirement uses `csi-secret-volume`, require a selected
   secrets plugin with `csi-secret-volume` and leave renderer support as a
   later deployment precondition.
5. If a selected requirement uses `environment`, allow it only for local/dev
   requirements. Do not let it become a production deployment default.
6. If a selected requirement uses generic `workload-identity`, require an
   explicit identity mode or a selected identity plugin that can satisfy the
   requested provider.
7. If a requirement names a specific identity mode, require a selected identity
   plugin that declares that mode.

New public issue codes should be actionable and distinct:

- `COMPOSITION_SECRET_PROVIDER_MISSING`
- `COMPOSITION_SECRET_PROJECTION_UNSUPPORTED`
- `COMPOSITION_IDENTITY_PROVIDER_MISSING`
- `COMPOSITION_IDENTITY_MODE_UNSUPPORTED`

The existing `COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED` remains for direct
storage/catalog credential-mode mismatches.

### Compile-Time Integration

The compiler should build capability inputs from resolved providers:

- Storage capability comes from `StorageDeploymentBinding.capabilities`.
- Catalog requirements come from `CatalogPlugin.get_storage_requirements()`.
- Secrets capability comes from `SecretsPlugin.get_secret_capabilities()`, when
  selected.
- Identity capability comes from `IdentityPlugin.get_identity_capabilities()`,
  when selected.

The current implicit Kubernetes baseline should be modeled as a resolver
default, not as a hidden plugin in `CompiledArtifacts.plugins`.

Compilation remains side-effect free. Plugins should not read secret values,
create Kubernetes resources, call cloud APIs, or mutate external identity
systems during this validation.

## Data Flow

```text
manifest.plugins
  -> resolve_plugins()
  -> ResolvedPlugins(secrets=?, identity=?)
  -> storage deployment binding
  -> catalog storage requirements
  -> optional secrets capabilities
  -> optional identity capabilities
  -> CompositionResolver.validate()
  -> DeploymentConfig(storage=?, catalog=?)
  -> renderers consume secret-free refs and mode hints
```

The output remains secret-free. Raw values can exist only in external systems,
Kubernetes Secret resources, runtime environment variables, or provider SDK
calls outside compiled artifacts.

## Compatibility Matrix

| Customer path | Secret projection | Workload identity | Expected result |
| --- | --- | --- | --- |
| MinIO + Polaris on Kind | `kubernetes-secret` | none | Valid with implicit Kubernetes baseline |
| MinIO + Polaris + explicit K8s secrets plugin | `kubernetes-secret` | none | Valid when `secrets:k8s` declares the mode |
| AWS S3 + Glue on EKS with IRSA | none or external sync | `aws-irsa` | Valid only with AWS identity capability |
| AWS S3 + Glue on EKS Pod Identity | none or external sync | `aws-pod-identity` | Valid only with AWS identity capability |
| GCS on GKE | none or external sync | `gcp-workload-identity` | Valid only with GCP identity capability |
| ADLS or Key Vault on AKS | `csi-secret-volume` or external sync | `azure-workload-identity` or `azure-managed-identity` | Valid only with Azure-capable providers |
| Vault-backed Kubernetes workloads | `external-secret-sync` or `csi-secret-volume` | `oidc-federation` or Kubernetes auth | Valid only with Vault/identity capabilities |
| Infisical operator | `external-secret-sync` to Kubernetes Secret | optional Kubernetes auth | Valid with Infisical secrets capability |
| Snowflake WIF compute path | none | `oidc-federation` or cloud-native identity | Future compute requirement, validated by identity capability |

## Testing Strategy

Add focused tests before or alongside implementation:

- `ResolvedPlugins` schema tests proving `secrets` and `identity` are accepted
  and serialized as `PluginRef` values without secret material.
- Resolver tests for:
  - current MinIO plus Polaris Kubernetes Secret path remaining valid with no
    explicit secrets plugin;
  - explicit `secrets:k8s` satisfying `kubernetes-secret`;
  - `external-secret-sync` failing without a secrets plugin;
  - unsupported projection mode failing with
    `COMPOSITION_SECRET_PROJECTION_UNSUPPORTED`;
  - `workload-identity` failing without an identity plugin;
  - unsupported specific identity mode failing with
    `COMPOSITION_IDENTITY_MODE_UNSUPPORTED`.
- Reference plugin tests for K8s Secrets, Infisical, and Keycloak capability
  declarations.
- Contract/security tests proving compiled artifacts and generated Helm values
  contain refs and mode names, not raw credential values.
- Compilation tests proving selected `secrets` and `identity` plugin refs flow
  from manifest to compiled artifacts.

## Documentation Updates

Update:

- `docs/architecture/plugin-composition-uplift-tracker.md` to move PCU-005
  from planned to implemented or in progress, depending on final branch state.
- `docs/architecture/interfaces/secrets-plugin.md` with the capability method
  and projection vocabulary.
- `docs/architecture/interfaces/identity-plugin.md` with the capability method
  and identity-mode vocabulary.
- `docs/architecture/interfaces/storage-plugin.md` and
  `docs/architecture/interfaces/catalog-plugin.md` where credential
  requirements reference the new vocabulary.

Do not document provider-specific configuration fields as core fields unless
they are implemented in this branch.

## Risks And Mitigations

- Risk: one generic `workload-identity` mode hides incompatible cloud
  semantics.
  Mitigation: keep generic `credential_modes` for backward compatibility but
  require provider-specific `identity_modes` for real validation.
- Risk: adding explicit secrets and identity providers breaks the current demo.
  Mitigation: preserve implicit Kubernetes baseline for `kubernetes-secret`.
- Risk: provider plugins leak raw secret material through capabilities.
  Mitigation: capabilities contain only modes, providers, references, and
  public endpoint metadata. Tests reject raw credential-looking values.
- Risk: core becomes a cloud-provider rule engine.
  Mitigation: core validates named modes and provider labels only; plugins own
  provider-specific translation.
- Risk: renderers need more information than this branch emits.
  Mitigation: defer `deployment.secrets` and `deployment.identity` bindings to
  RBAC/network/deployment follow-up after this validation contract lands.

## Acceptance Criteria

- `CompiledArtifacts.plugins` includes selected `secrets` and `identity`
  plugin refs when configured.
- Current MinIO plus Polaris Kubernetes Secret composition remains valid.
- External secret and workload identity modes are resolver-validated, not
  convention-driven.
- Unsupported credential, projection, or identity modes fail with actionable
  composition issues.
- Reference K8s, Infisical, and Keycloak plugins declare side-effect-free
  capabilities.
- Compiled artifacts and generated Helm values remain free of raw secret
  material.
- Architecture docs describe the adopted identity/secrets composition contract.
