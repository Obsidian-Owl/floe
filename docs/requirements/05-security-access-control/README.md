# Domain 05: Security and Access Control

**Priority**: CRITICAL
**Total Requirements**: 39
**Status**: Complete specification (Updated 2026-01-07)

## Overview

This domain defines security controls, authentication, authorization, and credential management for floe deployments. Security is enforced through Kubernetes RBAC, network policies, pod security standards, and credential vending mechanisms.

**Core Security Principle**: Zero-Trust Networking + Defense in Depth
- Least-privilege RBAC (namespace isolation)
- Network policies (default deny, explicit allow)
- Pod security standards (restricted execution)
- No hardcoded secrets (credential vending)
- Audit logging (all access)

## Security Architecture Layers

| Layer | Mechanism | Purpose | Requirements |
|-------|-----------|---------|--------------|
| **Identity** | K8s ServiceAccounts | Control pod identity | REQ-400 to REQ-410 |
| **Authorization** | RBAC Roles/RoleBindings | Least-privilege access | REQ-411 to REQ-415 |
| **Network** | NetworkPolicies | Default deny, explicit allow | REQ-416 to REQ-425 |
| **Workload** | Pod Security Standards | Restricted execution | REQ-426 to REQ-430 |
| **Credentials** | Secrets/ESO/Vault | No hardcoded secrets | REQ-431 to REQ-435 |
| **Namespace Identity** | Product-namespace scoping | Cross-product isolation | REQ-436 to REQ-438 |

## Key Architectural Decisions

- **ADR-0022**: Security & RBAC Model - K8s RBAC + network policies + pod security
- **ADR-0023**: Secrets Management Architecture - Credential vending via K8s Secrets, ESO, or Vault
- **ADR-0031**: Service-to-Service Authentication - OAuth2 + JWT for APIs
- **CLAUDE.md**: Security-first development standards

## Security Controls

### Kubernetes RBAC (Least Privilege)

```yaml
floe-platform namespace: Platform services (Dagster, Polaris, Cube, MinIO)
  - floe-platform-admin (full namespace access)
  - floe-dagster (create jobs in floe-jobs, read secrets)
  - floe-polaris (catalog management, S3 access)
  - floe-cube (read catalog, read secrets)

floe-jobs namespace: Ephemeral job pods
  - floe-job-runner (read-only secrets, emit telemetry)

floe-<domain>-domain namespaces: Data mesh domains
  - floe-job-<domain> (domain-scoped secrets and permissions)
```

### Network Policies (Default Deny)

```
floe-jobs → floe-platform/polaris (port 8181)
floe-jobs → floe-platform/otel-collector (ports 4317, 4318)
floe-jobs → floe-platform/minio (port 9000)
floe-jobs → external (port 443 - cloud DWH)
floe-platform → floe-platform (internal only)
* → * (DENY by default)
```

### Pod Security Standards

```
floe-platform: baseline (some privileged capabilities allowed)
floe-jobs: restricted (no root, no privileged, read-only filesystem)
```

### Credential Management

```
Compute targets: K8s Secrets / ESO / Vault (rotated quarterly)
Storage credentials: Polaris credential vending (short-lived, 1h TTL)
API credentials: OAuth2 / JWT (scoped, time-limited)
Internal services: K8s Secrets (long-lived, rotated on demand)
```

## Requirements Files

- [01-rbac-model.md](01-rbac-model.md) - REQ-400 to REQ-415: Service accounts, RBAC roles, namespace isolation
- [02-network-policies.md](02-network-policies.md) - REQ-416 to REQ-425: Network segmentation, default deny, explicit allow
- [03-credential-vending.md](03-credential-vending.md) - REQ-426 to REQ-435: Pod security, secrets management, rotation
- [04-namespace-identity-enforcement.md](04-namespace-identity-enforcement.md) - REQ-436 to REQ-438: Namespace-identity RBAC, catalog write validation, cross-product isolation

## Traceability Matrix

| Requirement Range | ADR | Architecture Doc | Test Spec |
|------------------|-----|------------------|-----------|
| REQ-400 to REQ-415 | ADR-0022 | adr/0022-security-rbac-model.md (lines 56-220) | tests/contract/test_rbac_isolation.py |
| REQ-416 to REQ-425 | ADR-0022 | adr/0022-security-rbac-model.md (lines 449-601) | tests/contract/test_network_policies.py |
| REQ-426 to REQ-435 | ADR-0023 | adr/0023-secrets-management.md | tests/contract/test_secrets_vending.py |
| REQ-436 to REQ-438 | ADR-0030, ADR-0038 | adr/0030-namespace-identity.md | tests/contract/test_namespace_identity_rbac.py |

## Security Checklist

### Pre-Deployment Validation
- [ ] All service accounts created with least-privilege roles
- [ ] All namespaces have Pod Security Standard labels
- [ ] Network policies deployed and rules validated
- [ ] No hardcoded secrets in config files
- [ ] All credentials referenced via SecretReference
- [ ] TLS certificates configured for ingress
- [ ] Security scan passes (Trivy, Kubescape, cosign)

### Post-Deployment Validation
- [ ] Verify all pods running as non-root (uid >= 1000)
- [ ] Verify network policy enforcement (test blocked traffic)
- [ ] Verify audit logging enabled for secrets
- [ ] Verify credential vending working (Polaris)
- [ ] Test secret rotation without pod restart (ESO)

### Ongoing Monitoring
- [ ] Monthly secret rotation
- [ ] Monthly RBAC review (least-privilege audit)
- [ ] Quarterly dependency vulnerability scanning
- [ ] Quarterly audit log review (unauthorized access attempts)

## Epic Mapping

This domain's requirements are satisfied in:

- **Epic 7: Enforcement Engine** (Phase 5A-5B)
  - REQ-400 to REQ-415: RBAC + namespace isolation
  - REQ-416 to REQ-425: Network policies + default deny
  - REQ-426 to REQ-435: Pod security + credential vending

## Validation Criteria

Domain 05 is complete when:

- [ ] All 39 requirements documented with complete template fields
- [ ] K8s RBAC roles and role bindings deployed via Helm charts
- [ ] Network policies enforced in all floe namespaces
- [ ] Pod security standards enforced via namespace labels
- [ ] Secrets management configured (K8s Secrets default, ESO optional)
- [ ] RBAC tests verify least-privilege isolation
- [ ] Network policy tests verify default deny + explicit allow
- [ ] Secret vending tests verify short-lived credentials
- [ ] Security scanning integrated in CI/CD
- [ ] ADRs backreference requirements
- [ ] Test coverage > 80% for security infrastructure

## Notes

- **Backward Compatibility**: MVP had no RBAC enforcement - this is additive
- **Breaking Changes**: NONE - security is enforced, application logic unchanged
- **Migration Risk**: MEDIUM - requires K8s cluster reconfiguration, but no application code changes
- **Compliance**: Meets SOC2, ISO 27001 security control requirements
