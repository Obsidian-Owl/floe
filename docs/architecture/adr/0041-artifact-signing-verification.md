# ADR-0041: Artifact Signing and Verification

## Status

Accepted

## Context

OCI artifacts in floe represent immutable platform configurations distributed across environments (dev → staging → production). Supply chain security requires cryptographic verification that artifacts:
- Were created by authorized signers (authenticity)
- Have not been tampered with in transit (integrity)
- Can be traced to specific builds (provenance)

### Requirements from EPIC-06

- **REQ-316**: Cosign integration for artifact signing
- **REQ-317**: Keyless signing with OIDC identity
- **REQ-318**: Key-based signing for air-gapped environments
- **REQ-319**: Trusted signer registry
- **REQ-320**: Signature verification before artifact pull
- **REQ-321**: Signature verification failure handling
- **REQ-322**: Certificate rotation procedures
- **REQ-323**: Signature metadata and attestations
- **REQ-324**: Public key distribution
- **REQ-325**: Air-gapped verification workflow

### Security Threat Model

**Attacks Signing PREVENTS**:
- ✅ **Supply chain attacks**: Attacker injects malicious artifact into registry
- ✅ **Tampering**: Artifact modified after creation (registry compromise)
- ✅ **Identity spoofing**: Attacker pushes artifact claiming to be platform team
- ✅ **Replay attacks**: Old vulnerable artifact republished with new tag

**Attacks Signing DOES NOT PREVENT**:
- ❌ **Vulnerable dependencies**: Signed artifact may contain CVEs
- ❌ **Logic bugs**: Legitimate platform team signs buggy artifact
- ❌ **Compromised build environment**: Attacker controls CI/CD, signs malicious code
- ❌ **Insider threats**: Authorized signer intentionally publishes malicious artifact

**Mitigation Layers**:
1. **Signing** (this ADR): Authenticity and integrity
2. **Policy enforcement** (ADR-0016): Configuration validation at compile-time
3. **Dependency scanning**: CVE detection in CI/CD (Trivy, Grype)
4. **SBOM generation**: Track artifact contents (Syft)
5. **Audit logging**: Who signed, when, from where

### Industry Context (2026)

**Sigstore Cosign** is the industry standard for OCI artifact signing:
- CNCF incubating project (2021), graduated 2024
- Used by Kubernetes, Istio, Tekton, Flux, Argo CD
- Supports keyless signing (OIDC), key-based signing (KMS, local keys)
- Transparency log (Rekor) provides non-repudiation
- Integration with Fulcio CA for short-lived certificates

**Alternatives Considered**:
| Solution | Pros | Cons |
|----------|------|------|
| **Cosign** | Industry standard, keyless signing, Rekor integration | Complex PKI for air-gapped |
| **Notary v2** | Docker Content Trust successor | Less adoption, heavier |
| **GPG** | Proven technology | Manual key management, no OIDC |
| **No signing** | Simple | Zero supply chain protection |

**Decision**: Adopt Cosign with dual-mode support (keyless for cloud, key-based for air-gapped)

## Decision

Implement **artifact signing and verification** using Sigstore Cosign with two operational modes:

1. **Keyless Signing (Default)**: OIDC identity + Fulcio CA + Rekor transparency log
2. **Key-Based Signing (Air-Gapped)**: Local key pairs with offline verification bundles

### Architecture Principles

1. **Signing is mandatory**: All production artifacts MUST be signed
2. **Verification before use**: `floe init` and `floe platform deploy` MUST verify signatures
3. **Identity-based trust**: OIDC identities (GitHub Actions, GitLab CI) as trust anchors
4. **Transparency by default**: All signatures logged to Rekor (cloud deployments)
5. **Air-gapped support**: Offline verification bundles for disconnected environments
6. **Immutable audit trail**: Signature metadata stored as OCI artifact annotations

---

## Keyless Signing (Cloud Deployments)

**Trust Model**: OIDC identity provider (GitHub, GitLab, Google) → Fulcio CA → short-lived certificate

### Workflow

