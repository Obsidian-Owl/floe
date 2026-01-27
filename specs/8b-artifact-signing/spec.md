# Feature Specification: Artifact Signing

**Epic**: 8B (Artifact Distribution - Signing)
**Feature Branch**: `8b-artifact-signing`
**Created**: 2026-01-27
**Status**: Draft
**Input**: User description: "Implement artifact signing with Sigstore/cosign for cryptographic verification of CompiledArtifacts"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keyless Signing in CI/CD (Priority: P0)

A CI/CD pipeline (GitHub Actions, GitLab CI) publishes a signed artifact without managing signing keys. The pipeline uses its OIDC identity to obtain a short-lived certificate from Fulcio CA, signs the artifact, and logs the signature to Rekor transparency log.

**Why this priority**: Keyless signing is the default mode for cloud deployments. It eliminates key management burden while providing cryptographic proof of artifact origin tied to CI/CD identity. This is the most common use case.

**Independent Test**: Can be fully tested by running `floe artifact sign --keyless <artifact-ref>` in a GitHub Actions workflow with OIDC configured, verifying the signature is stored in the registry and logged to Rekor.

**Acceptance Scenarios**:

1. **Given** a CI/CD pipeline with OIDC identity configured, **When** running `floe artifact sign --keyless <artifact-ref>`, **Then** the artifact is signed with a short-lived certificate tied to the OIDC identity, and the signature is stored in the OCI registry as a cosign signature artifact.

2. **Given** a keyless signing operation completes successfully, **When** the signature is created, **Then** an entry is logged to Rekor transparency log with the signature metadata, and the Rekor log index is stored in artifact annotations.

3. **Given** OIDC token acquisition fails (e.g., not running in CI/CD), **When** attempting keyless signing, **Then** a clear error message explains that keyless signing requires OIDC identity and suggests using key-based signing as an alternative.

---

### User Story 2 - Signature Verification Before Deployment (Priority: P0)

A platform operator or data engineer pulls an artifact and the system automatically verifies its signature before use. Unsigned or untrusted artifacts are rejected, ensuring only authorized artifacts are deployed.

**Why this priority**: Verification is the security enforcement point. Without verification, signing provides no security benefit. This is equally critical as signing itself.

**Independent Test**: Can be fully tested by pushing a signed artifact, then pulling it with verification enabled, confirming the verification passes; then attempting to pull an unsigned artifact, confirming rejection.

**Acceptance Scenarios**:

1. **Given** verification is enabled in manifest.yaml with trusted issuers configured, **When** running `floe artifact pull <artifact-ref>`, **Then** the signature is verified against the trusted issuer/subject configuration before the artifact is downloaded.

2. **Given** an artifact with a valid signature from a trusted signer, **When** verification succeeds, **Then** the artifact is downloaded and cached locally, and the verification result (signer identity, timestamp) is logged.

3. **Given** an artifact without a signature or with an invalid signature, **When** verification fails, **Then** the pull operation is rejected with a clear error message explaining the verification failure and listing trusted signers.

4. **Given** an artifact signed by an untrusted signer (not in trusted_issuers), **When** verification is performed, **Then** the pull is rejected with an error identifying the actual signer and the list of trusted signers.

---

### User Story 3 - SBOM Generation and Attestation (Priority: P1)

A security engineer generates a Software Bill of Materials (SBOM) for an artifact to track all dependencies. The SBOM is attached to the artifact as an attestation for compliance and vulnerability scanning.

**Why this priority**: SBOM provides transparency into artifact contents, enabling security scanning and compliance auditing. It's a compliance requirement for many organizations but not required for basic signing functionality.

**Independent Test**: Can be fully tested by running `floe artifact sbom <artifact-ref>` to generate an SBOM, then verifying the SBOM lists Python dependencies and dbt packages, and is attached as an attestation to the artifact.

**Acceptance Scenarios**:

1. **Given** a CompiledArtifacts JSON file, **When** running `floe artifact sbom --generate`, **Then** an SPDX-format SBOM is generated containing Python dependencies (from pyproject.toml/requirements.txt) and dbt package dependencies (from packages.yml).

2. **Given** a generated SBOM, **When** running `floe artifact sbom --attach <artifact-ref>`, **Then** the SBOM is signed and attached to the artifact as an in-toto attestation using cosign attest.

