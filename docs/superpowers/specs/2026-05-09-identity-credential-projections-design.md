# Identity And Credential Projection Design

Date: 2026-05-09
Status: Draft for review

## Goal

Extend composition from capability validation to typed, secret-free identity and
credential deployment projections.

The target contract keeps Floe's post-composition ownership model intact:
capabilities, requirements, and resolver validation own cross-plugin contracts;
plugins do not know another plugin's implementation details; and
`CompiledArtifacts` remains secret-free.

## Current Surfaces

The live identity and credential surface already has the right building blocks,
but it stops at validation and storage-specific credential references.

- Identity plugins are first-class plugin categories under the `floe.identity`
  entry point. `docs/architecture/interfaces/identity-plugin.md` documents
  `get_identity_capabilities(self) -> PluginCapabilities`, and
  `PluginType.IDENTITY` maps to `floe.identity` in
  `packages/floe-core/src/floe_core/plugin_types.py`.
- Secrets plugins are first-class plugin categories under the `floe.secrets`
  entry point. `docs/architecture/interfaces/secrets-plugin.md` documents
  `get_secret_capabilities(self) -> PluginCapabilities`, and
  `PluginType.SECRETS` maps to `floe.secrets`.
- The concrete `KeycloakIdentityPlugin` returns identity composition facts:
  `credential_modes=["workload-identity"]`,
  `identity_modes=["oidc-federation"]`, and `providers=["oidc"]`.
- The concrete Kubernetes secrets plugin returns
  `credential_modes=["kubernetes-secret"]`,
  `secret_projection_modes=["kubernetes-secret"]`, and
  `providers=["kubernetes"]`.
- The concrete Infisical secrets plugin returns
  `credential_modes=["external-secret-sync", "kubernetes-secret"]`,
  `secret_projection_modes=["external-secret-sync", "kubernetes-secret"]`,
  and `providers=["infisical", "kubernetes"]`.
- `CapabilitySet` and `RequirementSet` in
  `packages/floe-core/src/floe_core/composition/models.py` already type
  `credential_modes`, `secret_projection_modes`, `identity_modes`, and
  provider labels. The current `IdentityMode` vocabulary includes AWS IRSA,
  EKS Pod Identity, GCP Workload Identity, Azure Workload Identity, Azure
  Managed Identity, and generic OIDC federation.
- `_build_storage_deployment_binding()` in
  `packages/floe-core/src/floe_core/compilation/stages.py` resolves selected
  secrets and identity plugins, verifies their ABCs, and appends
  `get_secret_capabilities()` / `get_identity_capabilities()` output to the
  resolver input.
- `CompositionResolver` validates storage/catalog credential-mode
  compatibility, secret projection compatibility, identity-provider presence,
  identity modes, and identity provider labels. These checks already use
  `COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED`,
  `COMPOSITION_SECRET_PROJECTION_UNSUPPORTED`,
  `COMPOSITION_SECRET_PROVIDER_MISSING`,
  `COMPOSITION_SECRET_PROVIDER_UNSUPPORTED`,
  `COMPOSITION_IDENTITY_PROVIDER_MISSING`,
  `COMPOSITION_IDENTITY_MODE_UNSUPPORTED`, and
  `COMPOSITION_IDENTITY_PROVIDER_UNSUPPORTED`.
- `CredentialRef` in
  `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` is the
  canonical secret-free credential reference. It carries `source`, `name`, and
  optional `key`, and its validator only permits `key` for secret-backed
  sources.
- `StorageCredentialBinding.as_credential_ref()` converts storage-owned
  credential bindings to `CredentialRef` instances for Kubernetes Secret,
  external-secret-sync, CSI secret volume, environment, workload identity, or
  none.
- Existing compiled artifact validators reject raw credential-looking fields in
  runtime fragments and instruct callers to use `env_refs` or `CredentialRef`
  fields instead.
- `PolarisCatalogDeploymentBinding.credential_refs` already proves the desired
  reference-only shape for catalog consumers, but the projection is attached to
  the storage/catalog binding rather than a broader identity or credential
  provider projection.