```
┌─────────────────┐
│ GitHub Actions  │
│ (CI/CD)         │
└────────┬────────┘
         │ 1. OIDC token (sub: repo:acme/floe-platform:ref:refs/heads/main)
         ▼
┌─────────────────┐
│ Fulcio CA       │  2. Issue short-lived certificate (valid 10 minutes)
│ (identity.sigstore.dev)
└────────┬────────┘
         │ 3. Certificate (CN=repo:acme/floe-platform:ref:refs/heads/main)
         ▼
┌─────────────────┐
│ Cosign          │  4. Sign artifact with ephemeral key + certificate
│ (floe platform  │
│  publish)       │
└────────┬────────┘
         │ 5. Signature + certificate
         ▼
┌─────────────────┐
│ OCI Registry    │  6. Signature stored as OCI artifact
│ (Harbor/ECR)    │     (sha256-<digest>.sig)
└────────┬────────┘
         │ 7. Signature metadata
         ▼
┌─────────────────┐
│ Rekor           │  8. Transparency log entry (public, immutable)
│ (rekor.sigstore.io)
└─────────────────┘
```

### Signing Configuration

**CI/CD Environment Variables**:
```yaml
# GitHub Actions
env:
  COSIGN_EXPERIMENTAL: 1  # Enable keyless signing
  COSIGN_YES: true        # Auto-confirm prompts
```

**Signing Command**:
```bash
# floe platform publish (with signing)
floe platform publish \
  --registry=harbor.acme.com/floe-artifacts \
  --version=v1.2.3 \
  --sign

# Cosign signs with OIDC identity
cosign sign \
  --oidc-issuer=https://token.actions.githubusercontent.com \
  --oidc-client-id=sigstore \
  harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3
```

**Signature Stored in Registry**:
```
harbor.acme.com/floe-artifacts/
├── platform-manifest:v1.2.3                   # Original artifact
└── sha256-abc123.sig                          # Signature artifact (attached)
    ├── certificate (PEM-encoded)
    ├── signature (base64)
    └── rekor-entry (log index)
```

### Verification Configuration

**Trusted Identities**:
```yaml
# manifest.yaml
artifacts:
  signing:
    mode: keyless
    verification:
      enabled: true
      trusted_issuers:
        - issuer: https://token.actions.githubusercontent.com
          subject: repo:acme/floe-platform:ref:refs/heads/main  # Only main branch

        - issuer: https://gitlab.com
          subject: project_path:acme/floe-platform:ref_type:branch:ref:main

      require_rekor_entry: true  # Signature must be in transparency log
```

**Verification Command**:
```bash
# floe init --platform=v1.2.3 (automatic verification)
floe init --platform=v1.2.3

# Cosign verifies signature
cosign verify \
  --certificate-identity=repo:acme/floe-platform:ref:refs/heads/main \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  --rekor-url=https://rekor.sigstore.io \
  harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3

# Output (success):
Verification for harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - Existence of the claims in the transparency log was verified offline
  - The code-signing certificate was verified using trusted certificate authority certificates

[
  {
    "critical": {
      "identity": {
        "docker-reference": "harbor.acme.com/floe-artifacts/platform-manifest"
      },
      "image": {
        "docker-manifest-digest": "sha256:abc123..."
      },
      "type": "cosign container image signature"
    },
    "optional": {
      "Issuer": "https://token.actions.githubusercontent.com",
      "Subject": "repo:acme/floe-platform:ref:refs/heads/main",
      "run_id": "1234567890",
      "sha": "def456...",
      "workflow": "release"
    }
  }
]
```

**Verification Failure**:
```bash
floe init --platform=v1.2.3

# If signature invalid or missing:
ERROR: Artifact verification failed
Reason: No valid signatures found for harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3

Trusted identities:
  - repo:acme/floe-platform:ref:refs/heads/main (GitHub Actions)

Recommendation:
  - Verify artifact was signed by authorized CI/CD workflow
  - Check Rekor transparency log: https://rekor.sigstore.io
  - Contact platform team if signature is missing

Abort initialization.
```

---

## Key-Based Signing (Air-Gapped Deployments)

**Trust Model**: Pre-distributed public keys → Local key pair → Offline verification

### Workflow

```
┌─────────────────┐
│ Platform Team   │  1. Generate key pair (one-time)
│ (offline)       │     cosign generate-key-pair
└────────┬────────┘
         │ 2. Private key (cosign.key) - PROTECT
         │    Public key (cosign.pub) - DISTRIBUTE
         ▼
┌─────────────────┐
│ Signing Machine │  3. Sign artifact with private key
│ (CI/CD or       │     cosign sign --key=cosign.key ...
│  manual)        │
└────────┬────────┘
         │ 4. Signature
         ▼
┌─────────────────┐
│ OCI Registry    │  5. Signature stored (no Rekor)
│ (Harbor)        │
└─────────────────┘

┌─────────────────┐
│ Data Team       │  6. Verify with public key
│ (air-gapped)    │     cosign verify --key=cosign.pub ...
└─────────────────┘
```

