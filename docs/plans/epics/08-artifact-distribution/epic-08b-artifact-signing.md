# Epic 8B: Artifact Signing

## Summary

Artifact signing provides cryptographic verification of data product artifacts. Using Sigstore/cosign, artifacts are signed with keyless signatures and verified before deployment to ensure authenticity and integrity.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-08b-artifact-signing](https://linear.app/obsidianowl/project/floe-08b-artifact-signing-f7781634af80)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-316 | Cosign integration | CRITICAL |
| REQ-317 | Keyless signing (Sigstore) | HIGH |
| REQ-318 | Key-based signing | MEDIUM |
| REQ-319 | Signature verification | CRITICAL |
| REQ-320 | Signature storage | HIGH |
| REQ-321 | SBOM generation | HIGH |
| REQ-322 | SBOM attestation | HIGH |
| REQ-323 | Transparency log | HIGH |
| REQ-324 | Verification policy | CRITICAL |
| REQ-325 | CI/CD integration | HIGH |

---

## Architecture References

### ADRs
- [ADR-0052](../../../architecture/adr/0052-artifact-signing.md) - Artifact signing strategy
- [ADR-0053](../../../architecture/adr/0053-supply-chain-security.md) - Supply chain security

### Contracts
- `SigningClient` - Signing operations
- `VerificationPolicy` - Policy for signature verification
- `AttestationManifest` - SBOM and attestation model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── oci/
│   ├── signing.py               # SigningClient
│   ├── verification.py          # Verification logic
│   └── attestation.py           # Attestation handling
└── cli/
    └── sign.py                  # CLI sign commands
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 8A | Signs artifacts from OCI client |
| Blocks | Epic 8C | Promotion verifies signatures |
| Blocks | Epic 9A | K8s deployment verifies signatures |

---

## User Stories (for SpecKit)

### US1: Keyless Signing (P0)
**As a** CI/CD pipeline
**I want** keyless signing via Sigstore
**So that** I don't manage signing keys

**Acceptance Criteria**:
- [ ] `floe artifact sign` with OIDC identity
- [ ] Signature stored in registry
- [ ] Transparency log entry created
- [ ] Works in GitHub Actions, GitLab CI

### US2: Signature Verification (P0)
**As a** platform operator
**I want** signatures verified before deployment
**So that** only trusted artifacts are deployed

**Acceptance Criteria**:
- [ ] `floe artifact verify` command
- [ ] Verification policy configurable
- [ ] Untrusted artifacts rejected
- [ ] Verification status in artifact metadata

### US3: SBOM Generation (P1)
**As a** security engineer
**I want** SBOM generated for artifacts
**So that** I know what's inside data products

**Acceptance Criteria**:
- [ ] SPDX format SBOM
- [ ] Python dependencies included
- [ ] dbt package dependencies included
- [ ] SBOM attached as attestation

### US4: Verification Policy (P1)
**As a** platform operator
**I want** configurable verification policies
**So that** I can enforce signing requirements

**Acceptance Criteria**:
- [ ] Policy in manifest.yaml
- [ ] Required signers/identities
- [ ] Environment-specific policies
- [ ] Policy violation alerts

### US5: Key-Based Signing (P2)
**As a** enterprise user
**I want** to use my own signing keys
**So that** I can use existing PKI

**Acceptance Criteria**:
- [ ] KMS key support (AWS, GCP, Azure)
- [ ] Local key file support
- [ ] Key rotation handling
- [ ] Signature algorithm configuration

---

## Technical Notes

### Key Decisions
- Keyless signing (Sigstore) is default
- Key-based signing for air-gapped environments
- SBOM always generated (SPDX format)
- Rekor transparency log for audit

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Sigstore availability | LOW | HIGH | Fallback to key-based |
| OIDC token issues | MEDIUM | MEDIUM | Clear error messages |
| Verification performance | MEDIUM | LOW | Caching, parallel verify |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_signing.py`
- **Integration**: `packages/floe-core/tests/integration/test_cosign.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/04-artifact-distribution/`
- `docs/architecture/distribution/`
- `packages/floe-core/src/floe_core/oci/`

### Related Existing Code
- OCIClient from Epic 8A

### External Dependencies
- `sigstore>=2.0.0`
- `cosign` CLI (external tool)
- `syft` CLI (SBOM generation)
