# Network Security Composition Design

Date: 2026-05-09
Status: Draft for review

## Goal

Define typed endpoint and identity inputs for Kubernetes network policy
generation.

Network security should become a composition output: selected services,
workloads, endpoints, namespaces, and identity bindings should produce
NetworkPolicy manifests without the network plugin hardcoding Floe service
topology or reading concrete plugin config.

## Current Trigger

The Kubernetes network security plugin is discoverable, but it does not consume
typed endpoint or identity bindings.

The current code proves the trigger is real:

```bash
rg -n "class NetworkSecurityPlugin|NetworkPolicy|floe.network_security|generate_network_policy|default-deny|from_namespace|to_namespace|pod_selector" \
  packages/floe-core/src/floe_core \
  plugins/floe-network-security-k8s \
  packages/floe-core/tests/unit/test_network_generator.py \
  packages/floe-core/tests/unit/network_security
```

Evidence from that search:

- `NetworkSecurityPlugin` is the plugin ABC for `floe.network_security` and
  defines `generate_network_policy()`, default-deny generation, DNS egress,
  pod security context, container security context, and writable volume hooks.
- `plugins/floe-network-security-k8s/pyproject.toml` registers the Kubernetes
  implementation under the `floe.network_security` entry point.
- `K8sNetworkSecurityPlugin.generate_network_policy()` converts typed
  `NetworkPolicyConfig` into Kubernetes `NetworkPolicy` YAML with
  `podSelector`, `Ingress`, and `Egress` policy types.
- `NetworkPolicyManifestGenerator.generate(namespaces)` currently loops over
  namespace strings, generates default-deny policies, and appends DNS egress.
  It does not consume endpoint bindings or identity bindings.
- Current network tests prove default-deny policies, static platform egress
  rules, ingress-controller rules, jobs-to-platform rules, namespace selectors,
  and service ports such as Polaris `8181`, OTel `4317/4318`, and MinIO `9000`.
- Network schema tests already cover namespace/pod selector inputs and egress
  rule validation, but not composition-derived endpoint or identity models.

## Target Contract

Network policy generation consumes endpoint and identity bindings emitted by
composition, not concrete plugin config.

The target public shape is:

- Composition emits typed endpoint bindings for platform services, data
  workloads, control-plane services, and external dependencies.
- Identity projections identify workload identity/service-account names and
  namespace ownership without carrying secrets.
- The network generator consumes typed flow requirements such as
  workload-to-service, service-to-service, DNS, ingress-controller, and external
  CIDR access.
- `floe-network-security-k8s` translates typed flow requirements into
  Kubernetes `NetworkPolicy` manifests.
- The network plugin does not import compute, catalog, storage, semantic,
  orchestrator, identity, or secrets implementations.

The preferred additive model is:

```python
class NetworkEndpointBinding(BaseModel):
    ref: str
    namespace: str
    pod_selector: dict[str, str] = Field(default_factory=dict)
    service_name: str | None = None
    ports: list[NetworkPortBinding] = Field(default_factory=list)
    identity_ref: str | None = None


class NetworkFlowRequirement(BaseModel):
    from_ref: str
    to_ref: str
    ports: list[NetworkPortBinding] = Field(default_factory=list)
    direction: Literal["ingress", "egress", "bidirectional"] = "egress"
```

The exact names can change during implementation. The ownership should not:
composition owns endpoint and identity bindings; Kubernetes network security
plugins render policy from typed flow inputs.

## Composition Constraints

- Capabilities, requirements, typed bindings, and resolver validation own
  cross-plugin contracts.
- Network security plugins must not import or inspect concrete plugin
  implementations.
- `CompiledArtifacts` remains secret-free; endpoint and identity bindings carry
  labels, namespaces, ports, service names, and service account references only.
- Renderers consume resolved deployment bindings.
- Hardcoded Floe service topology should move behind generated endpoint
  bindings or documented platform defaults.

## Level Target

Current level: Level 0. The plugin and generator exist, but generated policy is
namespace/topology driven rather than composition driven.

Target level: Level 2. Network policy generation consumes typed endpoint and
identity bindings. Level 3 follows when resolver tests validate required flows
and missing endpoints before manifests render.

## Compatibility Retirement

Current namespace-only generation should remain as a compatibility and bootstrap
path, but it should not remain the canonical first-party composition path.

Retirement rule:

- Add endpoint/identity binding models first.
- Keep default-deny and DNS policy generation as safe platform defaults.
- Migrate platform, job, and domain service flows to typed
  `NetworkFlowRequirement` inputs.
- Add guard tests that fail if policy generation reaches into concrete plugin
  config or hardcodes service-specific ports when a binding is available.

## Acceptance Evidence

- Schema tests cover endpoint and identity input models.
- Network policy tests cover allowed service-to-service flows from typed
  bindings.
- No plugin imports another plugin's concrete implementation.
- Generator tests prove default-deny and DNS egress remain available while
  binding-derived flows add explicit ingress/egress rules.
- Search evidence proves first-party policy generation no longer depends on
  hardcoded Polaris/OTel/MinIO ports when endpoint bindings are present.

## Non-Goals

- Do not replace Kubernetes NetworkPolicy schema models.
- Do not weaken default-deny behavior.
- Do not make catalog, storage, compute, semantic, or orchestrator plugins
  generate NetworkPolicy YAML directly.
- Do not add raw secrets, tokens, credentials, or auth headers to endpoint or
  identity bindings.