### Key Generation

**One-Time Setup**:
```bash
# Generate key pair (platform team, secure environment)
cosign generate-key-pair

# Output:
# - cosign.key (private key, PASSWORD PROTECTED)
# - cosign.pub (public key, DISTRIBUTE TO DATA TEAMS)

# Store private key securely
# - HashiCorp Vault
# - AWS Secrets Manager
# - Azure Key Vault
# - Offline USB drive (air-gapped)
```

**Key Storage**:
```yaml
# Option 1: Cloud KMS
artifacts:
  signing:
    mode: key-based
    private_key:
      type: aws-kms
      key_id: arn:aws:kms:us-east-1:123456789:key/abc-123

# Option 2: Local file (air-gapped)
artifacts:
  signing:
    mode: key-based
    private_key:
      type: file
      path: /secure/cosign.key  # PASSWORD PROTECTED
      password_env: COSIGN_PASSWORD
```

### Signing Command

```bash
# Sign with local key
export COSIGN_PASSWORD=<secure-password>

cosign sign \
  --key=cosign.key \
  harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3

# Sign with KMS
cosign sign \
  --key=awskms:///arn:aws:kms:us-east-1:123456789:key/abc-123 \
  harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3
```

### Public Key Distribution

**Trusted Distribution Channels**:
1. **Embedded in floe-cli**: Public key baked into CLI binary
2. **OCI registry**: Public key published as artifact
3. **Git repository**: Public key committed to platform repo
4. **Manual transfer**: USB drive for air-gapped environments

**Public Key Storage**:
```bash
# Option 1: Embedded in CLI (most secure)
# floe-cli/src/floe_cli/signing/cosign.pub

# Option 2: Registry artifact
harbor.acme.com/floe-artifacts/cosign-public-key:latest

# Option 3: Git repository
floe-platform/signing/cosign.pub

# Option 4: Local file (air-gapped)
/etc/floe/signing/cosign.pub
```

**Verification Configuration**:
```yaml
# manifest.yaml
artifacts:
  signing:
    mode: key-based
    verification:
      enabled: true
      public_key:
        type: file
        path: /etc/floe/signing/cosign.pub
```

**Verification Command**:
```bash
# Verify with public key
cosign verify \
  --key=cosign.pub \
  harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3

# Output (success):
Verification for harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key

[Signature metadata...]
```

---

## Certificate Rotation (REQ-322)

### Keyless Signing (Automatic)

**Fulcio certificates expire after 10 minutes** (intentionally short-lived):
- No manual rotation needed
- Each signature gets new certificate
- Old signatures remain valid (verified via Rekor)

### Key-Based Signing (Manual)

**Rotation Policy**:
- **Recommended**: Rotate every 90 days
- **Maximum**: Rotate every 365 days
- **Emergency**: Rotate immediately if compromise suspected

**Rotation Procedure**:
```bash
# 1. Generate new key pair
cosign generate-key-pair

# 2. Sign all production artifacts with new key
for tag in $(floe platform list --environment=production); do
  cosign sign --key "${COSIGN_PUBLIC_KEY}" "$tag"
done

# 3. Distribute new public key (cosign-v2.pub)
# - Update floe-cli binary
# - Publish to registry
# - Commit to Git

# 4. Configure grace period (both keys valid)
artifacts:
  signing:
    verification:
      public_keys:
        - path: /etc/floe/signing/cosign.pub       # Old key (grace period)
        - path: /etc/floe/signing/cosign-v2.pub    # New key

# 5. After grace period (30 days), remove old key
artifacts:
  signing:
    verification:
      public_keys:
        - path: /etc/floe/signing/cosign-v2.pub    # New key only
```

---

## Air-Gapped Verification Bundles (REQ-325)

**Problem**: Air-gapped environments cannot reach Rekor transparency log or Fulcio CA.

**Solution**: Bundle signature metadata for offline verification.

### Bundle Creation (Online Environment)

```bash
# Sign artifact and create verification bundle
cosign sign \
  --bundle=platform-manifest-v1.2.3.bundle \
  harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3

# Bundle contents:
# - Signature
# - Certificate chain
# - Rekor entry (offline proof)
# - Fulcio root CA

# Transfer bundle to air-gapped environment (USB, etc.)
```

