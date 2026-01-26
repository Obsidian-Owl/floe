# Research: Network and Pod Security (Epic 7C)

**Feature**: Network and Pod Security
**Epic**: 7C
**Date**: 2026-01-26

## Prior Decisions from Agent-Memory

**Query**: "network policy kubernetes security architecture"

**Findings**:
- NetworkPolicies control traffic between pods at IP address/port level
- Default-deny policies are the foundation of zero-trust networking
- Pod Security Standards (PSS) replaced PodSecurityPolicies in K8s 1.25+
- Three PSS levels: privileged, baseline, restricted

## Architecture Patterns (from Epic 7B RBAC)

### Pattern 1: Schema-Driven Architecture

**Decision**: Follow the Pydantic v2 schema patterns established in Epic 7B

**Rationale**:
- Epic 7B established proven patterns for K8s resource generation
- SecurityConfig is the single source of truth for security configuration
- Pydantic provides validation, serialization, and JSON Schema export

**Alternatives Rejected**:
- Raw dict-based configuration: No validation, error-prone
- Custom YAML parsing: Reinvents wheel, no schema support

### Pattern 2: Plugin ABC + Concrete Implementation

**Decision**: Create `NetworkSecurityPlugin` ABC in floe-core with `K8sNetworkSecurityPlugin` implementation

**Rationale**:
- Consistent with ComputePlugin, OrchestratorPlugin, CatalogPlugin, RBACPlugin patterns
- Entry point discovery enables runtime selection
- ABC ensures contract compliance across implementations

**Alternatives Rejected**:
- Monolithic generator: Violates plugin-first architecture (Principle II)
- Direct K8s client calls: Not testable, tight coupling

### Pattern 3: ManifestGenerator Orchestration

**Decision**: Create `NetworkPolicyManifestGenerator` following `RBACManifestGenerator` pattern

**Rationale**:
- Proven pattern from Epic 7B with audit logging, validation, file organization
- Separates concerns: schema validation vs manifest generation vs file writing
- Supports dry-run mode for testing

**Alternatives Rejected**:
- CLI-only generation: No programmatic access
- Helm-only approach: Loses fine-grained control per-namespace

## Technology Research

### NetworkPolicy Best Practices (2025-2026)

