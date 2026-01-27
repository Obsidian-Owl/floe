# Research: Artifact Signing

**Feature**: Epic 8B - Artifact Signing
**Date**: 2026-01-27
**Status**: Complete

## Prior Decisions (from Agent Memory)

- Epic 8A OCI Client complete with verification hooks prepared
- ADR-0041 established Sigstore/cosign as the signing strategy
- Keyless signing (OIDC) is default, key-based for air-gapped environments

## Research Topics

### 1. OCIClient Integration Points

**Source**: Background exploration of `packages/floe-core/src/floe_core/oci/client.py`

#### Verification Hook Location in pull()

The exact location for signature verification integration is:

```python
# Line 697: Fetch from registry
content, digest = self._fetch_from_registry(tag)

# ← INSERT VERIFICATION HERE (after fetch, before deserialize)
# if self._verification_policy.enabled:
#     self._verify_signature(content, digest, tag)

# Line 700: Deserialize
artifacts = self._deserialize_artifacts(content)
```

**Key Insight**: Verification MUST happen after content fetch but before deserialization to prevent use of unverified artifacts.

#### Method Signatures to Extend

| Method | Current Signature | Signing Extension |
|--------|------------------|-------------------|
| `push()` | `(artifacts, tag, annotations=None)` | Add `sign: bool = False` parameter |
| `pull()` | `(tag, verify_digest=True)` | `verify_digest` reserved for signing |
| `inspect()` | `(tag)` | Update `signature_status` from verification |

#### Error Class to Add

```python
class SignatureVerificationError(OCIError):
    """Raised when artifact signature verification fails."""
    exit_code: int = 6

    def __init__(self, artifact_ref: str, reason: str,
                 expected_signer: str | None = None,
                 actual_signer: str | None = None) -> None:
        self.artifact_ref = artifact_ref
        self.reason = reason
        self.expected_signer = expected_signer
        self.actual_signer = actual_signer
        super().__init__(f"Signature verification failed for {artifact_ref}: {reason}")
```

### 2. CLI Command Patterns

**Source**: Background exploration of `packages/floe-core/src/floe_core/cli/artifact/`

#### Existing Artifact Command Group

```text
floe artifact
├── push  # Existing - add --sign flag
├── sign  # NEW - standalone signing
├── verify  # NEW - explicit verification
└── sbom  # NEW - SBOM generation
```

#### Click Patterns to Follow

From `push.py`:

```python
@click.command(
    name="push",
    help="""Push CompiledArtifacts to OCI registry.""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--artifact", "-a",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    required=True,
    help="Path to CompiledArtifacts JSON file.",
)
```

**Key Patterns**:
- Use `click.Path()` with `exists=True` for input files
- Use `-a` short form for `--artifact` consistently
- Use `click.Choice()` for enum-like options
- Follow error handling via `error_exit()` from `cli/utils.py`

#### Error Handling Pattern

```python
from floe_core.cli.utils import error_exit, success, info, ExitCode

def _handle_sign_error(e: Exception) -> NoReturn:
    """Handle signing errors with appropriate exit codes."""
    if isinstance(e, SignatureVerificationError):
        error_exit(f"Verification failed: {e.reason}", exit_code=ExitCode.VALIDATION_ERROR)
    elif isinstance(e, FileNotFoundError):
        error_exit(f"File not found: {e}", exit_code=ExitCode.FILE_NOT_FOUND)
    else:
        error_exit(f"Signing failed: {e}", exit_code=ExitCode.GENERAL_ERROR)
```

### 3. sigstore-python API

**Source**: Background librarian research

#### Key Classes

| Class | Purpose | Location |
|-------|---------|----------|
| `SigningContext` | Creates signing sessions | `sigstore.sign` |
| `Signer` | Signs artifacts with identity | `sigstore.sign` |
| `Verifier` | Verifies signatures | `sigstore.verify` |
| `Bundle` | Contains signature + materials | `sigstore.models` |
| `VerificationMaterials` | Verification inputs | `sigstore.verify` |

#### Keyless Signing Pattern

```python
from sigstore.sign import SigningContext
from sigstore.oidc import Issuer
from sigstore.models import Bundle

# Production trust config (uses public Sigstore)
trust_config = ClientTrustConfig.production()
issuer = Issuer(trust_config.signing_config.get_oidc_url())
context = SigningContext.from_trust_config(trust_config)

# Get OIDC identity token (automatic in CI/CD)
token = issuer.identity_token()

# Sign artifact
with context.signer(token, cache=True) as signer:
    bundle: Bundle = signer.sign_artifact(artifact_bytes)

# Save bundle (contains signature + certificate + Rekor entry)
bundle_json = bundle.to_json()
```

#### Verification Pattern

```python
from sigstore.verify import Verifier
from sigstore.verify.policy import Identity

# Create verifier with production trust root
verifier = Verifier.production()

# Define expected identity (from trusted_issuers config)
identity = Identity(
    identity="repo:acme/floe-platform:ref:refs/heads/main",
    issuer="https://token.actions.githubusercontent.com"
)

# Verify
result = verifier.verify_artifact(
    input_=artifact_bytes,
    bundle=bundle,
    policy=identity
)
# Raises VerificationError if invalid
```

#### Bundle Structure

```json
{
  "$case": "messageSignature",
  "messageSignature": {
    "messageDigest": {
      "algorithm": "SHA2_256",
      "digest": "base64-encoded-sha256"
    },
    "signature": "base64-encoded-signature"
  },
  "verificationMaterial": {
    "certificate": {
      "rawBytes": "base64-encoded-x509-cert"
    },
    "tlogEntries": [{
      "logIndex": "12345678",
      "logId": {...},
      "inclusionProof": {...}
    }]
  }
}
```

