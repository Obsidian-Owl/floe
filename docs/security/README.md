# Security Documentation Index

**Purpose**: Central hub for floe-platform security research, controls inventory, and remediation guidance.

---

## Quick Navigation

### For Security Research
Start here to understand security controls in the floe-platform Helm chart:
- **[SECURITY-RESEARCH-STAGE-4-SUMMARY.md](./SECURITY-RESEARCH-STAGE-4-SUMMARY.md)** - Executive summary of research findings (5 min read)

### For Control Inventory
Comprehensive catalog of all existing security controls:
- **[SECURITY-CONTROLS-CATALOG.md](./SECURITY-CONTROLS-CATALOG.md)** - Complete control inventory with configuration options (20 min read)

### For Implementation Details
Technical reference for developers implementing or modifying controls:
- **[SECURITY-CONTROL-IMPLEMENTATION-MAP.md](./SECURITY-CONTROL-IMPLEMENTATION-MAP.md)** - File locations, helper templates, usage patterns (15 min read)

### For Remediation Planning
Identified gaps and step-by-step remediation guidance:
- **[SECURITY-CONTROL-GAPS.md](./SECURITY-CONTROL-GAPS.md)** - Gaps, inconsistencies, and remediation options (25 min read)

---

## Document Purpose and Scope

| Document | Purpose | Audience | Length | Complexity |
|----------|---------|----------|--------|-----------|
| SUMMARY | Research findings and patterns | All | 5 min | Low |
| CATALOG | Control inventory and options | Auditors, operators | 20 min | Medium |
| IMPLEMENTATION-MAP | File locations and templates | Developers | 15 min | High |
| GAPS | Issues and remediations | Architects, maintainers | 25 min | High |

---

## Key Findings Summary

### Controls Inventory
- ✅ **Fully Implemented**: Pod security context, container security context, RBAC
- ⚠️ **Partially Implemented**: Network policies (optional), secrets (multiple tiers)
- ❌ **Not Enforced**: Pod Security Standards, network policies, secret encryption
- ❓ **Unclear**: When to use External Secrets vs. K8s native secrets

### Critical Gaps (Security Impact)
1. **Pod Security Standards** - Configured but not enforced (namespace labels required)
2. **Network Policies** - Excellent design but disabled by default
3. **Secret Encryption** - Unencrypted at rest (etcd encryption required)

### Consistency Issues (Maintenance Impact)
1. **PostgreSQL security context** - Hardcoded instead of using helper
2. **Init container overrides** - No documentation explaining privilege elevation
3. **Image tags** - Using mutable tags instead of immutable digests

---

## Control Status Matrix

### Control Implementation Status

| Control | Configured | Enforced | Recommended Action |
|---------|-----------|----------|-------------------|
| Pod Security Standards | ✅ Yes | ❌ No | Add namespace labels (helm hook) |
| Pod Security Context | ✅ Yes | ✅ Yes | No action needed |
| Container Security Context | ✅ Yes | ✅ Yes | Fix PostgreSQL hardcoding |
| Network Policies | ✅ Yes | ❌ No | Enable by default (prod) |
| RBAC | ✅ Yes | ✅ Yes | No action needed |
| Service Account | ✅ Yes | ✅ Yes | Consider token automount |
| K8s Secrets | ✅ Yes | ❌ No | Require etcd encryption (prod) |
| External Secrets | ✅ Yes | ❌ No | Require operator (prod) |
| Image Pull Secrets | ✅ Yes | ❌ No | Support digests |
| Pod Disruption Budget | ✅ Yes | ❌ No | Enable by default (HA) |
| Resource Quota | ✅ Yes | ❌ No | Enable by default (multi-tenant) |

**Legend**:
- ✅ Yes = Present in chart
- ❌ No = Not present or optional
- ⚠️ Partial = Some presence/enforcement

---

## Security Tiers by Environment

### Development
```yaml
# Insecure for faster iteration
podSecurityStandards: enabled (warn only)
networkPolicy: disabled
externalSecrets: disabled
encryption: none
imageDigests: optional
```