**Source**: [Kubernetes NetworkPolicy Documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

**Key Findings**:
1. **Default-deny first**: Always start with deny-all policy, then add allowlists
2. **DNS egress required**: Port 53 UDP to kube-system must always be allowed
3. **CNI dependency**: NetworkPolicies only work if CNI plugin supports them (Calico, Cilium)
4. **Namespace-scoped**: Standard NetworkPolicy is namespace-scoped (no cluster-wide)

**Design Implications**:
- FR-010, FR-011: Default-deny policies required
- FR-012: DNS egress allowlist built-in
- FR-084: CNI check command needed
- FR-004: Only namespace-scoped policies

### Pod Security Standards (PSS) Best Practices

**Source**: [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)

**Key Findings**:
1. **Three levels**: privileged (none), baseline (prevent known escalation), restricted (hardened)
2. **Namespace labels**: Applied via `pod-security.kubernetes.io/{mode}: {level}`
3. **Modes**: enforce (reject), audit (log), warn (user warning)
4. **K8s 1.25+**: Pod Security Admission controller is default

**Design Implications**:
- FR-051: `floe-jobs` = restricted (ephemeral job pods)
- FR-052: `floe-platform` = baseline (long-running services may need capabilities)
- FR-053: All namespaces get audit=restricted, warn=restricted for visibility

### SecurityContext Best Practices

**Source**: [Kubernetes Pod Security Context](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)

**Key Findings**:
1. **runAsNonRoot: true**: Prevents container from running as root
2. **readOnlyRootFilesystem: true**: Prevents filesystem modifications
3. **allowPrivilegeEscalation: false**: Prevents setuid/setgid attacks
4. **capabilities.drop: ["ALL"]**: Removes all Linux capabilities
5. **seccompProfile: RuntimeDefault**: Uses container runtime's default seccomp filter

**Design Implications**:
- FR-060: Pod-level securityContext with all hardening settings
- FR-061: Container-level securityContext with capabilities drop
- FR-062: seccompProfile required
- FR-063: emptyDir volumes for /tmp, /home when readOnlyRootFilesystem

## Integration Points

### SecurityConfig Extension

**Current Structure** (from Epic 7B):
```python
class SecurityConfig(BaseModel):
    rbac: RBACConfig
    pod_security: PodSecurityLevelConfig
    namespace_isolation: Literal["strict", "permissive"]
```

**Extended Structure** (for Epic 7C):
```python
class SecurityConfig(BaseModel):
    rbac: RBACConfig
    pod_security: PodSecurityLevelConfig
    network_policies: NetworkPoliciesConfig  # NEW
    namespace_isolation: Literal["strict", "permissive"]
```

### CLI Command Integration

**Current RBAC Commands**:
```
floe rbac generate
floe rbac validate
floe rbac audit
floe rbac diff
```

**New Network Commands**:
```
floe network generate
floe network validate
floe network audit
floe network diff
floe network check-cni
```

### Compilation Pipeline Integration

**Stage 3 (Security Validation)** currently validates:
- RBAC configuration
- Secret references

**Extended for 7C**:
- NetworkPolicy configuration
- PSS level validation
- SecurityContext completeness

## Monorepo Structure

### New Files (follows Epic 7B pattern)

```
packages/floe-core/src/floe_core/
├── network/                           # NEW module
│   ├── __init__.py
│   ├── schemas.py                     # NetworkPolicyConfig, EgressRule, etc.
│   ├── generator.py                   # NetworkPolicyManifestGenerator
│   ├── result.py                      # GenerationResult
│   ├── audit.py                       # AuditEvent classes
│   ├── validate.py                    # Manifest validation
│   └── diff.py                        # Policy diff
├── plugins/
│   └── network_security.py            # NetworkSecurityPlugin ABC

plugins/floe-network-security-k8s/     # NEW plugin
├── src/floe_network_security_k8s/
│   ├── __init__.py
│   └── plugin.py                      # K8sNetworkSecurityPlugin
├── tests/
│   ├── unit/
│   └── integration/
└── pyproject.toml

packages/floe-cli/src/floe_cli/commands/
└── network/                           # NEW command group
    ├── __init__.py
    ├── generate.py
    ├── validate.py
    ├── audit.py
    ├── diff.py
    └── check_cni.py

tests/contract/
├── test_network_policy_generator.py   # NEW
├── test_network_to_core_contract.py   # NEW
└── test_network_security_pipeline.py  # NEW
```

### Output Directory

```
target/network/
├── floe-platform-default-deny.yaml
├── floe-platform-allow-egress.yaml
├── floe-platform-allow-ingress.yaml
├── floe-jobs-default-deny.yaml
├── floe-jobs-allow-egress.yaml
└── NETWORK-POLICY-SUMMARY.md
```

## Key Design Decisions

### Decision 1: Extend vs New Plugin Type

**Decision**: Extend existing `SecurityConfig` and create new `NetworkSecurityPlugin` ABC

**Rationale**:
- SecurityConfig is already the authority for security settings
- New plugin ABC follows established pattern (11 plugin types now 12)
- Clear separation: RBACPlugin = RBAC resources, NetworkSecurityPlugin = NetworkPolicy resources

### Decision 2: Default-Deny by Design

**Decision**: Generated policies are default-deny with explicit allowlists

**Rationale**:
- Zero-trust networking is industry standard
- Matches K8s NetworkPolicy best practices
- Prevents accidental exposure of new workloads

### Decision 3: DNS Always Allowed

**Decision**: DNS egress (UDP 53 to kube-system) is always included, not configurable to disable

**Rationale**:
- Blocking DNS breaks all service discovery
- This is a universal requirement, not a policy choice
- Common mistake in NetworkPolicy implementations

### Decision 4: Separate Output Files per Namespace

**Decision**: Generate separate YAML files per namespace (not single file)

**Rationale**:
- Matches kubectl apply workflow (can apply per-namespace)
- Easier to review and audit
- Consistent with Epic 7B RBAC output pattern

### Decision 5: No ClusterNetworkPolicy

**Decision**: Only generate namespace-scoped NetworkPolicies (standard K8s API)

**Rationale**:
- ClusterNetworkPolicy is Cilium/Calico-specific
- Standard API ensures portability across CNI plugins
- Namespace isolation is sufficient for most use cases

## Risk Analysis

### Risk 1: CNI Plugin Compatibility

**Risk**: NetworkPolicies are silently ignored if CNI doesn't support them

**Mitigation**:
- FR-084: `floe network check-cni` command to validate CNI support
- Documentation recommends Calico or Cilium for production
- Warning in `floe deploy` if CNI support not detected

### Risk 2: Breaking Existing Workloads

**Risk**: Default-deny policies could break existing pods

**Mitigation**:
- `floe network validate` checks policies before apply
- Dry-run mode generates but doesn't apply
- NETWORK-POLICY-SUMMARY.md documents all allowed paths

### Risk 3: External Service Access

**Risk**: Jobs need access to cloud DWH (Snowflake, BigQuery) with dynamic IPs

**Mitigation**:
- Allow port 443 egress by default for external HTTPS
- Support CIDR-based rules for known IP ranges
- Document Cilium DNS-based egress as optional enhancement

## References

- [Kubernetes NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Calico NetworkPolicy Tutorial](https://docs.tigera.io/calico/latest/network-policy/get-started/kubernetes-policy/kubernetes-network-policy)
- [RBAC Good Practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/)
- Epic 7B spec: `specs/7b-k8s-rbac/spec.md`
- Epic 7B implementation: `packages/floe-core/src/floe_core/rbac/`
