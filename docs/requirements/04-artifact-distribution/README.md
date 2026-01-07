# Domain 04: Artifact Distribution

**Priority**: CRITICAL
**Total Requirements**: 40
**Status**: Complete specification

## Overview

This domain defines how platform configuration artifacts are stored, versioned, signed, distributed, and promoted across environments. Artifact distribution enables secure, immutable sharing of platform standards between platform teams and data teams.

**Core Architectural Principle**: OCI-Native Distribution (ADR-0016)
- OCI Registry > S3 direct access
- Immutable, content-addressable artifacts
- Industry-standard signing (cosign + sigstore)
- Progressive disclosure (registry, artifact format, promotion)

## Problem Statement

Without artifact distribution, platform teams cannot:
- Version platform standards independently
- Enforce governance policies at compile time
- Share platform configuration securely
- Track artifact provenance and compliance
- Promote configuration through environments
- Implement multi-environment deployments

## Solution Architecture

```
Platform Team                    OCI Registry                Data Teams
     │                               │                            │
     │  manifest.yaml       │                            │
     │         │                     │                            │
     │         ▼                     │                            │
     │  [floe platform compile]      │                            │
     │         │                     │                            │
     │         ▼                     │                            │
     │  [floe platform publish]      │                            │
     │         │                     │                            │
     │         ├─► oci://registry/floe-platform:v1.2.3-dev       │
     │         ├─► oci://registry/floe-platform:v1.2.3           │
     │         └─► oci://registry/floe-platform:v1.2.3-prod      │
     │                               │                            │
     │                               ├────► [cosign sign]         │
     │                               │       (immutable artifact)  │
     │                               │                            │
     │                               │  [floe init --platform=v1.2.3]
     │                               │◄────────────────────────────│
     │                               │                            │
     │                               │  [cosign verify]           │
     │                               │  (signature validation)    │
     │                               │                            │
     │                               │  [Pull immutable artifact] │
     │                               └─────────────────────────────►│
```

## Artifact Types

| Artifact Type | Purpose | Entry Point | Requirements |
|---------------|---------|-------------|--------------|
| Platform Manifest | Governance policies, plugin selection | OCI Registry | REQ-300 to REQ-315 |
| Helm Chart | K8s deployment configuration | OCI Registry | REQ-320 to REQ-325 |
| Plugin Packages | Plugin binaries and metadata | PyPI + OCI | REQ-326 to REQ-330 |
| Signature Metadata | Artifact signatures (cosign) | OCI | REQ-331 to REQ-340 |

## Requirements by Category

### 01-oci-operations.md
- **REQ-300 to REQ-310**: OCI artifact operations (push, pull, list, delete)
- **REQ-311 to REQ-315**: Schema versioning and artifact format

### 02-signing-verification.md
- **REQ-316 to REQ-320**: Artifact signing (cosign integration)
- **REQ-321 to REQ-325**: Signature verification (admission control)

### 03-promotion-rollback.md
- **REQ-326 to REQ-335**: Environment promotion workflows
- **REQ-336 to REQ-340**: Rollback and artifact management

## Key Architectural Decisions

- **ADR-0016**: Platform Enforcement Architecture - OCI registry decision rationale
- **ADR-0038**: Artifact Signing & Verification - Cosign integration strategy
- **ADR-0039**: Multi-Environment Promotion - Environment tag strategy
- **ADR-0040**: Artifact Immutability & Garbage Collection - Retention policies

## Traceability Matrix

| Requirement Range | ADR | Architecture Doc | Test Spec |
|------------------|-----|------------------|-----------|
| REQ-300 to REQ-315 | ADR-0016 | oci-registry-requirements.md | tests/contract/test_oci_operations.py |
| REQ-316 to REQ-325 | ADR-0038 | oci-registry-requirements.md | tests/contract/test_artifact_signing.py |
| REQ-326 to REQ-340 | ADR-0039 | platform-artifacts.md | tests/integration/test_promotion_workflow.py |

## Epic Mapping

This domain's requirements are satisfied in **Epic 6: OCI Registry** and **Epic 7: Enforcement Engine**:

- **Epic 6 Phase 4B: Artifact Publishing**
  - REQ-300 to REQ-310: OCI client implementation
  - REQ-311 to REQ-315: Schema versioning

- **Epic 6 Phase 4C: Artifact Signing**
  - REQ-316 to REQ-325: Cosign integration and verification

- **Epic 7 Phase 5A: Compile-Time Enforcement**
  - REQ-326 to REQ-340: Promotion workflow and rollback

## Validation Criteria

Domain 04 is complete when:

- [ ] All 40 requirements documented with complete template fields
- [ ] OCI client implemented (ORAS-based) in `floe-core`
- [ ] Platform artifact schema defined (Pydantic model)
- [ ] Schema versioning implemented (MAJOR/MINOR/PATCH)
- [ ] Cosign signing integration complete
- [ ] Signature verification admission controller implemented
- [ ] Environment promotion workflow implemented
- [ ] Rollback mechanism tested
- [ ] All OCI operations tests pass (push, pull, list, delete)
- [ ] Signing/verification tests pass
- [ ] Promotion/rollback tests pass
- [ ] ADRs backreference requirements
- [ ] Architecture docs backreference requirements
- [ ] Test coverage > 80% for artifact distribution

## Related Documents

- [platform-artifacts.md](../../architecture/platform-artifacts.md) - Artifact structure and workflow
- [oci-registry-requirements.md](../../architecture/oci-registry-requirements.md) - Registry configuration and resilience
- [ADR-0016: Platform Enforcement Architecture](../../architecture/adr/0016-platform-enforcement-architecture.md) - OCI decision
- [ADR-0038: Artifact Signing & Verification](../../architecture/adr/0038-artifact-signing-verification.md) - Cosign strategy
- [ADR-0039: Multi-Environment Promotion](../../architecture/adr/0039-multi-environment-promotion.md) - Promotion strategy
- [ADR-0040: Artifact Immutability & GC](../../architecture/adr/0040-artifact-immutability-gc.md) - Retention policies

## Requirements Files

- [01-oci-operations.md](01-oci-operations.md) - REQ-300 to REQ-315: OCI operations and schema versioning
- [02-signing-verification.md](02-signing-verification.md) - REQ-316 to REQ-325: Signing and verification
- [03-promotion-rollback.md](03-promotion-rollback.md) - REQ-326 to REQ-340: Promotion and rollback workflows

## Notes

- **Backward Compatibility**: Artifact distribution is new (no MVP equivalent)
- **Breaking Changes**: NONE - New feature, additive to existing architecture
- **Migration Risk**: LOW - Well-defined OCI standards, extensive test coverage
- **Security Considerations**: Artifact signing enables supply chain security
