# Implementation Plan: Artifact Signing

**Branch**: `8b-artifact-signing` | **Date**: 2026-01-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/8b-artifact-signing/spec.md`

## Summary

Implement cryptographic signing and verification for CompiledArtifacts using Sigstore/cosign. Supports two modes: **keyless signing** (OIDC-based, default for CI/CD) and **key-based signing** (for air-gapped environments). Verification is integrated into `OCIClient.pull()` to ensure only trusted artifacts are deployed. Includes SBOM generation and attestation support.

## Technical Context

**Language/Version**: Python 3.11+ (sigstore-python requires 3.10+)
**Primary Dependencies**:
- sigstore >= 3.0.0 (Python SDK for Sigstore keyless signing)
- cosign CLI >= 2.0.0 (via subprocess for advanced operations)
- syft CLI (SBOM generation)
**Storage**: OCI registries (signatures stored as cosign convention artifacts)
**Testing**: pytest with Kind cluster for integration tests
**Target Platform**: Linux (CI/CD), macOS (development)
**Project Type**: Python package extension (floe-core)
**Performance Goals**: < 5s signing time, < 2s verification time
**Constraints**: Must work offline for key-based mode; keyless requires OIDC
**Scale/Scope**: Integrates with Epic 8A OCIClient, consumed by Epic 8C (Promotion) and Epic 9A (K8s Deployment)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core/oci/ for signing modules)
- [x] No SQL parsing/validation in Python (N/A - not SQL related)
- [x] No orchestration logic outside floe-dagster (N/A - signing is infrastructure)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (N/A - signing is core, not pluggable)
- [x] Plugin registered via entry point (N/A - not a plugin)
- [x] PluginMetadata declares name, version, floe_api_version (N/A)

*Note: Signing is intentionally NOT a plugin - it's core security infrastructure that must not be swapped out.*

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (signing enforces artifact authenticity)
- [x] Pluggable choices documented in manifest.yaml (signing mode is configurable)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (signing operates on CompiledArtifacts)
- [x] Pydantic v2 models for all schemas (SigningConfig, VerificationPolicy)
- [x] Contract changes follow versioning rules (new schemas, no breaking changes)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (with Harbor registry)
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (all configs validated)
- [x] Credentials use SecretStr (private key references)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml -> signing behavior)
- [x] Layer ownership respected (Platform Team configures signing policies)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (for signing/verification operations)
- [x] OpenLineage events for data transformations (N/A - not data transformation)

## Integration Design

### Entry Point Integration
- [x] Feature reachable from: CLI (`floe artifact sign/verify/sbom`) and OCIClient API
- [x] Integration point: `packages/floe-core/src/floe_core/cli/artifact/` for CLI, `packages/floe-core/src/floe_core/oci/` for API
- [x] Wiring task needed: Yes - add sign/verify/sbom commands to artifact group, add verification hook to OCIClient.pull()

### Dependency Integration
| This Feature Uses | From Package | Integration Point |
|-------------------|--------------|-------------------|
| OCIClient | floe-core/oci | Direct import, add verification to pull() |
| CompiledArtifacts | floe-core/schemas | Operated on (signed/verified) |
| RegistryConfig | floe-core/schemas/oci | Reuse for authentication |
| CLI framework | floe-core/cli | Click commands, error handling |
| OCI errors | floe-core/oci/errors | Extend with SignatureVerificationError |

### Produces for Others
| Output | Consumers | Contract |
|--------|-----------|----------|
| SigningConfig schema | manifest.yaml, floe platform compile | Pydantic model at artifacts.signing |
| VerificationPolicy schema | manifest.yaml, OCIClient | Pydantic model at artifacts.verification |
| SignatureVerificationError | OCIClient consumers, CLI | Exception class in oci/errors.py |
| Verification hook in pull() | Epic 8C, Epic 9A, CLI | Automatic verification when policy enabled |

### Cleanup Required
- [ ] No old code to remove (new feature, not refactoring)
- [ ] No old tests to remove
- [ ] Update docs/architecture/adr/0041-artifact-signing-verification.md with implementation notes

## Project Structure

### Documentation (this feature)

```text
specs/8b-artifact-signing/
├── plan.md              # This file
├── research.md          # Phase 0: sigstore-python API, cosign patterns
├── data-model.md        # Phase 1: SigningConfig, VerificationPolicy schemas
├── quickstart.md        # Phase 1: How to sign/verify artifacts
├── contracts/           # Phase 1: Pydantic schemas as JSON Schema
│   ├── signing-config.json
│   └── verification-policy.json
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── oci/
│   ├── client.py            # MODIFY: Add verification hook to pull()
│   ├── signing.py           # NEW: SigningClient class
│   ├── verification.py      # NEW: VerificationClient class
│   ├── attestation.py       # NEW: SBOM/attestation handling
│   └── errors.py            # MODIFY: Add SignatureVerificationError
├── schemas/
│   ├── oci.py               # MODIFY: Add SigningConfig, VerificationPolicy
│   └── signing.py           # NEW: Signing-specific schemas
└── cli/
    └── artifact/
        ├── __init__.py      # MODIFY: Register sign, verify, sbom commands
        ├── push.py          # MODIFY: Add --sign flag
        ├── sign.py          # NEW: floe artifact sign command
        ├── verify.py        # NEW: floe artifact verify command
        └── sbom.py          # NEW: floe artifact sbom command

packages/floe-core/tests/
├── unit/
│   ├── oci/
│   │   ├── test_signing.py      # NEW: Unit tests for signing
│   │   └── test_verification.py # NEW: Unit tests for verification
│   └── cli/
│       ├── test_artifact_sign.py   # NEW: CLI unit tests
│       └── test_artifact_verify.py # NEW: CLI unit tests
└── integration/
    └── oci/
        ├── test_signing_e2e.py      # NEW: E2E signing tests with Harbor
        └── test_verification_e2e.py # NEW: E2E verification tests
```

**Structure Decision**: Extension of existing floe-core package. New modules added to `oci/` for signing logic, new commands added to `cli/artifact/` for CLI interface. Follows established patterns from Epic 8A OCI Client.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| External CLI (cosign, syft) | Sigstore ecosystem uses these | Pure Python doesn't support all features (KMS, HSM) |
| subprocess calls | cosign CLI for advanced features | sigstore-python covers 80%, cosign needed for KMS/attestations |

## Phase Artifacts

### Phase 0: Research (see research.md)
- sigstore-python API patterns
- cosign CLI integration patterns
- SBOM generation with syft
- OCI registry signature storage conventions

### Phase 1: Design (see data-model.md, contracts/)
- SigningConfig schema
- VerificationPolicy schema
- SignatureMetadata annotation schema
- AttestationManifest schema

### Phase 2: Tasks (see tasks.md - generated by /speckit.tasks)
- Implementation tasks broken down by component
