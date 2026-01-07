# REQ-316 to REQ-325: Artifact Signing and Verification

**Domain**: Artifact Distribution
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines artifact signing using cosign and signature verification strategies for supply chain security. Signing enables data teams to trust that artifacts come from authorized publishers.

**Key Principle**: Supply chain security via cosign integration (ADR-0038)

## Requirements

### REQ-316: Cosign Signing Integration **[New]**

**Requirement**: System MUST integrate cosign for artifact signing, supporting both keyless (OIDC-based) and key-based signing methods.

**Rationale**: Cosign is the industry standard for container artifact signing. Keyless signing eliminates key management burden.

**Acceptance Criteria**:
- [ ] `floe platform publish <version>` signs artifact automatically
- [ ] Keyless signing: OIDC identity (GitHub OIDC in CI/CD)
- [ ] Key-based signing: cosign private key (for offline environments)
- [ ] Signature stored in OCI registry (cosign convention)
- [ ] Signing configuration optional (dev mode, signing disabled)
- [ ] Signing command: `cosign sign oci://registry/floe-platform:v1.2.3`
- [ ] Clear error messages if signing fails
- [ ] Signature included in artifact metadata

**Enforcement**:
- Cosign integration tests (mock cosign)
- Keyless signing tests (mock OIDC provider)
- Key-based signing tests (test keypair)
- Registry integration tests

**Constraints**:
- MUST use cosign >= 2.0.0
- MUST support both signing methods
- MUST NOT require signing in development
- FORBIDDEN to hardcode private keys in config

**Configuration**:
```yaml
# manifest.yaml
artifacts:
  signing:
    enabled: true
    method: keyless | key-based
    # For keyless (CI/CD)
    oidc_provider: github | gitlab | gcp
    # For key-based (offline)
    private_key_ref: cosign-key  # K8s Secret
```

**Example**:
```bash
# GitHub Actions with OIDC
export COSIGN_EXPERIMENTAL=true
floe platform publish v1.2.3
# Automatically signs with GitHub OIDC identity

# Key-based signing
cosign generate-key-pair  # Generate once
floe platform publish v1.2.3 --key cosign.key
```

**Test Coverage**: `tests/unit/test_cosign_integration.py`

**Traceability**:
- oci-registry-requirements.md lines 124-178
- ADR-0038 (Artifact Signing & Verification)

---

### REQ-317: Signature Metadata Embedding **[New]**

**Requirement**: System MUST embed signature metadata in artifact, including signer identity, timestamp, and certificate information.

**Rationale**: Enables verification of who signed and when.

**Acceptance Criteria**:
- [ ] Metadata includes signer identity (CN from certificate)
- [ ] Metadata includes signing timestamp (ISO 8601)
- [ ] Metadata includes certificate issuer
- [ ] Metadata includes OIDC provider (for keyless)
- [ ] Metadata immutable after signing
- [ ] Searchable: `floe platform list --filter=signer:ci-system`
- [ ] Audit trail: who signed what and when

**Enforcement**:
- Metadata extraction tests
- Metadata validation tests
- Audit logging tests

**Constraints**:
- MUST capture signer identity
- MUST NOT modify signature metadata
- FORBIDDEN to sign without metadata
- MUST be queryable

**Example Metadata**:
```json
{
  "signature_metadata": {
    "signer": "CN=github-runner@github.com,O=GitHub",
    "timestamp": "2024-01-15T10:30:00Z",
    "issuer": "CN=sigstore,O=Sigstore",
    "oidc_provider": "github",
    "certificate_chain": "..."
  }
}
```

**Test Coverage**: `tests/unit/test_signature_metadata.py`

**Traceability**:
- oci-registry-requirements.md
- ADR-0038 (Artifact Signing & Verification)

---

### REQ-318: Signature Verification on Pull **[New]**

**Requirement**: System MUST verify artifact signatures during `floe init --platform=<version>` pull operation, rejecting unsigned artifacts when verification enabled.

**Rationale**: Ensures data teams only use authorized artifacts.

**Acceptance Criteria**:
- [ ] Signature verification automatic on pull
- [ ] Configuration: enforcement = warn | enforce | off
- [ ] warn: Log warning but continue (development)
- [ ] enforce: Reject unsigned artifacts (production)
- [ ] off: Skip verification (air-gapped environments)
- [ ] Public key configuration: from environment, K8s Secret, or embedded
- [ ] Clear error message if signature invalid
- [ ] Trust root validation: reject unknown signers
- [ ] Verification logging with signer identity

