# Implementation Plan: Network and Pod Security

**Branch**: `7c-network-pod-security` | **Date**: 2026-01-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/7c-network-pod-security/spec.md`

## Summary

Implement Kubernetes NetworkPolicy generation and Pod Security Standards enforcement for the floe platform. Following Epic 7B RBAC patterns, this epic creates a `NetworkSecurityPlugin` ABC with a `K8sNetworkSecurityPlugin` implementation that generates:
- Default-deny NetworkPolicies for `floe-jobs`, `floe-platform`, and domain namespaces
- Egress allowlists for DNS, Polaris catalog, OTel Collector, MinIO, and external HTTPS
- Pod Security Standards namespace labels (restricted for jobs, baseline for platform)
- Hardened container securityContext configurations

## Technical Context

**Language/Version**: Python 3.10+ (matches floe-core requirements)
**Primary Dependencies**: Pydantic v2 (schemas), structlog (logging), PyYAML, kubernetes client (validation)
**Storage**: File-based (YAML manifests in `target/network/` directory)
**Testing**: pytest with K8s-native integration tests (Kind cluster)
**Target Platform**: Kubernetes 1.25+ (required for Pod Security Admission)
**Project Type**: Monorepo (floe-core extension + new plugin package)
**Performance Goals**: Generate policies for 100 namespaces in <5s
**Constraints**: Only standard K8s NetworkPolicy API (no Cilium/Calico enterprise features)
**Scale/Scope**: 3 core namespaces, unlimited domain namespaces

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core for schemas, plugins/ for K8s implementation)
- [x] No SQL parsing/validation in Python (N/A - this epic doesn't involve SQL)
- [x] No orchestration logic outside floe-dagster (NetworkPolicy generation is configuration, not orchestration)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (NetworkSecurityPlugin ABC)
- [x] Plugin registered via entry point (`floe.network_security`)
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (K8s-native deployment is enforced)
- [x] Pluggable choices documented in manifest.yaml (`security.network_policies.*`)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (SecurityConfig extension documented in contracts/)
- [x] Pydantic v2 models for all schemas (NetworkPoliciesConfig, EgressAllowRule, etc.)
- [x] Contract changes follow versioning rules (SecurityConfig MINOR bump 1.0.0 → 1.1.0)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (all config models)
- [x] Credentials use SecretStr (N/A - no credentials in NetworkPolicy configs)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → NetworkPolicy YAML → K8s)
- [x] Layer ownership respected (Platform Team owns security config, Data Team cannot override)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (via structlog + OTel integration)
- [x] OpenLineage events for data transformations (N/A - this is infrastructure config)

## Project Structure

### Documentation (this feature)

```text
specs/7c-network-pod-security/
├── plan.md              # This file
├── research.md          # Phase 0 output - architecture patterns, technology research
├── data-model.md        # Phase 1 output - entity definitions
├── quickstart.md        # Phase 1 output - developer getting started guide
├── contracts/           # Phase 1 output - interface contracts
│   ├── network-security-plugin-interface.md
│   └── security-config-extension.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Core schemas and generator (floe-core)
packages/floe-core/src/floe_core/
├── security.py                    # EXTEND: Add NetworkPoliciesConfig to SecurityConfig
├── network/                       # NEW module
│   ├── __init__.py
│   ├── schemas.py                 # NetworkPolicyConfig, EgressRule, IngressRule, PortRule
│   ├── generator.py               # NetworkPolicyManifestGenerator
│   ├── result.py                  # NetworkPolicyGenerationResult
│   ├── audit.py                   # NetworkPolicyAuditEvent
│   ├── validate.py                # Manifest validation against cluster
│   └── diff.py                    # Policy drift detection
├── plugins/
│   └── network_security.py        # NetworkSecurityPlugin ABC

# Plugin implementation
plugins/floe-network-security-k8s/
├── src/floe_network_security_k8s/
│   ├── __init__.py
│   └── plugin.py                  # K8sNetworkSecurityPlugin implementation
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   └── test_plugin.py
│   └── integration/
│       └── test_network_policy_deployment.py
└── pyproject.toml

# CLI commands (floe-cli)
packages/floe-cli/src/floe_cli/commands/
└── network/                       # NEW command group
    ├── __init__.py
    ├── generate.py                # floe network generate
    ├── validate.py                # floe network validate
    ├── audit.py                   # floe network audit
    ├── diff.py                    # floe network diff
    └── check_cni.py               # floe network check-cni

# Contract tests (root level)
tests/contract/
├── test_network_policy_generator.py      # NEW
├── test_network_to_core_contract.py      # NEW
└── test_security_config_extension.py     # NEW

