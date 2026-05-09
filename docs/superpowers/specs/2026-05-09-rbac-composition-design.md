# RBAC Composition Design

Date: 2026-05-09
Status: Draft for review

## Goal

Map identity and plugin requirements into generated Kubernetes access policy.

RBAC should become a composition output: selected identity bindings and
plugin-declared access requirements should produce Kubernetes ServiceAccounts,
Roles, RoleBindings, and Namespaces without exposing concrete plugin
implementation details.

## Current Trigger

The Kubernetes RBAC plugin is discoverable and generation tests exist, but it
does not consume typed identity or plugin requirement bindings.

The current code proves the trigger is real:

```bash
rg -n "class RBACPlugin|ServiceAccount|RoleBinding|RequirementSet|identity_modes|PluginType.RBAC|floe.rbac" \
  packages/floe-core/src/floe_core \
  plugins/floe-rbac-k8s \
  packages/floe-core/tests/unit/test_rbac_*.py \
  packages/floe-core/tests/integration/test_rbac_generation.py \
  tests/contract/test_composition_capability_contract.py \
  packages/floe-core/tests/unit/composition/test_resolver.py
```

Evidence from that search:

- `PluginType.RBAC` maps to the `floe.rbac` entry point, and
  `plugins/floe-rbac-k8s/pyproject.toml` registers the Kubernetes RBAC plugin.
- `RBACPlugin` defines generation methods for ServiceAccounts, Roles,
  RoleBindings, Namespaces, and pod security context.
- `K8sRBACPlugin` delegates to typed RBAC schema models such as
  `ServiceAccountConfig`, `RoleConfig`, and `RoleBindingConfig`.
- `RBACManifestGenerator.generate()` currently receives `SecurityConfig`,
  `secret_references`, and optional explicit RBAC configs. It does not receive
  identity deployment bindings or plugin requirement models.
- `CapabilitySet` and `RequirementSet` already type `credential_modes`,
  `secret_projection_modes`, `identity_modes`, providers, catalog providers,
  table formats, and related compatibility flags.
- `CompositionResolver._validate_identity()` already validates required
  workload identity modes against selected identity capabilities.
- RBAC tests already cover ServiceAccount and RoleBinding schema/generation
  behavior, including least-privilege defaults such as
  `automountServiceAccountToken=False`.

## Target Contract

RBAC generation consumes identity bindings and plugin requirements, then emits
Kubernetes access policy without direct knowledge of concrete plugin
implementation details.

The target public shape is:

- Composition emits typed identity and credential-provider projections before
  RBAC generation.
- Plugins declare access requirements as requirement models, not arbitrary
  Kubernetes YAML.
- `floe-core` translates selected identity bindings plus plugin requirements
  into a provider-neutral access-policy input.
- `floe-rbac-k8s` translates that input into Kubernetes ServiceAccounts,
  Roles, RoleBindings, and Namespaces.
- RBAC generation may include provider-owned annotations emitted by identity
  projections, but must not inspect concrete identity plugin config.

The preferred additive model is:

```python
class WorkloadAccessRequirement(BaseModel):
    workload_ref: str
    namespace: str
    service_account_name: str
    required_identity_modes: list[str] = Field(default_factory=list)
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)
    rules: list[AccessRuleRequirement] = Field(default_factory=list)


class AccessRuleRequirement(BaseModel):
    api_groups: list[str] = Field(default_factory=list)
    resources: list[str]
    verbs: list[str]
    resource_names: list[str] = Field(default_factory=list)
```

The exact names can change during implementation. The ownership should not:
composition validates the selected requirements and bindings; the RBAC plugin
renders Kubernetes resources from typed access-policy inputs.

## Composition Constraints

- Capabilities, requirements, typed bindings, and resolver validation own
  cross-plugin contracts.
- RBAC plugins must not import concrete identity, secrets, storage, catalog, or
  orchestrator implementations.
- `CompiledArtifacts` remains secret-free; generated policies may reference
  secret names and service accounts but must not embed secret values.
- Renderers consume resolved deployment bindings and access-policy inputs.
- Kubernetes RBAC is the first implementation proof, not the only possible
  access-policy backend.

## Level Target

Current level: Level 0. The plugin and generator exist, but they render from
manual security/RBAC inputs rather than composition-owned identity and plugin
requirements.

Target level: Level 2. RBAC generation consumes typed identity bindings and
plugin requirement inputs. Level 3 follows when resolver tests prove incompatible
identity modes or missing provider capabilities fail before manifests render.

## Compatibility Retirement

Current generator inputs such as explicit `service_accounts`, `roles`, and
`role_bindings` should remain as manual override and compatibility surfaces.
They should not remain the only first-party path for generated policy.

Retirement rule:

- Add binding-derived access-policy input first.
- Keep explicit RBAC configs for platform overrides and migration.
- Make composition-derived inputs the canonical product path.
- Add guard tests that fail if generated first-party policy depends on raw
  plugin config or embeds raw secrets.

## Acceptance Evidence

- Resolver tests cover required identity modes.
- RBAC generation tests cover generated service accounts, roles, and bindings
  from typed inputs.
- No generated policy embeds raw secrets.
- Schema tests cover access requirement and workload identity binding inputs.
- Compatibility tests prove RBAC generation does not import concrete identity
  or secrets plugin implementations.

## Non-Goals

- Do not replace Kubernetes RBAC schema models.
- Do not grant wildcard permissions to make composition easier.
- Do not make identity plugins generate Kubernetes RBAC manifests directly.
- Do not remove manual RBAC override inputs before the binding-derived path is
  proven.
