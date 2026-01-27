# Data Model: Artifact Signing

**Feature**: Epic 8B - Artifact Signing
**Date**: 2026-01-27

## Entity Overview

```
┌─────────────────────┐     ┌────────────────────────┐
│   SigningConfig     │     │  VerificationPolicy    │
│  (manifest.yaml)    │     │   (manifest.yaml)      │
└─────────┬───────────┘     └──────────┬─────────────┘
          │                            │
          │ configures                 │ configures
          ▼                            ▼
┌─────────────────────┐     ┌────────────────────────┐
│   SigningClient     │     │  VerificationClient    │
│  (runtime service)  │     │   (runtime service)    │
└─────────┬───────────┘     └──────────┬─────────────┘
          │                            │
          │ produces                   │ validates
          ▼                            ▼
┌─────────────────────────────────────────────────────┐
│              SignatureMetadata                       │
│         (OCI artifact annotations)                   │
└─────────────────────────────────────────────────────┘
```

## Entities

### 1. SigningConfig

**Purpose**: Configuration for artifact signing operations
**Location**: `manifest.yaml` at `artifacts.signing`
**Persistence**: YAML file (immutable after platform compile)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | `Literal["keyless", "key-based"]` | Yes | Signing method |
| `oidc_issuer` | `HttpUrl \| None` | Keyless only | OIDC provider URL |
| `rekor_url` | `HttpUrl` | No | Rekor instance (default: production) |
| `private_key_ref` | `SecretReference \| None` | Key-based only | Reference to private key |
| `fulcio_url` | `HttpUrl` | No | Fulcio CA instance (default: production) |

**Validation Rules**:
- If `mode == "keyless"`: `oidc_issuer` is required, `private_key_ref` must be None
- If `mode == "key-based"`: `private_key_ref` is required
- URLs must be valid HTTP/HTTPS URLs

**State Transitions**: N/A (configuration, not stateful)

### 2. VerificationPolicy

**Purpose**: Policy for verifying artifact signatures
**Location**: `manifest.yaml` at `artifacts.verification`
**Persistence**: YAML file (immutable after platform compile)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | `bool` | Yes | Enable/disable verification |
| `enforcement` | `Literal["enforce", "warn", "off"]` | Yes | Enforcement level |
| `trusted_issuers` | `list[TrustedIssuer]` | If enabled | List of trusted signers |
| `require_rekor` | `bool` | No | Require transparency log entry |
| `require_sbom` | `bool` | No | Require SBOM attestation |
| `public_key_ref` | `SecretReference \| None` | Key-based only | Reference to public key |
| `environments` | `dict[str, EnvironmentPolicy]` | No | Per-environment overrides |
| `grace_period_days` | `int` | No | Days to accept expired certs during rotation (default: 7) |

**Nested: TrustedIssuer**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issuer` | `HttpUrl` | Yes | OIDC issuer URL |
| `subject` | `str` | Yes | Expected certificate subject |
| `subject_regex` | `str \| None` | No | Regex pattern for subject matching |

**Nested: EnvironmentPolicy**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enforcement` | `Literal["enforce", "warn", "off"]` | Yes | Override enforcement level |
| `require_sbom` | `bool \| None` | No | Override SBOM requirement |

**Validation Rules**:
- If `enabled == True`: at least one `trusted_issuers` OR `public_key_ref` required
- `subject` and `subject_regex` are mutually exclusive
- Environment names must match known environments (dev, staging, prod)

### 3. SignatureMetadata

**Purpose**: Metadata stored in OCI artifact annotations after signing
**Location**: OCI manifest annotations
**Persistence**: OCI registry (immutable once pushed)

| Field | Type | Description |
|-------|------|-------------|
| `bundle` | `str` | Base64-encoded Sigstore bundle JSON |
| `mode` | `Literal["keyless", "key-based"]` | Signing mode used |
| `issuer` | `str \| None` | OIDC issuer (keyless only) |
| `subject` | `str` | Certificate subject / signer identity |
| `signed_at` | `datetime` | Signing timestamp (ISO 8601) |
| `rekor_log_index` | `int \| None` | Rekor transparency log index |
| `certificate_fingerprint` | `str` | SHA256 of signing certificate |

**Annotation Keys**:
- `dev.floe.signature.bundle` → `bundle`
- `dev.floe.signature.mode` → `mode`
- `dev.floe.signature.issuer` → `issuer`
- `dev.floe.signature.subject` → `subject`
- `dev.floe.signature.signed-at` → `signed_at`
- `dev.floe.signature.rekor-index` → `rekor_log_index`
- `dev.floe.signature.cert-fingerprint` → `certificate_fingerprint`

### 4. VerificationResult

**Purpose**: Result of signature verification operation
**Location**: In-memory (returned from VerificationClient)
**Persistence**: Logged for audit, not persisted

#### SignatureStatus Enum