### 4. Annotation-Based Signature Storage

**Decision**: Store signature bundles as OCI annotations

#### Annotation Schema

| Annotation | Purpose | Value |
|------------|---------|-------|
| `dev.floe.signature.bundle` | Sigstore bundle JSON | Base64-encoded |
| `dev.floe.signature.mode` | Signing mode | `keyless` or `key-based` |
| `dev.floe.signature.issuer` | OIDC issuer (keyless) | URL string |
| `dev.floe.signature.subject` | Signer identity | Certificate subject |
| `dev.floe.signature.rekor-index` | Transparency log entry | Integer |

**Alternative Considered**: Cosign's separate signature artifact (`sha256-<digest>.sig`). **Rejected** because:
- Requires two OCI operations per pull
- More complex cache management
- Annotations are simpler for our use case

### 5. Manifest.yaml Schema Extension

**Decision**: Add `artifacts.signing` and `artifacts.verification` sections

```yaml
artifacts:
  registry:
    uri: oci://harbor.example.com/floe
    # ... existing config

  signing:
    mode: keyless  # or 'key-based'
    # For keyless mode:
    oidc_issuer: https://token.actions.githubusercontent.com
    rekor_url: https://rekor.sigstore.io  # optional, defaults to production
    # For key-based mode:
    private_key_ref:
      source: env
      name: COSIGN_PRIVATE_KEY

  verification:
    enabled: true
    enforcement: enforce  # or 'warn', 'off'
    trusted_issuers:
      - issuer: https://token.actions.githubusercontent.com
        subject: repo:acme/floe-platform:ref:refs/heads/main
      - issuer: https://gitlab.com
        subject: project_path:acme/floe-platform:ref_type:branch:ref:main
    require_rekor: true  # require transparency log entry
    require_sbom: false  # require SBOM attestation
    # Per-environment overrides
    environments:
      dev:
        enforcement: off
      staging:
        enforcement: warn
      prod:
        enforcement: enforce
        require_sbom: true
```

### 6. SBOM Generation

**Tool**: Syft CLI (external, invoked via subprocess)

**Command**:
```bash
syft packages dir:./project -o spdx-json > sbom.spdx.json
```

**Integration Pattern**:
```python
import subprocess
import json

def generate_sbom(project_path: Path) -> dict:
    """Generate SPDX SBOM using syft."""
    result = subprocess.run(
        ["syft", "packages", f"dir:{project_path}", "-o", "spdx-json"],
        capture_output=True,
        text=True,
        check=True
    )
    return json.loads(result.stdout)
```

**Attestation**: Attach SBOM as cosign attestation:
```bash
cosign attest --predicate sbom.spdx.json --type spdx <artifact-ref>
```

## Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary signing lib | sigstore-python | Native Python, keyless support, CNCF standard |
| Fallback CLI | cosign | KMS support, attestations, advanced features |
| Signature storage | OCI annotations | Simpler than separate artifacts |
| Bundle format | Sigstore Bundle | Industry standard, includes all verification materials |
| SBOM tool | Syft | SPDX support, active maintenance, fast |
| Config location | `artifacts.signing/verification` | Groups with existing OCI config |
| Verification hook | Inside OCIClient.pull() | Cannot be bypassed |

## Unknowns Resolved

| Unknown | Resolution |
|---------|------------|
| Where to add verification in pull() | After `_fetch_from_registry()`, before `_deserialize_artifacts()` |
| How to store signatures | OCI manifest annotations |
| Per-environment policies | `artifacts.verification.environments.{env}.enforcement` |
| Auth for signing | Reuse OCIClient credentials |
| Offline verification | Bundle contains all materials, no network needed |

## OpenTelemetry Trace Specification (SC-007)

### Span Naming Convention

All spans follow the pattern: `floe.oci.{operation}`

| Operation | Span Name | Description |
|-----------|-----------|-------------|
| Signing | `floe.oci.sign` | Root span for signing operation |
| OIDC token | `floe.oci.sign.oidc_token` | OIDC token acquisition |
| Fulcio cert | `floe.oci.sign.fulcio` | Certificate issuance |
| Rekor log | `floe.oci.sign.rekor` | Transparency log entry |
| Verification | `floe.oci.verify` | Root span for verification |
| Policy check | `floe.oci.verify.policy` | Policy evaluation |
| Bundle parse | `floe.oci.verify.bundle` | Sigstore bundle parsing |

### Span Attributes

**Common attributes (all spans):**

| Attribute | Type | Description |
|-----------|------|-------------|
| `floe.artifact.ref` | string | Full OCI artifact reference |
| `floe.artifact.digest` | string | SHA256 digest |
| `floe.signing.mode` | string | "keyless" or "key-based" |

**Signing-specific:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `floe.signing.issuer` | string | OIDC issuer URL |
| `floe.signing.subject` | string | Certificate subject |
| `floe.signing.rekor_index` | int | Rekor log index |

**Verification-specific:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `floe.verification.enforcement` | string | "enforce", "warn", "off" |
| `floe.verification.status` | string | SignatureStatus value |
| `floe.verification.environment` | string | Environment name if set |

### Error Recording

Errors are recorded with:
- `otel.status_code = ERROR`
- `otel.status_description = <error message>`
- Exception recorded via `span.record_exception()`

### Example Trace

```
floe.oci.sign (3.2s)
├── floe.oci.sign.oidc_token (0.5s)
├── floe.oci.sign.fulcio (1.2s)
├── floe.oci.sign.rekor (1.0s)
└── floe.oci.client.push_annotations (0.5s)

floe.oci.verify (1.1s)
├── floe.oci.verify.bundle (0.1s)
├── floe.oci.verify.policy (0.2s)
└── floe.oci.verify.rekor (0.8s)
```