### Bundle Verification (Air-Gapped Environment)

```bash
# Verify using bundle (no internet required)
cosign verify \
  --bundle=platform-manifest-v1.2.3.bundle \
  --certificate-identity=repo:acme/floe-platform:ref:refs/heads/main \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  --offline \
  harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3

# Verification uses bundled Rekor entry (offline proof)
```

**Bundle Distribution**:
- Artifact annotation: `dev.floe.signing.bundle-url`
- Sidecar artifact: `platform-manifest:v1.2.3-bundle`
- Manual transfer: USB drive with bundles

---

## Signature Metadata and Attestations (REQ-323)

### OCI Artifact Annotations

```json
{
  "manifest": {
    "annotations": {
      "org.opencontainers.image.created": "2024-01-15T10:30:00Z",
      "dev.floe.signature.mode": "keyless",
      "dev.floe.signature.issuer": "https://token.actions.githubusercontent.com",
      "dev.floe.signature.subject": "repo:acme/floe-platform:ref:refs/heads/main",
      "dev.floe.signature.rekor-index": "123456789",
      "dev.floe.signature.certificate-sha256": "abc123...",
      "dev.floe.signature.bundle-url": "harbor.acme.com/floe-artifacts/platform-manifest:v1.2.3-bundle"
    }
  }
}
```

### SLSA Provenance (Future Enhancement)

```yaml
# Future: SLSA provenance attestation
_type: https://in-toto.io/Statement/v0.1
subject:
  - name: harbor.acme.com/floe-artifacts/platform-manifest
    digest:
      sha256: abc123...
predicateType: https://slsa.dev/provenance/v0.2
predicate:
  builder:
    id: https://github.com/acme/floe-platform/actions/workflows/release.yml@main
  buildType: https://github.com/Attestations/GitHubActionsWorkflow@v1
  invocation:
    configSource:
      uri: git+https://github.com/acme/floe-platform
      digest:
        sha1: def456...
      entryPoint: .github/workflows/release.yml
  metadata:
    buildStartedOn: 2024-01-15T10:25:00Z
    buildFinishedOn: 2024-01-15T10:30:00Z
```

---

## Implementation

### floe CLI Integration

```python
# floe_cli/commands/platform/publish.py
import subprocess

def publish_artifact(
    registry: str,
    version: str,
    sign: bool = True,
    signing_mode: str = "keyless"
) -> None:
    """Publish platform artifact with signing."""

    # Step 1: Build and push artifact
    artifact_ref = f"{registry}/platform-manifest:{version}"
    push_artifact(artifact_ref)

    # Step 2: Sign artifact if requested
    if sign:
        if signing_mode == "keyless":
            sign_keyless(artifact_ref)
        elif signing_mode == "key-based":
            sign_with_key(artifact_ref)

def sign_keyless(artifact_ref: str) -> None:
    """Sign artifact using keyless (OIDC) mode."""
    cmd = [
        "cosign", "sign",
        "--yes",  # Auto-confirm
        artifact_ref
    ]

    # COSIGN_EXPERIMENTAL=1 enables keyless signing (set in environment)
    result = subprocess.run(cmd, check=True, capture_output=True)

    # Parse Rekor index from output
    rekor_index = parse_rekor_index(result.stdout)
    logger.info(f"Artifact signed. Rekor index: {rekor_index}")

def sign_with_key(artifact_ref: str) -> None:
    """Sign artifact using key-based mode."""
    key_path = os.getenv("COSIGN_KEY_PATH", "cosign.key")

    cmd = [
        "cosign", "sign",
        f"--key={key_path}",
        artifact_ref
    ]

    subprocess.run(cmd, check=True)
    logger.info(f"Artifact signed with key: {key_path}")
```