```python
from enum import Enum

class SignatureStatus(str, Enum):
    """Status of artifact signature verification."""
    VALID = "valid"        # Signature verified successfully
    INVALID = "invalid"    # Signature exists but verification failed
    UNSIGNED = "unsigned"  # No signature present on artifact
    UNKNOWN = "unknown"    # Unable to determine status (e.g., network error)
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | `SignatureStatus` | VALID, INVALID, UNSIGNED, UNKNOWN |
| `signer_identity` | `str \| None` | Verified signer identity |
| `issuer` | `str \| None` | OIDC issuer if keyless |
| `verified_at` | `datetime` | Verification timestamp |
| `rekor_verified` | `bool` | Transparency log verified |
| `certificate_chain` | `list[str]` | Certificate chain (PEM) |
| `failure_reason` | `str \| None` | Reason if verification failed |

### 5. AttestationManifest

**Purpose**: SBOM or provenance attestation attached to artifact
**Location**: OCI registry (as in-toto attestation via cosign)
**Persistence**: OCI registry (immutable once pushed)

| Field | Type | Description |
|-------|------|-------------|
| `predicate_type` | `str` | Attestation type (e.g., `https://spdx.dev/Document`) |
| `predicate` | `dict` | Attestation payload (SBOM content) |
| `subject` | `list[Subject]` | Artifacts this attestation covers |

**Nested: Subject**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Artifact reference |
| `digest` | `dict[str, str]` | Digest map (sha256 -> value) |

### 6. SigningAuditEvent

**Purpose**: Structured audit log for signing operations
**Location**: Emitted via structlog with trace context
**Persistence**: Log aggregation system (Loki, CloudWatch, etc.)

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | `Literal["signing"]` | Event type discriminator |
| `artifact_ref` | `str` | Full OCI artifact reference |
| `artifact_digest` | `str` | SHA256 digest of artifact |
| `signing_mode` | `Literal["keyless", "key-based"]` | Mode used |
| `signer_identity` | `str` | Certificate subject / signer ID |
| `issuer` | `str \| None` | OIDC issuer (keyless only) |
| `rekor_log_index` | `int \| None` | Transparency log entry |
| `timestamp` | `datetime` | Operation timestamp (ISO 8601) |
| `trace_id` | `str` | W3C trace context ID |
| `span_id` | `str` | W3C span ID |
| `success` | `bool` | Operation succeeded |
| `error` | `str \| None` | Error message if failed |

### 7. VerificationAuditEvent

**Purpose**: Structured audit log for verification operations
**Location**: Emitted via structlog with trace context
**Persistence**: Log aggregation system

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | `Literal["verification"]` | Event type discriminator |
| `artifact_ref` | `str` | Full OCI artifact reference |
| `artifact_digest` | `str` | SHA256 digest of artifact |
| `policy_enforcement` | `Literal["enforce", "warn", "off"]` | Active enforcement level |
| `environment` | `str \| None` | Environment context if set |
| `expected_issuers` | `list[str]` | Configured trusted issuers |
| `actual_issuer` | `str \| None` | Actual signer issuer |
| `actual_subject` | `str \| None` | Actual signer identity |
| `signature_status` | `SignatureStatus` | Verification result status |
| `rekor_verified` | `bool` | Transparency log checked |
| `timestamp` | `datetime` | Operation timestamp (ISO 8601) |
| `trace_id` | `str` | W3C trace context ID |
| `span_id` | `str` | W3C span ID |
| `success` | `bool` | Verification passed |
| `failure_reason` | `str \| None` | Reason if verification failed |

### 8. VerificationBundle (FR-015)

**Purpose**: Offline bundle for air-gapped verification
**Location**: Exported file or embedded in artifact
**Persistence**: File system or OCI registry

| Field | Type | Description |
|-------|------|-------------|
| `version` | `Literal["1.0"]` | Bundle format version |
| `artifact_digest` | `str` | SHA256 of signed artifact |
| `sigstore_bundle` | `dict` | Full Sigstore bundle JSON |
| `certificate_chain` | `list[str]` | PEM-encoded cert chain |
| `rekor_entry` | `dict \| None` | Rekor log entry (if available) |
| `created_at` | `datetime` | Bundle creation timestamp |

## Entity Relationships

```
SigningConfig (1) ──configures──> SigningClient (1)
                                        │
                                        │ produces
                                        ▼
                                 SignatureMetadata (1)
                                        │
                                        │ stored in
                                        ▼
                                  OCI Artifact (1)
                                        │
                                        │ verified by
                                        ▼
VerificationPolicy (1) ──configures──> VerificationClient (1)
                                        │
                                        │ produces
                                        ▼
                                 VerificationResult (1)
```

## Pydantic Model Definitions

### SigningConfig