**Enforcement**:
- Signature verification tests
- Trust root validation tests
- Enforcement level tests
- Invalid signature rejection tests

**Constraints**:
- MUST verify before using artifact
- MUST reject unsigned in enforce mode
- FORBIDDEN to use artifacts without verification in enforce mode
- MUST support public key from multiple sources

**Configuration**:
```yaml
# floe.yaml or manifest.yaml
artifacts:
  signing:
    enforcement: warn | enforce | off  # Default: warn
    public_key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...
      -----END PUBLIC KEY-----
    # OR
    public_key_ref: cosign-public-key  # K8s Secret
```

**Example**:
```bash
# Verification mode: enforce
$ floe init --platform=v1.2.3
Pulling platform artifacts from oci://registry.example.com/floe-platform:v1.2.3
  ✓ Verifying signature with issuer CN=sigstore,O=Sigstore
  ✓ Signature valid, signer: CN=github-runner@github.com,O=GitHub
  ✓ Downloading artifacts (8.6 KB)

# Invalid signature
$ floe init --platform=v1.2.3 (unsigned artifact)
Error: Artifact signature verification failed
  Enforcement: enforce
  Signature: missing
  Resolution: Contact platform team to sign artifact
```

**Test Coverage**: `tests/unit/test_signature_verification.py`

**Traceability**:
- oci-registry-requirements.md lines 179-197
- ADR-0038 (Artifact Signing & Verification)

---

### REQ-319: Trusted Signer Registry **[New]**

**Requirement**: System MUST maintain registry of trusted signers and reject artifacts signed by unknown signers.

**Rationale**: Prevents unauthorized platform configuration injection.

**Acceptance Criteria**:
- [ ] Trusted signer list: authorized identities
- [ ] Signer identity format: CN from certificate
- [ ] Trust root: root CA certificate
- [ ] Update trusted signers: `floe config set trusted-signers=<list>`
- [ ] Reject unsigned artifacts (when verification enabled)
- [ ] Reject artifacts by untrusted signers
- [ ] Audit log all signature checks
- [ ] Clear error messages: reason for rejection

**Enforcement**:
- Trusted signer tests
- Unauthorized signer rejection tests
- Audit logging tests

**Constraints**:
- MUST reject unknown signers
- MUST maintain trust root
- FORBIDDEN to trust arbitrary signers
- MUST support multiple trusted signers

**Configuration**:
```yaml
# .floe/config.yaml
security:
  trusted_signers:
    - CN=github-runner@github.com,O=GitHub
    - CN=ci-system@acme.com,O=Acme
  trust_root: |
    -----BEGIN CERTIFICATE-----
    MIIBkjCB+wIJAKHHMDqPBDlQMA0GCSqGSIb3DQEBBQUAMBMxETAPBgNVBAMMCG...
    -----END CERTIFICATE-----
```

**Test Coverage**: `tests/unit/test_trusted_signer_registry.py`

**Traceability**:
- security.md
- ADR-0038 (Artifact Signing & Verification)

---

### REQ-320: Rekor Transparency Log Integration **[New]**

**Requirement**: System MUST integrate with Rekor transparency log (sigstore) to verify artifact signatures and enable public auditability.

**Rationale**: Rekor provides public, immutable record of signatures enabling verification without direct access to signing key.

**Acceptance Criteria**:
- [ ] Keyless signing automatically uploads to Rekor
- [ ] Signature verification queries Rekor
- [ ] Rekor URL configurable (default: production sigstore)
- [ ] Rekor unavailability handled gracefully
- [ ] Offline environments can disable Rekor
- [ ] Public verification: anyone can verify signature
- [ ] Artifact immutability: Rekor entry is immutable

**Enforcement**:
- Rekor integration tests (mock Rekor)
- Transparency verification tests
- Offline fallback tests

**Constraints**:
- MUST use Rekor production or custom instance
- MUST NOT fail if Rekor unavailable (graceful degradation)
- FORBIDDEN to modify Rekor entries after signature
- MUST support offline verification (key-based)

**Configuration**:
```yaml
# manifest.yaml (optional)
artifacts:
  signing:
    rekor:
      enabled: true
      server: https://rekor.sigstore.dev  # Default
      # OR for custom
      server: https://rekor.internal.company.com
```