# Generated output directory
target/network/
├── floe-platform-default-deny.yaml
├── floe-platform-allow-ingress.yaml
├── floe-platform-allow-egress.yaml
├── floe-jobs-default-deny.yaml
├── floe-jobs-allow-egress.yaml
├── floe-{domain}-domain-default-deny.yaml  # Per domain
├── floe-{domain}-domain-allow-egress.yaml  # Per domain
└── NETWORK-POLICY-SUMMARY.md
```

**Structure Decision**: This follows the established Epic 7B RBAC pattern:
- Core schemas in `floe-core` (single package dependency for consumers)
- Plugin implementation in separate package under `plugins/`
- CLI commands in `floe-cli` command group
- Contract tests at repository root level

## Integration Design

### Entry Points

| Entry Point | Location | Wired Into |
|-------------|----------|------------|
| `floe.network_security` | `plugins/floe-network-security-k8s/pyproject.toml` | Plugin registry discovery |
| `floe network` | `packages/floe-cli/src/floe_cli/commands/network/__init__.py` | CLI command group |
| `SecurityConfig.network_policies` | `packages/floe-core/src/floe_core/security.py` | Manifest parser |

### Dependencies

```
floe-cli
  └── floe-core (NetworkPolicyManifestGenerator, SecurityConfig)
        └── floe-network-security-k8s (K8sNetworkSecurityPlugin)
```

### Cleanup Required

- **None**: This is additive to Epic 7B, no code replacement needed
- Future consideration: Consolidate security-related CLI commands under `floe security` umbrella

## Complexity Tracking

No constitution violations - standard plugin pattern follows Epic 7B RBAC precedent.

| Decision | Justification |
|----------|---------------|
| Separate plugin package | Consistent with other floe plugins, enables independent versioning |
| Extend SecurityConfig | Natural extension point, maintains backward compatibility (MINOR version) |
| New CLI command group | NetworkPolicy commands are distinct from RBAC commands |

## Key Design Decisions

1. **Extend SecurityConfig (not new top-level key)**: NetworkPolicies are part of security configuration, logically grouped under `security.network_policies` in manifest.yaml.

2. **Default-deny by design**: Generated policies start with deny-all, then add explicit allowlists. This is zero-trust networking best practice.

3. **DNS always allowed**: DNS egress (UDP 53 to kube-system) is always included in default-deny policies. Cannot be disabled - blocking DNS breaks all service discovery.

4. **Separate files per namespace**: Each namespace gets its own policy files for easier review and kubectl apply workflow. Matches Epic 7B RBAC output pattern.

5. **No ClusterNetworkPolicy**: Standard K8s NetworkPolicy API only, ensuring portability across CNI plugins (Calico, Cilium, cloud-native CNI).

## Implementation Phases

### Phase 1: Core Schemas and ABC (Week 1)
- Extend SecurityConfig with NetworkPoliciesConfig
- Create NetworkSecurityPlugin ABC
- Create NetworkPolicyConfig, EgressRule, IngressRule schemas
- Contract tests for schema stability

### Phase 2: Generator Implementation (Week 1-2)
- NetworkPolicyManifestGenerator class
- Default-deny policy generation
- Egress allowlist generation
- DNS rule auto-inclusion
- Unit tests with mocked plugin

### Phase 3: K8s Plugin (Week 2)
- K8sNetworkSecurityPlugin implementation
- Namespace-specific policy generation
- Pod Security Standards label generation
- SecurityContext generation
- Plugin compliance tests

### Phase 4: CLI Commands (Week 2-3)
- `floe network generate` command
- `floe network validate` command
- `floe network audit` command
- `floe network diff` command
- `floe network check-cni` command

### Phase 5: Integration Testing (Week 3)
- Kind cluster integration tests
- NetworkPolicy enforcement validation
- Cross-namespace traffic blocking tests
- CNI detection tests

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| CNI not supporting NetworkPolicy | `floe network check-cni` command; documentation recommends Calico/Cilium |
| Breaking existing workloads | Dry-run mode; NETWORK-POLICY-SUMMARY.md documents all changes |
| External services with dynamic IPs | CIDR-based egress rules; default allow port 443 for cloud DWH |

## References

- [Kubernetes NetworkPolicy Documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Epic 7B RBAC Implementation](../7b-k8s-rbac/spec.md)
- [NetworkSecurityPlugin Contract](./contracts/network-security-plugin-interface.md)
- [SecurityConfig Extension Contract](./contracts/security-config-extension.md)
