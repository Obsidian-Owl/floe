# Epic 8A: OCI Client

## Summary

The OCI client provides artifact packaging and distribution via OCI-compliant registries. Data products, compiled artifacts, and configurations are packaged as OCI artifacts for versioned, secure distribution across environments.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-08a-oci-client](https://linear.app/obsidianowl/project/floe-08a-oci-client-a33dd725a781)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-300 | OCI client library | CRITICAL |
| REQ-301 | Artifact push | CRITICAL |
| REQ-302 | Artifact pull | CRITICAL |
| REQ-303 | Tag management | HIGH |
| REQ-304 | Digest verification | CRITICAL |
| REQ-305 | Registry authentication | CRITICAL |
| REQ-306 | Multi-registry support | HIGH |
| REQ-307 | Artifact manifest creation | HIGH |
| REQ-308 | Layer management | HIGH |
| REQ-309 | Content addressing | HIGH |
| REQ-310 | Retry logic | HIGH |
| REQ-311 | Progress reporting | MEDIUM |
| REQ-312 | Artifact inspection | HIGH |
| REQ-313 | Registry mirroring | MEDIUM |
| REQ-314 | Bandwidth optimization | MEDIUM |
| REQ-315 | Artifact caching | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0050](../../../architecture/adr/0050-oci-distribution.md) - OCI artifact distribution
- [ADR-0051](../../../architecture/adr/0051-artifact-format.md) - Artifact format specification

### Contracts
- `OCIClient` - OCI registry client
- `ArtifactManifest` - Artifact manifest model
- `RegistryConfig` - Registry configuration model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── oci/
│   ├── __init__.py
│   ├── client.py                # OCIClient
│   ├── manifest.py              # ArtifactManifest
│   ├── registry.py              # Registry operations
│   ├── auth.py                  # Authentication
│   └── layer.py                 # Layer management
└── cli/
    └── artifact.py              # CLI artifact commands
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 2B | Packages CompiledArtifacts |
| Blocked By | Epic 7A | Uses secrets for registry auth |
| Blocks | Epic 8B | Signing uses OCI client |
| Blocks | Epic 8C | Promotion uses OCI client |
| Blocks | Epic 9A | K8s pulls artifacts from registry |

---

## User Stories (for SpecKit)

### US1: Artifact Push (P0)
**As a** data engineer
**I want** to push data products to OCI registry
**So that** they can be deployed to other environments

**Acceptance Criteria**:
- [ ] `floe artifact push` command works
- [ ] CompiledArtifacts packaged as OCI artifact
- [ ] Tags support semver and environment labels
- [ ] Digest returned after push

### US2: Artifact Pull (P0)
**As a** platform operator
**I want** to pull data products from OCI registry
**So that** I can deploy them to my cluster

**Acceptance Criteria**:
- [ ] `floe artifact pull` command works
- [ ] Pull by tag or digest
- [ ] Digest verification on pull
- [ ] Local cache for efficiency

### US3: Registry Authentication (P0)
**As a** platform operator
**I want** secure registry authentication
**So that** only authorized users can push/pull

**Acceptance Criteria**:
- [ ] Docker config.json support
- [ ] K8s imagePullSecrets support
- [ ] Cloud provider auth (ECR, GCR, ACR)
- [ ] Token refresh handling

### US4: Artifact Inspection (P1)
**As a** platform operator
**I want** to inspect artifact contents
**So that** I can verify what will be deployed

**Acceptance Criteria**:
- [ ] `floe artifact inspect` command
- [ ] List layers and contents
- [ ] Show manifest metadata
- [ ] Display signatures (Epic 8B)

### US5: Multi-Registry Support (P1)
**As a** platform operator
**I want** multiple registries supported
**So that** I can use different registries per environment

**Acceptance Criteria**:
- [ ] Registry per environment in manifest
- [ ] Registry mirroring for DR
- [ ] Cross-registry copy
- [ ] Registry health checks

---

## Technical Notes

### Key Decisions
- OCI Distribution Spec 1.0 compliance
- Artifacts are immutable (tags are mutable pointers)
- Content addressing via SHA256 digests
- Layered format for efficient delta transfers

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Registry availability | MEDIUM | HIGH | Mirroring, retry logic |
| Large artifact size | MEDIUM | MEDIUM | Layer optimization, compression |
| Authentication complexity | HIGH | MEDIUM | Abstraction layer, clear docs |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_oci_client.py`
- **Integration**: `packages/floe-core/tests/integration/test_oci_registry.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/04-artifact-distribution/`
- `docs/architecture/distribution/`
- `packages/floe-core/src/floe_core/oci/`

### Related Existing Code
- CompiledArtifacts from Epic 2B

### External Dependencies
- `oras-py>=0.1.0` (OCI client library)
- `docker>=6.0.0` (config file parsing)