**Example**:
```bash
# Keyless signing automatically uploads to Rekor
export COSIGN_EXPERIMENTAL=true
floe platform publish v1.2.3
# Signature automatically logged to Rekor

# Verification queries Rekor
$ cosign verify-blob --signature sig.txt --certificate cert.crt artifact.tar
# Rekor entry: https://rekor.sigstore.dev/log/entry/<uuid>
```

**Test Coverage**: `tests/integration/test_rekor_integration.py`

**Traceability**:
- oci-registry-requirements.md
- ADR-0038 (Artifact Signing & Verification)

---

### REQ-321: Signature Verification Failure Handling **[New]**

**Requirement**: System MUST handle signature verification failures gracefully with clear error messages and actionable remediation steps.

**Rationale**: Clear error messages enable faster debugging and remediation.

**Acceptance Criteria**:
- [ ] Missing signature: error message suggests contacting platform team
- [ ] Invalid signature: error message suggests re-pulling or verifying trust root
- [ ] Untrusted signer: error message lists trusted signers
- [ ] Expired certificate: error message explains expiration and next steps
- [ ] Rekor unavailable: graceful fallback (if configured)
- [ ] Configuration mismatch: error message explains expected vs. actual
- [ ] Actionable messages: remediation steps included
- [ ] Debug mode: verbose logging for troubleshooting

**Enforcement**:
- Error message tests
- Failure scenario tests
- Debug logging tests

**Constraints**:
- MUST provide actionable error messages
- MUST NOT reveal internal certificate details
- FORBIDDEN to continue without verification in enforce mode
- MUST include remediation steps

**Example Error Messages**:
```
Error: Artifact signature verification failed

Issue: Signature missing
Enforcement: enforce (production)
Artifact: oci://registry.example.com/floe-platform:v1.2.3

Remediation:
1. Contact platform team: platform@acme.com
2. Request signed artifact for v1.2.3
3. Retry after new artifact is published

Debug:
  Platform Configuration: /home/user/.floe/config.yaml
  Verification Mode: enforce
  Trust Root: CN=sigstore,O=Sigstore
  Trusted Signers: 1 configured
  Rekor Status: unreachable (expected: reachable)
```

**Test Coverage**: `tests/unit/test_signature_error_handling.py`

**Traceability**:
- security.md
- ADR-0038 (Artifact Signing & Verification)

---

### REQ-322: Certificate Rotation Support **[New]**

**Requirement**: System MUST support certificate rotation without breaking existing signature verifications through certificate chain support and grace period.

**Rationale**: Enables credential rotation and long-term security.

**Acceptance Criteria**:
- [ ] Certificate chain included with signature
- [ ] Root CA certificate trusted (via trust root)
- [ ] Intermediate certificates chained properly
- [ ] Certificate expiration tracked and alerted
- [ ] Grace period: 7 days before expiration
- [ ] Old certificates supported during grace period
- [ ] New certificates activated immediately
- [ ] Audit trail of certificate changes

**Enforcement**:
- Certificate chain tests
- Rotation tests
- Grace period tests
- Expiration alert tests

**Constraints**:
- MUST support certificate chains
- MUST NOT break verification during rotation
- FORBIDDEN to ignore expired certificates
- MUST alert before expiration

**Configuration**:
```yaml
# manifest.yaml
artifacts:
  signing:
    certificate_rotation:
      grace_period_days: 7
      alert_before_expiry: true
```

**Test Coverage**: `tests/unit/test_certificate_rotation.py`

**Traceability**:
- ADR-0038 (Artifact Signing & Verification)

---

### REQ-323: Audit Logging of Signature Verification **[New]**

**Requirement**: System MUST log all signature verification attempts with success/failure status, signer identity, and artifact version.

**Rationale**: Enables compliance auditing and security investigation.

**Acceptance Criteria**:
- [ ] Log entry for every verification attempt
- [ ] Log includes: timestamp, artifact, signer, status (success/failure), reason
- [ ] Structured logging (JSON)
- [ ] Storage: configurable (local file, syslog, cloud logging)
- [ ] Retention: configurable (default 1 year)
- [ ] Searchable: by artifact, signer, status
- [ ] Compliance export: audit trail for compliance reviews

**Enforcement**:
- Logging tests
- Audit trail tests
- Export functionality tests

**Constraints**:
- MUST log every verification
- MUST include signer identity
- FORBIDDEN to log private data
- MUST support structured logging