3. **Given** an artifact with an attached SBOM attestation, **When** inspecting the artifact, **Then** the SBOM content is retrievable via `floe artifact inspect --show-sbom <artifact-ref>`.

---

### User Story 4 - Verification Policy Configuration (Priority: P1)

A platform operator configures verification policies in manifest.yaml to enforce signing requirements. Policies define trusted signers, required attestations, and enforcement levels per environment.

**Why this priority**: Policies enable governance over signing requirements. Different environments may have different requirements (e.g., production requires signatures, development does not).

**Independent Test**: Can be fully tested by configuring verification policies in manifest.yaml, then verifying that artifacts are accepted or rejected based on policy rules.

**Acceptance Scenarios**:

1. **Given** a manifest.yaml with verification policy specifying trusted issuers (OIDC identity), **When** an artifact is pulled, **Then** verification checks the signer identity matches one of the trusted issuers.

2. **Given** a verification policy with enforcement level "enforce", **When** signature verification fails, **Then** the pull operation is blocked with a fatal error.

3. **Given** a verification policy with enforcement level "warn", **When** signature verification fails, **Then** a warning is logged but the pull operation continues.

4. **Given** a verification policy requiring SBOM attestation, **When** an artifact lacks an SBOM, **Then** verification fails with an error indicating the missing attestation.

---

### User Story 5 - Key-Based Signing for Air-Gapped Environments (Priority: P2)

An enterprise user in an air-gapped environment signs artifacts using pre-distributed key pairs. No internet access is required for signing or verification.

**Why this priority**: Air-gapped environments are common in regulated industries. This is an alternative mode to keyless signing, supporting offline operation.

**Independent Test**: Can be fully tested by generating a key pair, signing an artifact with the private key, then verifying with the public key in an offline environment.

**Acceptance Scenarios**:

1. **Given** a cosign key pair (cosign.key, cosign.pub), **When** running `floe artifact sign --key cosign.key <artifact-ref>`, **Then** the artifact is signed with the private key and the signature is stored in the registry.

2. **Given** a signed artifact and public key, **When** running verification with `--key cosign.pub` in an offline environment, **Then** the signature is verified without requiring internet access or Rekor.

3. **Given** key-based signing mode, **When** signing an artifact, **Then** no transparency log entry is created (Rekor is not used).

4. **Given** a KMS key reference (AWS KMS, GCP KMS, Azure Key Vault), **When** running `floe artifact sign --key awskms:///arn:aws:kms:... <artifact-ref>`, **Then** the artifact is signed using the KMS key.

---

### Edge Cases