The gap is therefore not discovery or vocabulary. The missing contract is a
typed deployment projection that records which identity and credential-provider
facts were selected and validated, without embedding any raw token, password,
client secret, or provider-owned secret value.

## Proposed Projections

Add two secret-free projection families under the compiled deployment contract.
The exact field names can be finalized during implementation, but the contract
should be explicit enough for deployment, RBAC, network, catalog, compute, and
runtime translators to consume without rediscovering plugin config.

### Identity projection

The identity projection describes workload identity facts selected by
composition:

```python
ProviderSelectionRef = Annotated[
    str,
    Field(pattern=r"^(identity|secrets):[a-z0-9][a-z0-9_-]*$"),
]


class IdentityDeploymentProjection(BaseModel):
    provider_ref: ProviderSelectionRef
    provider: str
    issuer: str
    audience: str
    workload_identity_mode: IdentityMode
    token_audience: str | None = None
    token_audience_metadata: dict[str, str] = Field(default_factory=dict)
    credential_mode: Literal["workload-identity"] = "workload-identity"
```

Required semantics:

- `provider_ref` points at the selected identity plugin, such as
  `identity:keycloak`; it uses the same category-qualified string shape as
  `PluginCapabilities.ref` and is not `PluginRef` because projection consumers
  must not receive provider config.
- `issuer` and `audience` are non-secret identity metadata, for example OIDC
  issuer URL and expected token audience. They must come from an identity-owned
  projection source, not from resolver inspection of plugin config.
- `workload_identity_mode` must be one of the resolver-supported identity
  modes.
- `token_audience` and `token_audience_metadata` carry non-secret hints needed
  by runtime consumers or policy renderers.
- Provider-specific resources, such as IAM role ARNs, GCP service account
  emails, Azure client IDs, Keycloak realm internals, Vault roles, or
  controller CRDs, remain provider-owned fields on provider-owned bindings or
  future provider renderers.

### Credential projection

The credential projection describes how credential material will be looked up at
runtime without carrying the material itself:

```python
class CredentialProviderProjection(BaseModel):
    provider_ref: ProviderSelectionRef
    provider: str
    supported_credential_modes: list[CredentialMode]
    supported_secret_projection_modes: list[SecretProjectionMode] = Field(default_factory=list)
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)
```

Required semantics:

- `provider_ref` points at the selected secrets or identity plugin, such as
  `secrets:k8s`, `secrets:infisical`, or `identity:keycloak`. It is a
  category-qualified, config-free reference, not `PluginRef`.
- `supported_credential_modes` records the validated credential modes for that
  provider selection.
- `supported_secret_projection_modes` records secret projection modes for
  secrets-backed providers only.
- `credential_refs` is the only place the projection names runtime lookup
  handles. Each `CredentialRef` keeps the current `source`, `name`, and
  optional `key` shape.
- Workload identity uses `CredentialRef(source="workload-identity", name=...)`
  for the service account or provider-owned runtime identity reference.
- Kubernetes Secret, external-secret-sync, and CSI secret volume modes use
  `CredentialRef` with `key`; environment and workload-identity modes do not.

### Projection source

Capability and requirement models remain the validation contract. They are not
expanded into arbitrary provider configuration bags. Projection emission should
derive facts from these explicit sources only:

- selected `PluginCapabilities.ref` values, which become
  category-qualified `provider_ref` strings;
- selected capabilities and requirements, which supply mode and provider-label
  vocabulary already validated by `CompositionResolver`;
- existing typed deployment bindings, such as storage and catalog credential
  bindings, when they already expose `CredentialRef` handles; and
- provider-owned, non-secret projection metadata emitted by the selected
  identity or secrets plugin.

For the first Keycloak identity implementation, the identity plugin can satisfy
the provider-owned metadata source by using its own `get_oidc_config()` result
for `issuer` and an explicit non-secret audience/client identifier owned by the
identity plugin configuration. The compiler may call a narrow identity-owned
projection method or adapter for those fields, but it must not reach into
`KeycloakIdentityConfig`, infer realm internals, or couple generic composition
code to Keycloak implementation details.

If an identity plugin advertises an identity mode that requires issuer or
audience metadata but cannot emit those non-secret fields, projection emission
must fail before `CompiledArtifacts` are produced.