**Example Audit Entry**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "event": "signature_verification",
  "artifact": "oci://registry.example.com/floe-platform:v1.2.3",
  "signer": "CN=github-runner@github.com,O=GitHub",
  "status": "success",
  "enforcement_mode": "enforce",
  "user": "data-engineer@acme.com",
  "host": "laptop-001"
}
```

**Test Coverage**: `tests/unit/test_signature_audit_logging.py`

**Traceability**:
- security.md
- ADR-0038 (Artifact Signing & Verification)

---

### REQ-324: Public Key Distribution **[New]**

**Requirement**: System MUST distribute public keys (cosign.pub) for signature verification, supporting multiple distribution channels.

**Rationale**: Enables data teams to verify artifacts without custom configuration.

**Acceptance Criteria**:
- [ ] Public key embedded in floe-cli package
- [ ] Public key published in OCI registry artifact
- [ ] Public key in team documentation
- [ ] Public key in Git repository (public)
- [ ] Key distribution: GitHub, documentation site, email
- [ ] Key pinning: option to pin to specific key
- [ ] Key discovery: automated detection from artifact
- [ ] Key rotation: supported without breaking verification

**Enforcement**:
- Key distribution tests
- Key discovery tests
- Key pinning tests

**Constraints**:
- MUST distribute public key securely
- MUST support multiple distribution channels
- FORBIDDEN to require manual key setup
- MUST handle missing key gracefully

**Example Key Locations**:
```
# Embedded in floe-cli
/opt/floe/etc/cosign.pub

# Published in registry
oci://registry.example.com/floe-keys:v1

# Documentation
https://floe.dev/security/cosign.pub

# Git repository (public)
https://github.com/anthropics/floe/tree/main/security/cosign.pub
```

**Test Coverage**: `tests/unit/test_public_key_distribution.py`

**Traceability**:
- ADR-0038 (Artifact Signing & Verification)

---

### REQ-325: Signature Verification in Air-Gapped Environments **[New]**

**Requirement**: System MUST support signature verification in air-gapped environments without internet access via bundle distribution.

**Rationale**: Enables secure deployments in offline environments.

**Acceptance Criteria**:
- [ ] Bundle export: `floe platform export-bundle --sign --include-keys`
- [ ] Bundle includes: artifact, signatures, public keys, certificate chain
- [ ] Bundle distribution: tarball or container image
- [ ] Bundle import: `floe platform import-bundle --verify`
- [ ] Offline verification: no Rekor access required
- [ ] Key distribution: included in bundle
- [ ] Certificate chain: included for offline verification
- [ ] Clear instructions for air-gapped deployment

**Enforcement**:
- Bundle export/import tests
- Offline verification tests
- Air-gapped environment tests

**Constraints**:
- MUST include all verification materials in bundle
- MUST NOT require internet for verification
- FORBIDDEN to skip verification in air-gapped
- MUST provide clear air-gapped documentation

**Example Workflow**:
```bash
# Connected environment: export with signatures
$ floe platform export-bundle \
  --version=v1.2.3 \
  --include-signatures \
  --include-keys \
  --output=platform-v1.2.3.tar

# Transfer platform-v1.2.3.tar via secure media

# Air-gapped environment: import and verify
$ floe platform import-bundle \
  --bundle=platform-v1.2.3.tar \
  --registry=oci://harbor.internal/floe \
  --verify

Verifying signatures (offline mode)...
  ✓ Signature verified with local key
  ✓ Trust root valid
  ✓ Signer trusted
Importing to registry...
  ✓ Artifact imported
  ✓ Signatures imported
```

**Test Coverage**: `tests/integration/test_air_gapped_verification.py`

**Traceability**:
- oci-registry-requirements.md lines 199-237
- ADR-0038 (Artifact Signing & Verification)

---

## Domain Acceptance Criteria

Artifact Signing and Verification (REQ-316 to REQ-325) is complete when:

- [ ] All 10 requirements have complete template fields
- [ ] Cosign integration working (keyless + key-based)
- [ ] Signature verification on pull implemented
- [ ] Trusted signer registry enforced
- [ ] Rekor transparency log integrated (optional but recommended)
- [ ] Signature verification failures handled gracefully
- [ ] Certificate rotation supported
- [ ] Audit logging implemented
- [ ] Public key distribution setup
- [ ] Air-gapped verification supported
- [ ] All signing/verification tests pass (>80% coverage)
- [ ] Documentation updated with signing/verification flow
- [ ] ADRs backreference requirements
- [ ] Architecture docs backreference requirements

## Epic Mapping

These requirements are satisfied in **Epic 6: OCI Registry** Phase 4C:
- Phase 4C: Artifact signing and signature verification