- What happens when Rekor transparency log is unavailable during keyless signing? System fails with a clear error explaining Rekor dependency.
- What happens when the OIDC token expires mid-signing? System refreshes the token or fails gracefully with instructions.
- How does the system handle signature verification for artifacts signed with rotated keys? Support certificate chain validation and grace period for key transitions.
- What happens when pulling an artifact from a registry that doesn't support cosign signatures? Fail with a clear error explaining registry requirements.
- How does the system handle concurrent signing of the same artifact? Use atomic operations to prevent signature corruption.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST integrate cosign for artifact signing, supporting both keyless (OIDC-based) and key-based signing methods. Uses sigstore-python as primary library for keyless signing; cosign CLI as fallback for KMS/attestations (see [research.md](./research.md#decisions-summary)). [REQ-316]
- **FR-002**: System MUST support keyless signing using OIDC identity providers (GitHub Actions, GitLab CI, Google Cloud) with Fulcio CA for certificate issuance. [REQ-317]
- **FR-003**: System MUST support key-based signing using local key files, KMS keys (AWS, GCP, Azure), or hardware security modules. [REQ-318]
- **FR-004**: System MUST verify artifact signatures during pull operations, rejecting unsigned or untrusted artifacts when verification is enabled. [REQ-319]
- **FR-005**: System MUST store signatures in OCI registries following cosign conventions (sha256-<digest>.sig artifacts). [REQ-320]
- **FR-006**: System MUST generate SBOM in SPDX format containing Python and dbt dependencies. [REQ-321]
- **FR-007**: System MUST attach SBOM as an in-toto attestation to artifacts using cosign attest. [REQ-322]
- **FR-008**: System MUST integrate with Rekor transparency log for keyless signing, logging all signatures for auditability. [REQ-323]
- **FR-009**: System MUST support configurable verification policies in manifest.yaml including trusted issuers, required attestations, and enforcement levels. [REQ-324]
- **FR-010**: System MUST provide CLI commands for signing, verification, and SBOM operations: `floe artifact push --sign` (integrated push-and-sign), `floe artifact sign` (standalone for already-pushed artifacts), `floe artifact verify`, `floe artifact sbom`. [REQ-325]
- **FR-011**: System MUST embed signature metadata (signer identity, timestamp, certificate info) in artifact annotations for auditability.
- **FR-012**: System MUST support certificate rotation without breaking existing signature verifications through certificate chain support and grace periods.
- **FR-013**: System MUST log all signature verification attempts with success/failure status, signer identity, and artifact version for audit compliance.
- **FR-014**: System MUST provide clear, actionable error messages for all signing and verification failures with remediation steps.
- **FR-015**: System MUST support offline verification bundles for air-gapped environments containing signatures, certificates, and Rekor entries.

### Key Entities *(include if feature involves data)*

- **SigningConfig**: Configuration for signing mode (keyless/key-based), key references, OIDC providers, and Rekor settings. Location: `manifest.yaml` at `artifacts.signing`
- **VerificationPolicy**: Policy defining trusted issuers, required attestations, enforcement level (enforce/warn/off), and certificate roots. Location: `manifest.yaml` at `artifacts.verification`. Supports per-environment overrides via `artifacts.verification.environments.{env}` for graduated enforcement (e.g., dev=off, staging=warn, prod=enforce)
- **SignatureMetadata**: Artifact annotations containing signer identity, timestamp, certificate chain, Rekor log index
- **AttestationManifest**: In-toto attestation structure for SBOM and provenance attestations
- **VerificationBundle**: Offline bundle containing signature, certificate chain, and Rekor entry for air-gapped verification

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Platform operators can sign artifacts in CI/CD pipelines with zero key management overhead using keyless signing (< 5 seconds added to build time)
- **SC-002**: Data engineers cannot deploy unsigned artifacts when verification enforcement is enabled (100% rejection rate for unsigned artifacts)
- **SC-003**: Security teams can audit artifact provenance by querying signature metadata and Rekor transparency log entries
- **SC-004**: Air-gapped deployments can verify signatures without internet access using offline verification bundles
- **SC-005**: SBOM generation captures 100% of declared Python and dbt dependencies
- **SC-006**: Signature verification adds < 2 seconds to artifact pull operations
- **SC-007**: All signing and verification operations emit OpenTelemetry traces for observability
- **SC-008**: Certificate rotation can be performed without invalidating existing signatures during a configurable grace period

## Scope

### In Scope

- Cosign integration for keyless and key-based signing
- Signature storage in OCI registries (cosign conventions)
- Signature verification during artifact pull
- SBOM generation (SPDX format) and attestation
- Rekor transparency log integration
- Verification policy configuration in manifest.yaml
- CLI commands: `floe artifact push --sign` (integrated), `floe artifact sign` (standalone), `floe artifact verify`, `floe artifact sbom`
- Audit logging of signing and verification operations
- Error handling with actionable remediation guidance
- Air-gapped verification bundles

### Out of Scope

- SLSA provenance attestations (future enhancement)
- Admission controller for Kubernetes (Epic 9A dependency)
- Automated key rotation (manual rotation with grace period support)
- Multi-signature requirements (single signer per artifact)
- GUI for signature management (CLI only)

### Integration Points

**Entry Point**: `floe artifact sign`, `floe artifact verify`, `floe artifact sbom` CLI commands (floe-core package)

**Dependencies**:
- floe-core: OCIClient (Epic 8A - complete) - verification hooks added to `pull()` method
- floe-core: CompiledArtifacts schema, CLI framework
- External: cosign CLI (>= 2.0.0), syft CLI (SBOM generation)
- External: sigstore-python library (>= 3.0.0) for programmatic signing

**Integration Mechanism**:
- `OCIClient.pull()` calls verification internally when `verification.enabled=true` in VerificationPolicy
- Verification failure raises `SignatureVerificationError` before artifact download completes
- Callers of OCIClient API (including CLI and downstream epics) get verification automatically
- Signing operations reuse `OCIClient` authentication (no separate signing credentials needed)

**Produces**:
- SigningConfig, VerificationPolicy schemas (added to floe-core/schemas/)
- signing.py, verification.py, attestation.py modules (added to floe-core/oci/)
- CLI commands registered in floe-core CLI
- Used by: Epic 8C (Promotion verifies signatures), Epic 9A (K8s deployment verifies signatures)

## Assumptions

- Cosign CLI (>= 2.0.0) is available in the execution environment
- For keyless signing, the execution environment provides OIDC identity (CI/CD systems)
- OCI registries support cosign signature storage (Harbor, ECR, GCR, ACR, GHCR all support this)
- Rekor public instance (rekor.sigstore.io) is available for keyless signing; custom Rekor instances can be configured
- Syft CLI is available for SBOM generation
- Python 3.10+ (required for sigstore-python compatibility)

## Technical Notes

### Key Decisions (from ADR-0041)
- Keyless signing (Sigstore) is the default for cloud deployments
- Key-based signing for air-gapped environments and organizations with existing PKI
- SBOM always generated in SPDX format (industry standard)
- Rekor transparency log for non-repudiation (keyless mode only)
- Certificate rotation supported via grace period mechanism

### External Dependencies
- `sigstore>=3.0.0` (Python SDK for Sigstore)
- `cosign` CLI (>= 2.0.0) - external tool, invoked via subprocess
- `syft` CLI - external tool for SBOM generation

### Security Considerations
- Private keys (key-based mode) MUST be password-protected or stored in KMS
- OIDC tokens are short-lived (typically 10 minutes)
- Fulcio certificates are short-lived (10 minutes by default)
- No secrets logged (Pydantic SecretStr for key references)
- Verification failures are fatal in "enforce" mode (no bypass)

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Sigstore availability | LOW | HIGH | Fallback to key-based signing; document outage procedures |
| OIDC token acquisition failures | MEDIUM | MEDIUM | Clear error messages; retry logic with exponential backoff |
| Verification performance impact | MEDIUM | LOW | Caching of verification results; parallel verification |
| Registry doesn't support cosign | LOW | MEDIUM | Document supported registries; fail fast with clear error |

## Clarifications

- Q: How does verification integrate with OCIClient.pull()? A: Verification is integrated inside `OCIClient.pull()` - when `verification.enabled=true` in config, pull automatically verifies before returning artifacts. This ensures verification cannot be bypassed.
- Q: Should signing integrate with existing push command? A: Yes, add `--sign` flag to `floe artifact push` for push-and-sign in one step. Keep separate `floe artifact sign` command for signing already-pushed artifacts.
- Q: Where do SigningConfig and VerificationPolicy live in manifest.yaml? A: Under `artifacts.signing` and `artifacts.verification` sections, grouping with OCI registry config from Epic 8A.
- Q: How do verification requirements differ across environments? A: Per-environment enforcement via `artifacts.verification.environments.{dev,staging,prod}` with different enforcement levels (e.g., dev=off, staging=warn, prod=enforce).
- Q: Does signing reuse OCIClient authentication or need separate credentials? A: Reuse existing OCIClient auth from Epic 8A. Signature artifacts are stored in the same registry, so same credentials apply (Docker config, K8s imagePullSecrets, cloud provider auth).

## References

### Architecture Documents
- [ADR-0041: Artifact Signing and Verification](../../docs/architecture/adr/0041-artifact-signing-verification.md)
- [Epic 8B: Artifact Signing](../../docs/plans/epics/08-artifact-distribution/epic-08b-artifact-signing.md)
- [OCI Registry Requirements](../../docs/architecture/oci-registry-requirements.md)

### Requirements Documents
- [REQ-316 to REQ-325: Artifact Signing and Verification](../../docs/requirements/04-artifact-distribution/02-signing-verification.md)

### External References
- [Sigstore Cosign Documentation](https://docs.sigstore.dev/cosign/overview/)
- [Keyless Signing with OIDC](https://docs.sigstore.dev/cosign/signing/signing_with_containers/)
- [Rekor Transparency Log](https://docs.sigstore.dev/logging/overview/)
- [SPDX Specification](https://spdx.dev/specifications/)
- [In-toto Attestation Framework](https://in-toto.io/)
