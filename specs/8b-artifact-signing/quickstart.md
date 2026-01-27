# Quickstart: Artifact Signing

> **Note**: This document covers both the Python API (implemented in Epic 8B) and
> CLI commands (to be implemented in future epics). Python API examples work now;
> CLI commands show the planned interface.

## Prerequisites

- floe-core package installed (`pip install floe-core`)
- cosign CLI >= 2.0.0 (`brew install cosign` or [install guide](https://docs.sigstore.dev/cosign/installation/)) - required for key-based signing with KMS
- For SBOM generation: syft CLI (`brew install syft`)
- For keyless signing: Running in CI/CD with OIDC (GitHub Actions, GitLab CI)

## 1. Configure Signing (manifest.yaml)

### Keyless Signing (Recommended for CI/CD)

```yaml
# manifest.yaml
artifacts:
  registry:
    uri: oci://harbor.example.com/floe-platform

  signing:
    mode: keyless
    oidc_issuer: https://token.actions.githubusercontent.com

  verification:
    enabled: true
    enforcement: enforce
    trusted_issuers:
      - issuer: https://token.actions.githubusercontent.com
        subject: repo:myorg/floe-platform:ref:refs/heads/main
```

### Key-Based Signing (For Air-Gapped)

```yaml
# manifest.yaml
artifacts:
  registry:
    uri: oci://harbor.internal.com/floe-platform

  signing:
    mode: key-based
    private_key_ref:
      source: env
      name: COSIGN_PRIVATE_KEY

  verification:
    enabled: true
    enforcement: enforce
    public_key_ref:
      source: file
      name: /etc/floe/cosign.pub
```

## 2. Sign Artifacts (CLI - Planned)

> **Note**: These CLI commands are planned for future implementation. See
> "Python API" section below for currently available functionality.

### Push and Sign (One Step)

```bash
# Compile your pipeline
floe platform compile --output target/compiled_artifacts.json

# Push and sign in one command
floe artifact push \
  --artifact target/compiled_artifacts.json \
  --registry oci://harbor.example.com/floe-platform \
  --tag v1.0.0 \
  --sign

# Output:
# Pushing artifact to harbor.example.com/floe-platform:v1.0.0...
# Signing artifact with keyless signing (OIDC)...
# Signature logged to Rekor: https://rekor.sigstore.io/api/v1/log/entries?logIndex=12345678
# Pushed artifact: sha256:abc123...
```

### Sign Existing Artifact

```bash
# Sign an already-pushed artifact
floe artifact sign \
  --artifact oci://harbor.example.com/floe-platform:v1.0.0 \
  --keyless

# Or with a key file
floe artifact sign \
  --artifact oci://harbor.example.com/floe-platform:v1.0.0 \
  --key cosign.key
```

## Python API (Available Now)

### Signing with Python

```python
from floe_core.oci.signing import SigningClient, sign_artifact
from floe_core.schemas.signing import SigningConfig

# Keyless signing (in CI/CD with OIDC)
config = SigningConfig(
    mode="keyless",
    oidc_issuer="https://token.actions.githubusercontent.com"
)

client = SigningClient(config)
metadata = client.sign(
    content=b"artifact content bytes",
    artifact_ref="oci://harbor.example.com/floe-platform:v1.0.0"
)

print(f"Signed by: {metadata.subject}")
print(f"Issuer: {metadata.issuer}")
print(f"Rekor index: {metadata.rekor_log_index}")

# Or use convenience function
metadata = sign_artifact(
    content=b"artifact content bytes",
    artifact_ref="oci://harbor.example.com/floe-platform:v1.0.0",
    config=config
)
```

### Verification with Python

```python
from floe_core.oci.verification import VerificationClient
from floe_core.schemas.signing import VerificationPolicy, TrustedIssuer

policy = VerificationPolicy(
    enabled=True,
    enforcement="enforce",
    trusted_issuers=[
        TrustedIssuer(
            issuer="https://token.actions.githubusercontent.com",
            subject="repo:myorg/floe-platform:ref:refs/heads/main"
        )
    ]
)

client = VerificationClient(policy)
result = client.verify(
    content=b"artifact content bytes",
    artifact_ref="oci://harbor.example.com/floe-platform:v1.0.0",
    signature_metadata=metadata  # From signing or pulled from OCI annotations
)

if result.verified:
    print(f"Verified! Signer: {result.signer_identity}")
else:
    print(f"Verification failed: {result.failure_reason}")
```

### Key-Based Signing

```python
from floe_core.schemas.secrets import SecretReference, SecretSource

# Configure with key file reference
config = SigningConfig(
    mode="key-based",
    private_key_ref=SecretReference(
        source=SecretSource.ENV,
        name="COSIGN_PRIVATE_KEY"  # Env var containing key path
    )
)

client = SigningClient(config)
metadata = client.sign(content, artifact_ref)
```

## 3. Verify Artifacts (CLI - Planned)

> **Note**: These CLI commands are planned for future implementation.

### Automatic Verification on Pull

```bash
# Verification happens automatically when enabled in manifest.yaml
floe artifact pull oci://harbor.example.com/floe-platform:v1.0.0

# Output (success):
# Verifying signature...
# Signer: repo:myorg/floe-platform:ref:refs/heads/main
# Issuer: https://token.actions.githubusercontent.com
# Rekor: https://rekor.sigstore.io/api/v1/log/entries?logIndex=12345678
# Pulling artifact...
# Downloaded: target/compiled_artifacts.json
```

```bash
# Output (failure with enforcement=enforce):
# Verifying signature...
# ERROR: Signature verification failed
# Reason: Signer identity mismatch
# Expected: repo:myorg/floe-platform:ref:refs/heads/main
# Actual: repo:untrusted/repo:ref:refs/heads/main
#
# Trusted issuers configured:
#   - https://token.actions.githubusercontent.com (subject: repo:myorg/floe-platform:ref:refs/heads/main)
```

### Explicit Verification

```bash
# Verify without pulling
floe artifact verify oci://harbor.example.com/floe-platform:v1.0.0

# Verify with specific public key (offline)
floe artifact verify \
  --artifact oci://harbor.example.com/floe-platform:v1.0.0 \
  --key cosign.pub
```

## 4. Generate and Attach SBOM

```bash
# Generate SBOM
floe artifact sbom --generate --output sbom.spdx.json

# Attach SBOM as attestation
floe artifact sbom --attach \
  --artifact oci://harbor.example.com/floe-platform:v1.0.0 \
  --sbom sbom.spdx.json

# View attached SBOM
floe artifact inspect oci://harbor.example.com/floe-platform:v1.0.0 --show-sbom
```

## 5. Per-Environment Verification

```yaml
# manifest.yaml - graduated enforcement
artifacts:
  verification:
    enabled: true
    enforcement: warn  # default
    trusted_issuers:
      - issuer: https://token.actions.githubusercontent.com
        subject: repo:myorg/floe-platform:ref:refs/heads/main
    environments:
      dev:
        enforcement: off  # No verification in dev
      staging:
        enforcement: warn  # Warn but allow
      prod:
        enforcement: enforce  # Block unsigned
        require_sbom: true  # Also require SBOM
```

```bash
# Pull with environment context
FLOE_ENVIRONMENT=prod floe artifact pull oci://harbor.example.com/floe-platform:v1.0.0

# Or via CLI flag
floe artifact pull oci://harbor.example.com/floe-platform:v1.0.0 --environment prod
```

## 6. GitHub Actions Example

```yaml
# .github/workflows/release.yml
name: Release Platform Artifact

on:
  push:
    tags: ['v*']

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write  # Required for keyless signing
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Install floe
        run: pip install floe-core

      - name: Install cosign
        uses: sigstore/cosign-installer@v3

      - name: Login to Registry
        run: |
          echo "${{ secrets.REGISTRY_PASSWORD }}" | \
            docker login harbor.example.com -u ${{ secrets.REGISTRY_USERNAME }} --password-stdin

      - name: Compile and Push
        env:
          COSIGN_EXPERIMENTAL: "1"  # Enable keyless
        run: |
          floe platform compile --output target/compiled_artifacts.json
          floe artifact push \
            --artifact target/compiled_artifacts.json \
            --registry oci://harbor.example.com/floe-platform \
            --tag ${{ github.ref_name }} \
            --sign
```

## Common Issues

### "OIDC token not available"

Keyless signing requires OIDC identity. Ensure:
- Running in CI/CD with OIDC enabled (GitHub Actions: `id-token: write`)
- Set `COSIGN_EXPERIMENTAL=1` for keyless signing

### "Signature verification failed"

Check:
1. `trusted_issuers` in manifest.yaml matches actual signer
2. Artifact was signed with expected identity (branch, repo)
3. `enforcement` level allows pull (`warn` vs `enforce`)

### "cosign not found"

Install cosign: `brew install cosign` or see [installation guide](https://docs.sigstore.dev/cosign/installation/)

## Next Steps

- Configure [verification policies](./data-model.md#verificationpolicy) for your organization
- Set up [SBOM generation](./research.md#6-sbom-generation) in CI/CD
- Review [security considerations](../spec.md#security-considerations)