```python
# floe_cli/commands/init.py
def init_data_product(platform_version: str, verify: bool = True) -> None:
    """Initialize data product with platform artifact verification."""

    artifact_ref = f"{registry}/platform-manifest:{platform_version}"

    # Step 1: Verify signature before pull
    if verify:
        verify_artifact_signature(artifact_ref)

    # Step 2: Pull artifact
    pull_artifact(artifact_ref)

def verify_artifact_signature(artifact_ref: str) -> None:
    """Verify artifact signature before use."""

    # Read verification config from platform-manifest
    config = load_signing_config()

    if config["mode"] == "keyless":
        verify_keyless(artifact_ref, config)
    elif config["mode"] == "key-based":
        verify_with_key(artifact_ref, config)

def verify_keyless(artifact_ref: str, config: dict) -> None:
    """Verify artifact using keyless mode."""

    for trusted_identity in config["trusted_issuers"]:
        cmd = [
            "cosign", "verify",
            f"--certificate-identity={trusted_identity['subject']}",
            f"--certificate-oidc-issuer={trusted_identity['issuer']}",
            artifact_ref
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Signature verified: {trusted_identity['subject']}")
            return  # Verification successful
        except subprocess.CalledProcessError:
            continue  # Try next trusted identity

    # No valid signature found
    raise SignatureVerificationError(
        f"No valid signature found for {artifact_ref}. "
        f"Trusted identities: {[t['subject'] for t in config['trusted_issuers']]}"
    )
```

### CI/CD Integration (GitHub Actions)

```yaml
# .github/workflows/release.yml
name: Release Platform Artifact

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write  # Required for keyless signing (OIDC token)
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Install Cosign
        uses: sigstore/cosign-installer@v3

      - name: Login to Harbor
        uses: docker/login-action@v3
        with:
          registry: harbor.acme.com
          username: ${{ secrets.HARBOR_USERNAME }}
          password: ${{ secrets.HARBOR_PASSWORD }}

      - name: Build and Publish Artifact
        env:
          COSIGN_EXPERIMENTAL: 1  # Enable keyless signing
        run: |
          floe platform publish \
            --registry=harbor.acme.com/floe-artifacts \
            --version=${{ github.ref_name }} \
            --sign

      - name: Generate SBOM
        run: |
          syft harbor.acme.com/floe-artifacts/platform-manifest:${{ github.ref_name }} \
            -o spdx-json > sbom.spdx.json

      - name: Attach SBOM to Artifact
        run: |
          cosign attach sbom \
            --sbom sbom.spdx.json \
            harbor.acme.com/floe-artifacts/platform-manifest:${{ github.ref_name }}
```

---

## Consequences

### Positive

- **Supply chain security**: Cryptographic proof of artifact authenticity
- **Non-repudiation**: Rekor transparency log provides audit trail
- **Keyless convenience**: No manual key management for cloud deployments
- **Air-gapped support**: Key-based signing + offline bundles for disconnected environments
- **Industry standard**: Cosign is CNCF standard (Kubernetes, Istio, Tekton use it)
- **OIDC integration**: GitHub Actions, GitLab CI identities as trust anchors

### Negative

- **Complexity**: PKI, certificates, transparency logs add learning curve
- **Verification overhead**: Adds ~2-5 seconds to `floe init` and `floe platform deploy`
- **Rekor dependency**: Keyless signing requires internet access to rekor.sigstore.io
- **Key rotation burden**: Manual key rotation for air-gapped deployments
- **Signing tools required**: CI/CD must install cosign

### Neutral

- Signing is mandatory (cannot be disabled for production)
- Verification failures are fatal (cannot bypass)
- Transparency log is public (signatures visible to anyone)

---

## Related ADRs and Requirements

- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md) - OCI registry decision
- [ADR-0039: Multi-Environment Promotion](0039-multi-environment-promotion.md) - Artifact promotion workflows
- [ADR-0040: Artifact Immutability and GC](0040-artifact-immutability-gc.md) - Immutability enforcement
- [REQ-316 to REQ-325](../../plan/requirements/04-artifact-distribution/02-signing-verification.md) - Signing requirements
- [EPIC-06: OCI Artifact System](../../plan/epics/EPIC-06.md) - Implementation epic

## References