```python
from pydantic import BaseModel, ConfigDict, HttpUrl, model_validator
from typing import Literal

class SigningConfig(BaseModel):
    """Configuration for artifact signing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["keyless", "key-based"]
    oidc_issuer: HttpUrl | None = None
    rekor_url: HttpUrl = HttpUrl("https://rekor.sigstore.io")
    fulcio_url: HttpUrl = HttpUrl("https://fulcio.sigstore.dev")
    private_key_ref: SecretReference | None = None

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> "SigningConfig":
        if self.mode == "keyless" and not self.oidc_issuer:
            raise ValueError("oidc_issuer required for keyless mode")
        if self.mode == "key-based" and not self.private_key_ref:
            raise ValueError("private_key_ref required for key-based mode")
        return self
```

### VerificationPolicy

```python
class TrustedIssuer(BaseModel):
    """A trusted OIDC issuer for signature verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issuer: HttpUrl
    subject: str | None = None
    subject_regex: str | None = None

    @model_validator(mode="after")
    def validate_subject(self) -> "TrustedIssuer":
        if not self.subject and not self.subject_regex:
            raise ValueError("Either subject or subject_regex required")
        if self.subject and self.subject_regex:
            raise ValueError("subject and subject_regex are mutually exclusive")
        return self

class EnvironmentPolicy(BaseModel):
    """Per-environment verification policy override."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enforcement: Literal["enforce", "warn", "off"]
    require_sbom: bool | None = None

class VerificationPolicy(BaseModel):
    """Policy for verifying artifact signatures."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    enforcement: Literal["enforce", "warn", "off"] = "warn"
    trusted_issuers: list[TrustedIssuer] = []
    require_rekor: bool = True
    require_sbom: bool = False
    public_key_ref: SecretReference | None = None
    environments: dict[str, EnvironmentPolicy] = {}
    grace_period_days: int = 7  # FR-012: Accept expired certs during rotation

    def get_enforcement_for_env(self, env: str) -> Literal["enforce", "warn", "off"]:
        """Get effective enforcement level for an environment."""
        if env in self.environments:
            return self.environments[env].enforcement
        return self.enforcement

    def is_within_grace_period(self, cert_expired_at: datetime, now: datetime) -> bool:
        """Check if expired cert is still within rotation grace period (FR-012)."""
        from datetime import timedelta
        grace_end = cert_expired_at + timedelta(days=self.grace_period_days)
        return now <= grace_end
```

### SignatureMetadata

```python
from datetime import datetime

class SignatureMetadata(BaseModel):
    """Signature metadata stored in OCI annotations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle: str  # Base64-encoded Sigstore bundle
    mode: Literal["keyless", "key-based"]
    issuer: str | None = None
    subject: str
    signed_at: datetime
    rekor_log_index: int | None = None
    certificate_fingerprint: str

    def to_annotations(self) -> dict[str, str]:
        """Convert to OCI annotation dict."""
        annotations = {
            "dev.floe.signature.bundle": self.bundle,
            "dev.floe.signature.mode": self.mode,
            "dev.floe.signature.subject": self.subject,
            "dev.floe.signature.signed-at": self.signed_at.isoformat(),
            "dev.floe.signature.cert-fingerprint": self.certificate_fingerprint,
        }
        if self.issuer:
            annotations["dev.floe.signature.issuer"] = self.issuer
        if self.rekor_log_index is not None:
            annotations["dev.floe.signature.rekor-index"] = str(self.rekor_log_index)
        return annotations

    @classmethod
    def from_annotations(cls, annotations: dict[str, str]) -> "SignatureMetadata | None":
        """Parse from OCI annotations, returns None if not signed."""
        bundle = annotations.get("dev.floe.signature.bundle")
        if not bundle:
            return None
        return cls(
            bundle=bundle,
            mode=annotations["dev.floe.signature.mode"],
            issuer=annotations.get("dev.floe.signature.issuer"),
            subject=annotations["dev.floe.signature.subject"],
            signed_at=datetime.fromisoformat(annotations["dev.floe.signature.signed-at"]),
            rekor_log_index=int(annotations["dev.floe.signature.rekor-index"])
                if "dev.floe.signature.rekor-index" in annotations else None,
            certificate_fingerprint=annotations["dev.floe.signature.cert-fingerprint"],
        )
```

## Integration with Existing Schemas

### Extension to ArtifactManifest

The existing `ArtifactManifest` in `schemas/oci.py` already has:
- `signature_status: SignatureStatus` (currently hardcoded to UNSIGNED)
- `annotations: dict[str, str]`

**Changes needed**:
1. Parse `SignatureMetadata` from annotations
2. Set `signature_status` based on verification result
3. Add `signature_metadata: SignatureMetadata | None` property

### Extension to RegistryConfig

Add optional signing/verification config:

```python
class RegistryConfig(BaseModel):
    # ... existing fields ...
    signing: SigningConfig | None = None
    verification: VerificationPolicy | None = None
```

## Schema Versioning

| Schema | Version | Breaking Change |
|--------|---------|-----------------|
| SigningConfig | 1.0.0 | New schema |
| VerificationPolicy | 1.0.0 | New schema |
| SignatureMetadata | 1.0.0 | New schema |
| RegistryConfig | 1.1.0 | Additive (new optional fields) |
| ArtifactManifest | 1.1.0 | Additive (new computed property) |