### Staging
```yaml
# Moderate security for testing
podSecurityStandards: enforced (warn + audit)
networkPolicy: enabled
externalSecrets: optional (recommended)
encryption: etcd encryption recommended
imageDigests: optional
```

### Production
```yaml
# Maximum security
podSecurityStandards: enforced (strict)
networkPolicy: enabled
externalSecrets: required
encryption: etcd encryption + external secrets
imageDigests: required
```

---

## Quick Reference Guides

### For Operators Deploying the Chart

**Minimum Production Checklist**:
```bash
# 1. Install with required controls
helm install floe ./charts/floe-platform \
  -f values-prod.yaml \
  --set networkPolicy.enabled=true

# 2. Apply Pod Security Standards labels
kubectl label namespace floe-prod \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted

# 3. Verify pod compliance
kubectl get pods -n floe-prod -o wide
# All pods should show restricted PSS status

# 4. Enable etcd encryption (cluster-level, not chart)
# See: docs/security/SECURITY-CONTROLS-CATALOG.md#secret-management
```

### For Developers Modifying Security

**Consistency Checklist**:
1. Use helper templates (don't hardcode `securityContext`)
2. Document why any security context deviates from defaults
3. Add comments explaining privilege elevation (init containers)
4. Test with `--dry-run` to verify generated manifests

**Common Tasks**:
- **Add new component**: Copy from existing (Polaris or PostgreSQL), use helpers
- **Change security context globally**: Update `values.yaml` section (2 places)
- **Add network policy rule**: Update `networkpolicy.yaml` template
- **Add secret**: Update appropriate `secret-*.yaml` or use ExternalSecret

### For Security Auditors

**Audit Checklist**:
1. Verify namespace labels applied (see: SECURITY-CONTROLS-CATALOG.md section "Pod Security Standards")
2. Verify network policies enabled (see: SECURITY-CONTROLS-CATALOG.md section "Network Policies")
3. Verify etcd encryption configured (cluster-level, not chart)
4. Verify secret encryption enabled (External Secrets or K8s secrets + etcd encryption)
5. Verify RBAC least privilege (see: SECURITY-CONTROLS-CATALOG.md section "RBAC")

---

## Remediation Roadmap

### Phase 1: Critical (Week 1)
**Goal**: Enforce critical controls

- [ ] Pod Security Standards enforcement (namespace labels)
- [ ] Network policies enabled by default (production)
- [ ] Secret encryption required (External Secrets or etcd)

**Impact**: Security posture moves from "configured" to "enforced"

### Phase 2: Consistency (Week 2)
**Goal**: Fix implementation inconsistencies

- [ ] PostgreSQL uses helper template
- [ ] Init containers documented
- [ ] Image digests supported

**Impact**: Reduced maintenance burden, improved clarity

### Phase 3: Operational (Week 3)
**Goal**: Improve defaults

- [ ] Pod Disruption Budgets enabled by default (HA)
- [ ] Resource Quotas enabled by default (multi-tenant)
- [ ] Service account token automount per-container

**Impact**: Better defaults, fewer misconfigurations

---

## File Structure Reference

```
docs/security/
├── README.md (this file)
│   └── Central navigation and quick reference
│
├── SECURITY-RESEARCH-STAGE-4-SUMMARY.md
│   └── Overview, key findings, patterns
│   └── Best for: executives, architects
│
├── SECURITY-CONTROLS-CATALOG.md
│   └── Complete inventory of all controls
│   └── Best for: auditors, operators
│
├── SECURITY-CONTROL-IMPLEMENTATION-MAP.md
│   └── File locations, helpers, templates
│   └── Best for: developers, chart maintainers
│
└── SECURITY-CONTROL-GAPS.md
    └── Gaps, inconsistencies, remediation options
    └── Best for: architects, lead developers
```

---

## Key Documents in Helm Chart

**Security-Related Files**:
```
charts/floe-platform/
├── values.yaml
│   ├── podSecurityStandards (lines 521-532)
│   ├── podSecurityContext (lines 535-541)
│   ├── containerSecurityContext (lines 544-551)
│   ├── networkPolicy (lines 556-564)
│   ├── rbac (lines 497-499)
│   ├── serviceAccount (lines 504-515)
│   ├── externalSecrets (lines 662-703)
│   └── [other security controls...]
│
├── templates/
│   ├── _helpers.tpl (helper templates)
│   ├── networkpolicy.yaml (network policies)
│   ├── role.yaml (RBAC)
│   ├── rolebinding.yaml (RBAC)
│   ├── serviceaccount.yaml (service accounts)
│   ├── secret-postgresql.yaml
│   ├── secret-dagster.yaml
│   ├── externalsecret.yaml
│   ├── deployment-polaris.yaml
│   ├── statefulset-postgresql.yaml
│   └── [other deployments...]
```

---

## Glossary

| Term | Definition | Reference |
|------|-----------|-----------|
| **PSS** | Pod Security Standards - K8s admission control for pod security | CATALOG: Pod Security Standards |
| **RBAC** | Role-Based Access Control - K8s authorization system | CATALOG: RBAC Configuration |
| **SecComp** | Secure Computing - Linux kernel security feature | CATALOG: Security Contexts |
| **NetworkPolicy** | K8s network segmentation control | CATALOG: Network Policies |
| **ExternalSecret** | Secret synced from external vault (Vault, AWS Secrets Manager, etc.) | CATALOG: Secret Management |
| **etcd** | K8s backing store (encrypted at rest optional) | GAPS: Secret Management Gap |
| **Image Digest** | SHA256 hash of image (immutable) vs. tag (mutable) | GAPS: Image Tags Gap |
| **fsGroup** | Pod-level file system group ownership | CATALOG: Security Contexts |

---

## Common Questions

### Q: Which documents should I read?

**As a...** | **Read this first** | **Then read** | **Reference**
---|---|---|---
Developer | IMPLEMENTATION-MAP | SUMMARY | CATALOG
Operator | CATALOG | SUMMARY | none
Auditor | CATALOG | GAPS | IMPLEMENTATION-MAP
Architect | SUMMARY | GAPS | CATALOG + IMPLEMENTATION-MAP
Manager | SUMMARY | none | none

### Q: Where do I find security context definitions?

See: SECURITY-CONTROL-IMPLEMENTATION-MAP.md section "Security Context Injection"

### Q: How do I enable Network Policies?

See: SECURITY-CONTROLS-CATALOG.md section "Network Policies" OR SECURITY-CONTROL-GAPS.md Gap #2

### Q: Why are secrets unencrypted?

See: SECURITY-CONTROL-GAPS.md Gap #3

### Q: How do I know if my deployment is secure?

See: SECURITY-CONTROLS-CATALOG.md section "Configuration Hierarchy" + SECURITY-CONTROL-GAPS.md Remediation Roadmap

---

## Updates and Changes

**Document Version**: 1.0
**Last Updated**: 2026-02-01
**Chart Version Analyzed**: 0.1.0

**Change Log**:
- 2026-02-01: Initial research complete, all documents created

---

## Contact and Support

For questions about security controls in the floe-platform Helm chart:
1. Check the appropriate document (use Quick Navigation section above)
2. Search for control name in SECURITY-CONTROLS-CATALOG.md
3. Reference IMPLEMENTATION-MAP.md for file locations
4. Check GAPS.md for known issues and remediation

---

## Related Documentation

- [Architecture](../../docs/architecture/) - System design and component interactions
- [Testing](../../TESTING.md) - Test organization and standards
- [Deployment Guide](../../docs/guides/) - Installation and deployment procedures
- [Epic 9B Specification](../../.specify/epics/epic-9b/) - Full Helm chart specification

---

## Acknowledgments

This security controls catalog was developed as part of **Epic 9B: Helm Charts Specification and Analysis** to provide comprehensive documentation of existing security controls and identify remediation opportunities.

**Research Phase**: Stage 4 - Catalog Existing Security Controls
**Completion Date**: 2026-02-01
**Documentation**: 58 KB across 4 markdown files + this index