## Secret Handling

`CompiledArtifacts` carry references only.

Raw tokens, passwords, client secrets, private keys, provider API tokens,
Infisical Universal Auth client secrets, Keycloak confidential client secrets,
Kubernetes Secret values, Vault values, cloud secret-manager payloads, and any
provider secret values remain outside `CompiledArtifacts`.

Allowed values:

- plugin references and provider labels;
- non-secret issuer, audience, endpoint, mode, and token-audience metadata;
- `CredentialRef` source/name/key lookup handles;
- environment variable names;
- Kubernetes Secret names and keys;
- service account or provider-owned identity names.

Disallowed values:

- decoded secret data;
- bearer/access/refresh tokens;
- passwords and client secrets;
- cloud access keys or secret keys;
- opaque provider credentials;
- inline auth headers;
- credential-bearing URLs.

Schema validators should reuse the existing secret-free compiled artifact
pattern: reject credential-looking key names or values in generic runtime
fragments, and prefer explicit `CredentialRef` fields for credential lookup
handles.

## Resolver Validation

Resolver validation should fail before projections are emitted when selected
plugins require identity or credential modes that configured providers cannot
satisfy.

Required validation behavior:

- If a storage or catalog requirement selects `workload-identity`, an identity
  plugin must be selected unless a validated non-identity credential mode also
  satisfies the requirement.
- The selected identity plugin's `identity_modes` must intersect the required
  identity modes.
- The selected identity plugin's providers must satisfy provider labels required
  by consumers.
- If a storage or catalog requirement selects Kubernetes Secret,
  external-secret-sync, CSI secret volume, or environment-based projection, a
  secrets plugin must satisfy the required secret projection mode unless the
  mode is an intentionally supported Kubernetes/environment baseline.
- Secret projection providers must satisfy consumer provider labels.
- The selected storage credential mode must remain included in
  `StorageCapabilities.credential_modes`.
- Unsupported identity or credential vocabulary values must fail as contract
  errors, not be silently dropped.

Projection emission should consume the already-validated compatibility result.
Renderers should not repeat plugin compatibility checks or rediscover provider
config.

## Composability Constraints

- Cross-plugin contracts live in typed capabilities, requirements, resolver
  validation, and compiled deployment projections.
- A storage plugin can declare that it supports workload identity or secret
  projection modes, but it must not know Keycloak, Infisical, Vault, Polaris,
  Dagster, or dbt implementation details.
- A secrets plugin can declare projection modes and provider labels, but it
  must not decide catalog, compute, or storage compatibility by inspecting
  those plugins.
- An identity plugin can declare supported workload identity modes and provider
  labels, but it must not render storage or catalog configuration directly.
- `CompiledArtifacts` must remain the handoff contract for deployment and
  runtime consumers, and that contract must be reference-only for credentials.
- Provider-specific translation belongs to provider-owned renderers or typed
  provider-owned deployment bindings, not to generic resolver branches.

## Acceptance Evidence

Implementation should include focused evidence before the projection contract is
considered complete:

- Schema tests cover `IdentityDeploymentProjection`,
  `CredentialProviderProjection`, and `CredentialRef` validation, including
  workload identity, Kubernetes Secret, external-secret-sync, CSI secret volume,
  environment, and none modes.
- Contract tests prove compiled projections contain references only and reject
  raw tokens, passwords, client secrets, cloud access keys, provider API tokens,
  and credential-bearing URLs.
- Resolver tests cover compatible and incompatible credential modes across
  storage, catalog, secrets, and identity providers.
- Resolver tests cover compatible and incompatible identity modes, missing
  identity plugins, unsupported identity provider labels, and invalid identity
  vocabulary.
- Existing storage binding tests continue proving MinIO plus Polaris emits
  secret-free credential references.
- Helm/rendering tests prove renderers consume compiled projections and do not
  rediscover plugin config.
- Docs navigation and content validators pass after public docs are updated.

Suggested focused checks for the implementation phase:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py -q
uv run pytest packages/floe-core/tests/unit/composition/test_resolver.py -q
uv run pytest tests/contract -q
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
```