- [Sigstore Cosign Documentation](https://docs.sigstore.dev/cosign/overview/)
- [Keyless Signing with OIDC](https://docs.sigstore.dev/cosign/signing/signing_with_self-managed_keys/)
- [Rekor Transparency Log](https://docs.sigstore.dev/logging/overview/)
- [SLSA Provenance](https://slsa.dev/spec/v0.1/requirements)
- [Supply Chain Levels for Software Artifacts (SLSA)](https://slsa.dev/)

---

## Implementation Notes (Epic 8B)

*Added during implementation - January 2026*

### Architecture Decisions Made During Implementation

**1. sigstore-python as Primary SDK**

The implementation uses `sigstore-python` library (v3.x) as the primary signing mechanism instead of shelling out to cosign CLI:

- **Rationale**: Better error handling, type safety, native Python integration
- **Deviation**: Original ADR showed cosign CLI commands; implementation wraps sigstore-python
- **Fallback**: cosign CLI is used for key-based signing with KMS (awskms://, gcpkms://) due to better KMS integration in cosign

**2. Signature Storage in OCI Annotations**

Signatures are stored as OCI manifest annotations rather than separate `.sig` artifacts:

```python
# Annotation keys (packages/floe-core/src/floe_core/oci/signing.py)
ANNOTATION_BUNDLE = "dev.floe.signature.bundle"       # Base64-encoded Sigstore bundle
ANNOTATION_MODE = "dev.floe.signature.mode"           # "keyless" or "key-based"
ANNOTATION_ISSUER = "dev.floe.signature.issuer"       # OIDC issuer URL
ANNOTATION_SUBJECT = "dev.floe.signature.subject"     # Signer identity
ANNOTATION_SIGNED_AT = "dev.floe.signature.signed-at" # ISO8601 timestamp
ANNOTATION_REKOR_INDEX = "dev.floe.signature.rekor-index"
ANNOTATION_CERT_FINGERPRINT = "dev.floe.signature.cert-fingerprint"
```

- **Rationale**: Atomic push (signature travels with manifest), simpler garbage collection
- **Trade-off**: Limited to ~1MB bundle size (sufficient for most signatures)

**3. Concurrent Signing Lock**

File-based locking prevents race conditions when multiple processes sign the same artifact:

```python
# Uses fcntl.flock() with timeout (default: 30s)
# Lock files: $TMPDIR/floe/signing-locks/signing-<hash>.lock
# Configure via: FLOE_SIGNING_LOCK_TIMEOUT environment variable
```

- **Rationale**: OCI annotation updates are not atomic; concurrent updates cause data loss
- **Scope**: Per-artifact lock (different artifacts can be signed concurrently)

**4. OIDC Token Retry with Exponential Backoff**

Token acquisition retries on transient failures:

```python
# Configuration (packages/floe-core/src/floe_core/oci/signing.py)
OIDC_MAX_RETRIES = int(os.environ.get("FLOE_OIDC_TOKEN_MAX_RETRIES", "3"))
OIDC_RETRY_BASE_DELAY = 0.5  # seconds, doubles each retry
OIDC_RETRY_MAX_DELAY = 8.0   # cap
```

- **Rationale**: CI/CD OIDC endpoints can have transient failures
- **Pattern**: Standard exponential backoff with jitter

### Performance Characteristics

| Operation | Typical Latency | Notes |
|-----------|-----------------|-------|
| Keyless sign | 2-4 seconds | Includes Fulcio cert + Rekor log |
| Key-based sign | 0.5-1 second | Local operation, no network |
| Keyless verify | 1-2 seconds | Online Rekor check |
| Offline verify | 0.3-0.5 seconds | Bundle verification only |
| Lock acquisition | < 100ms | Unless contention |

### Module Structure

```
packages/floe-core/src/floe_core/oci/
├── signing.py       # SigningClient, keyless/key-based signing
├── verification.py  # VerificationClient, trust policies
├── errors.py        # SignatureVerificationError, ConcurrentSigningError
└── schemas/
    └── signing.py   # SigningConfig, SignatureMetadata, VerificationResult
```

### Key Files for Future Maintainers

- **Signing implementation**: `packages/floe-core/src/floe_core/oci/signing.py`
- **Verification implementation**: `packages/floe-core/src/floe_core/oci/verification.py`
- **Schema contracts**: `packages/floe-core/src/floe_core/schemas/signing.py`
- **Research notes**: `specs/8b-artifact-signing/research.md` (OTel spans, sigstore patterns)
- **Test coverage**: `packages/floe-core/tests/unit/oci/test_signing.py`, `test_verification.py`

### Lessons Learned

1. **sigstore-python API changes**: v3.x significantly differs from v2.x; use `SigningContext.production()` not `ClientTrustConfig`
2. **Certificate expiry grace period**: Short-lived Fulcio certs (10 min) need grace period handling for verification
3. **Rekor optional for air-gapped**: `require_rekor_entry: false` enables offline verification with bundled proofs
4. **Error message quality**: Users need actionable remediation steps, not just failure reasons
