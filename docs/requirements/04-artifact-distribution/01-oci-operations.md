# REQ-300 to REQ-315: OCI Operations and Schema Versioning

**Domain**: Artifact Distribution
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines OCI artifact operations (push, pull, list, delete, validate) and schema versioning strategy for platform artifacts. These operations form the foundation for artifact distribution.

**Key Principle**: Immutable, versioned artifacts stored in OCI registries (ADR-0016)

## Requirements

### REQ-300: OCI Client Implementation **[New]**

**Requirement**: System MUST implement OCI client using ORAS library with support for push, pull, list, delete operations for OCI artifacts.

**Rationale**: ORAS is the standard library for OCI artifact storage. Avoids reinventing container image protocol.

**Acceptance Criteria**:
- [ ] OCI client wraps ORAS library functionality
- [ ] Supports push operation with artifact metadata and layers
- [ ] Supports pull operation with signature verification integration point
- [ ] Supports list operation to enumerate artifacts in registry
- [ ] Supports delete operation with retention policy checks
- [ ] Handles authentication (AWS IRSA, Azure Managed Identity, token-based, basic auth)
- [ ] Returns structured responses (pull success, push digest, list results)
- [ ] Clear error messages for registry operations

**Enforcement**:
- OCI client unit tests with ORAS mock
- Registry integration tests with real OCI registries
- Authentication tests for each auth method

**Constraints**:
- MUST use ORAS >= 1.0.0
- MUST support all registry types (ECR, ACR, GAR, GHCR, Harbor)
- MUST NOT hardcode registry credentials
- MUST handle partial failures gracefully

**Test Coverage**: `tests/unit/test_oci_client.py`

**Traceability**:
- oci-registry-requirements.md lines 1-100
- ADR-0016 (Platform Enforcement Architecture)

---

### REQ-301: OCI Push Operation **[New]**

**Requirement**: System MUST implement `floe platform publish <version>` command that pushes platform artifact to OCI registry with manifest and layer organization.

**Rationale**: Enables platform teams to distribute immutable versions of platform configuration.

**Acceptance Criteria**:
- [ ] `floe platform publish <version>` compiles and pushes artifact
- [ ] Artifact includes manifest.json with metadata
- [ ] Artifact includes policies/ layer with governance rules
- [ ] Artifact includes catalog/ layer with namespace config
- [ ] Artifact includes architecture/ layer with naming rules
- [ ] Manifest includes digest, created timestamp, version
- [ ] Destination: `oci://registry/floe-platform:<version>`
- [ ] Return push result with digest and size
- [ ] Failed push rolls back gracefully

**Enforcement**:
- Push workflow tests
- Manifest generation tests
- Layer organization tests
- Registry integration tests

**Constraints**:
- MUST calculate and include digest
- MUST validate artifact structure before push
- MUST include all required layers
- FORBIDDEN to push incomplete artifacts

**Example**:
```bash
$ floe platform publish v1.2.3
Publishing to oci://registry.example.com/floe-platform:v1.2.3
  ✓ Uploading manifest.json (2.1 KB)
  ✓ Uploading policies/ (4.5 KB)
  ✓ Uploading catalog/ (1.2 KB)
  ✓ Uploading architecture/ (0.8 KB)
Published: oci://registry.example.com/floe-platform:v1.2.3
Digest: sha256:abc123def456...
```

**Test Coverage**: `tests/integration/test_platform_publish.py`

**Traceability**:
- platform-artifacts.md lines 140-197
- oci-registry-requirements.md

---

### REQ-302: OCI Pull Operation **[New]**

**Requirement**: System MUST implement `floe init --platform=<version>` command that pulls platform artifact from OCI registry and caches it locally.

**Rationale**: Enables data teams to initialize projects with platform standards.

**Acceptance Criteria**:
- [ ] `floe init --platform=v1.2.3` pulls artifact
- [ ] Destination: `oci://registry.example.com/floe-platform:v1.2.3`
- [ ] Cache artifacts at `.floe/platform/<version>/`
- [ ] Return pull result with layers extracted
- [ ] Extract manifest.json, policies/, catalog/, architecture/ layers
- [ ] Cache validation: verify digest matches
- [ ] Version constraints supported: exact (v1.2.3), patch (v1.2.*), minor (v1.*)
- [ ] Clear error messages for pull failures

**Enforcement**:
- Pull workflow tests
- Cache extraction tests
- Version constraint tests
- Registry integration tests

**Constraints**:
- MUST verify artifact digest matches expected
- MUST cache artifacts to avoid repeated downloads
- FORBIDDEN to trust unsigned artifacts (unless signing disabled)
- MUST support signature verification integration

**Example**:
```bash
$ floe init --platform=v1.2.3
Pulling platform artifacts from oci://registry.example.com/floe-platform:v1.2.3
  ✓ Verifying signature
  ✓ Downloading artifacts (8.6 KB)
Platform: acme-data-platform v1.2.3
  Compute: duckdb
  Orchestrator: dagster
  Catalog: polaris
```

**Test Coverage**: `tests/integration/test_platform_pull.py`

**Traceability**:
- platform-artifacts.md lines 199-239
- oci-registry-requirements.md

---

### REQ-303: Artifact Caching **[New]**

**Requirement**: System MUST implement local artifact caching with TTL and immutable tag handling to reduce registry load.

**Rationale**: Repeated artifact pulls are expensive; immutable tags (semver versions) never change, justifying indefinite cache.

**Acceptance Criteria**:
- [ ] Cache location: `.floe/platform/<version>/`
- [ ] Cache validation: verify digest matches
- [ ] TTL-based eviction for mutable tags (latest, dev)
- [ ] Immutable cache (never re-fetch) for semver tags (v1.2.3)
- [ ] SHA-based immutable cache (sha256:abc123)
- [ ] Cache hits logged with metadata
- [ ] Cache misses trigger registry pull
- [ ] Cache clear command: `floe platform cache clear`
- [ ] Force re-pull: `floe init --platform=v1.2.3 --force`

**Enforcement**:
- Cache hit/miss tests
- TTL eviction tests
- Immutable tag tests
- Cache validation tests

**Constraints**:
- MUST verify digest before using cached artifact
- MUST NOT use stale cached data
- FORBIDDEN to cache unsigned artifacts if verification enabled
- MUST support cache size limits (default 10GB)

**Configuration**:
```yaml
# .floe/cache.yaml
cache:
  enabled: true
  local_path: /var/cache/floe/oci
  ttl_hours: 24
  max_size_gb: 10
  immutable_tags: true  # v1.2.3 never re-fetched
```

**Test Coverage**: `tests/unit/test_artifact_caching.py`

**Traceability**:
- oci-registry-requirements.md lines 417-439
- platform-artifacts.md lines 241-267

---

### REQ-304: OCI List Operation **[New]**

**Requirement**: System MUST implement `floe platform list` command to enumerate available platform artifacts in registry with version information.

**Rationale**: Enables platform teams and data teams to discover available versions.

**Acceptance Criteria**:
- [ ] `floe platform list` enumerates all tagged versions
- [ ] Output includes version, created date, digest, size
- [ ] Filter by version pattern: `--filter=v1.2.*`
- [ ] Sort by version or date: `--sort=version|date`
- [ ] Limit results: `--limit=10`
- [ ] JSON output for programmatic use: `--format=json`
- [ ] Default to human-readable table format

**Enforcement**:
- List workflow tests
- Filter/sort tests
- Format tests
- Registry integration tests

**Constraints**:
- MUST list all tags in registry
- MUST include manifest digest
- MUST support filtering by pattern

**Example**:
```bash
$ floe platform list --filter=v1.2.*
Version    Created              Digest                Size
v1.2.3     2024-01-15 10:30:00  sha256:abc123...      8.6 KB
v1.2.2     2024-01-10 14:45:00  sha256:def456...      7.2 KB
v1.2.1     2024-01-05 09:15:00  sha256:ghi789...      6.8 KB
```

**Test Coverage**: `tests/integration/test_platform_list.py`

**Traceability**:
- oci-registry-requirements.md

---

### REQ-305: OCI Delete Operation **[New]**

**Requirement**: System MUST implement `floe platform delete <version>` command to remove platform artifacts from registry with retention policy enforcement.

**Rationale**: Enables cleanup of obsolete versions and cost control.

**Acceptance Criteria**:
- [ ] `floe platform delete <version>` removes artifact
- [ ] Confirm before deletion: `--confirm` flag
- [ ] Respects retention policy: cannot delete protected versions
- [ ] Protected versions: latest major, latest minor, last 3 versions
- [ ] Cascade delete associated signatures
- [ ] Return deletion status and freed space
- [ ] Log audit trail of deletion

**Enforcement**:
- Delete workflow tests
- Retention policy tests
- Cascade deletion tests
- Audit logging tests

**Constraints**:
- MUST NOT delete protected versions
- MUST require confirmation (or --confirm flag)
- MUST delete associated signatures
- FORBIDDEN to delete while in-use

**Example**:
```bash
$ floe platform delete v1.0.0
This action will delete v1.0.0 from oci://registry.example.com/floe-platform
This is not protected by retention policy.
Continue? (y/n): y
Deleting v1.0.0...
  ✓ Artifact deleted
  ✓ Signatures deleted
  ✓ Freed 6.2 KB
```

**Test Coverage**: `tests/integration/test_platform_delete.py`

**Traceability**:
- ADR-0040 (Artifact Immutability & GC)

---

### REQ-306: Artifact Format Specification **[New]**

**Requirement**: System MUST define platform artifact structure (manifest, layers, metadata) with JSON Schema for validation and IDE autocomplete.

**Rationale**: Enables consistent artifact creation and validation across tools.

**Acceptance Criteria**:
- [ ] Artifact root includes manifest.json
- [ ] Manifest includes: apiVersion, kind, metadata, plugins, specs
- [ ] Metadata includes: name, version, created, digest, owner, tags
- [ ] Layers: policies/, catalog/, architecture/
- [ ] JSON Schema for artifact validation
- [ ] JSON Schema includes type definitions for all fields
- [ ] Schema versioning: v1, v2, etc.
- [ ] Auto-generation of TypeScript types for IDE support
- [ ] Validation tool: `floe platform validate --file=artifact.tar`

**Enforcement**:
- Artifact validation tests
- Schema conformance tests
- IDE integration tests

**Constraints**:
- MUST follow JSON Schema specification
- MUST include all required fields
- MUST be backward compatible within major version

**Example Manifest**:
```json
{
  "apiVersion": "floe.dev/v1",
  "kind": "PlatformArtifact",
  "metadata": {
    "name": "acme-data-platform",
    "version": "1.2.3",
    "created": "2024-01-15T10:30:00Z",
    "digest": "sha256:abc123def456...",
    "owner": "data-platform-team",
    "tags": ["prod", "stable"]
  },
  "plugins": {
    "compute": "duckdb@1.0.0",
    "orchestrator": "dagster@1.5.0",
    "catalog": "polaris@1.2.0"
  }
}
```

**Test Coverage**: `tests/unit/test_artifact_schema.py`

**Traceability**:
- platform-artifacts.md lines 38-107
- data-contracts.md

---

### REQ-307: Multi-Registry Support **[New]**

**Requirement**: System MUST support pulling artifacts from multiple registries with failover strategy (primary, secondary, tertiary).

**Rationale**: Enables resilience when primary registry is unavailable.

**Acceptance Criteria**:
- [ ] Configuration supports multiple registry URIs
- [ ] Failover order: primary → secondary → tertiary
- [ ] Fallback to secondary only after primary fails (not for performance)
- [ ] Fallback to tertiary only after secondary fails
- [ ] Digest verification ensures artifact integrity across registries
- [ ] Clear logging of which registry succeeded
- [ ] Configuration example with multiple registries

**Enforcement**:
- Failover tests with simulated registry failures
- Digest verification tests
- Multi-registry integration tests

**Constraints**:
- MUST verify digest matches across all registries
- MUST NOT use secondary for performance optimization
- MUST fail-fast when primary available
- FORBIDDEN to mix artifacts from different registries for single version

**Configuration**:
```yaml
# platform-manifest.yaml
artifacts:
  registry:
    primaries:
      - uri: oci://primary.example.com/floe
    secondaries:
      - uri: oci://secondary.example.com/floe
    tertiaries:
      - uri: oci://tertiary.example.com/floe
```

**Test Coverage**: `tests/integration/test_multi_registry_failover.py`

**Traceability**:
- oci-registry-requirements.md

---

### REQ-308: Artifact Size and Bandwidth Tracking **[New]**

**Requirement**: System MUST track artifact sizes and bandwidth usage for cost monitoring and SLA compliance.

**Rationale**: Enables cost control and performance optimization.

**Acceptance Criteria**:
- [ ] Metrics tracked: artifact size (total, per-layer), download bandwidth
- [ ] Metrics include: layer breakdown, compression ratio
- [ ] Bandwidth tracking per registry operation (push, pull)
- [ ] Cost estimation: GB-month, monthly transfer estimate
- [ ] Command: `floe platform stats --version=v1.2.3`
- [ ] Metrics exported to Prometheus format
- [ ] Billing alerts configurable

**Enforcement**:
- Metrics collection tests
- Export format tests
- Alert threshold tests

**Constraints**:
- MUST track actual bytes, not estimated
- MUST support compression ratio tracking
- MUST be accurate for cost modeling

**Example**:
```bash
$ floe platform stats --version=v1.2.3
Artifact Size
  manifest.json: 2.1 KB (uncompressed)
  policies/: 4.5 KB (uncompressed) → 1.2 KB (compressed, 73% reduction)
  catalog/: 1.2 KB (uncompressed) → 0.8 KB (compressed, 33% reduction)
  architecture/: 0.8 KB (uncompressed) → 0.6 KB (compressed, 25% reduction)
  Total: 8.6 KB (uncompressed) → 3.6 KB (compressed, 58% reduction)

Monthly Projection (based on daily pulls: 50)
  Total Transfer: 180 MB/month
  Estimated Cost (ECR: $0.09/GB): $0.02/month
```

**Test Coverage**: `tests/unit/test_artifact_metrics.py`

**Traceability**:
- ADR-0016 (Platform Enforcement Architecture)

---

### REQ-309: Content-Addressable Artifacts **[New]**

**Requirement**: System MUST use SHA256 content-addressable digests for artifacts, enabling automatic integrity verification and deduplication.

**Rationale**: Content addressing guarantees artifact integrity and enables efficient storage.

**Acceptance Criteria**:
- [ ] Every artifact assigned SHA256 digest
- [ ] Digest calculated from artifact contents
- [ ] Digest immutable: same contents = same digest
- [ ] Digest verification on pull: calculated vs. expected
- [ ] Deduplication: identical artifact content shares storage
- [ ] Digest in artifact URI: `oci://registry/floe-platform@sha256:abc123`
- [ ] Tag-to-digest resolution: `v1.2.3` → `sha256:abc123`
- [ ] Digest pinning: data teams can pin to specific digest

**Enforcement**:
- Digest calculation tests
- Integrity verification tests
- Deduplication tests

**Constraints**:
- MUST use SHA256 (not MD5, SHA1)
- MUST verify digest on every pull
- FORBIDDEN to trust unverified artifacts
- MUST support digest-based artifact references

**Example**:
```bash
# Pull by tag (tag can change)
$ floe init --platform=v1.2.3

# Pull by digest (immutable)
$ floe init --platform=oci://registry.example.com/floe-platform@sha256:abc123def456...
```

**Test Coverage**: `tests/unit/test_content_addressing.py`

**Traceability**:
- ADR-0016 (Platform Enforcement Architecture)
- oci-registry-requirements.md lines 10-24

---

### REQ-310: Artifact Manifest Versioning **[New]**

**Requirement**: System MUST track artifact manifest format version (v1, v2, etc.) enabling schema evolution and backward compatibility.

**Rationale**: Enables schema to evolve while maintaining compatibility with older clients.

**Acceptance Criteria**:
- [ ] Manifest includes `apiVersion: floe.dev/v1` field
- [ ] Version follows semver: MAJOR.MINOR.PATCH
- [ ] MAJOR version change: breaking schema changes
- [ ] MINOR version change: backward-compatible additions
- [ ] PATCH version change: documentation, bug fixes
- [ ] Compatibility: clients support current version ± 2 patch versions
- [ ] Clear error message when schema version unsupported
- [ ] Migration tool: `floe platform migrate-schema v1 → v2`

**Enforcement**:
- Schema versioning tests
- Version parsing tests
- Compatibility tests
- Migration tests

**Constraints**:
- MUST follow semver
- MUST maintain 3-version compatibility window
- MUST reject incompatible versions

**Configuration**:
```yaml
# Current target state
apiVersion: floe.dev/v2.0.0

# Supported range
minApiVersion: v1.8.0  # 3 patch versions back from v2.0.0
maxApiVersion: v2.0.0  # current
```

**Test Coverage**: `tests/unit/test_manifest_versioning.py`

**Traceability**:
- pydantic-contracts.md (versioning section)
- ADR-0016 (Platform Enforcement Architecture)

---

### REQ-311: Schema MAJOR/MINOR/PATCH Semantics **[New]**

**Requirement**: System MUST define and enforce semantic versioning for artifact schemas with clear compatibility guarantees.

**Rationale**: Enables safe schema evolution and prevents breaking changes.

**Acceptance Criteria**:
- [ ] MAJOR (v1 → v2): Breaking changes allowed (schema incompatible)
- [ ] MINOR (v1.1 → v1.2): New optional fields, backward compatible
- [ ] PATCH (v1.0.1 → v1.0.2): Documentation, bug fixes, no schema change
- [ ] Client compatibility: supports current ± 1 minor version
- [ ] Server compatibility: requires clients within compatibility window
- [ ] Deprecation warning: 2 minor versions before removal
- [ ] Migration guide: provided for MAJOR version changes

**Enforcement**:
- Compatibility validation tests
- Version bump validation tests
- Deprecation warning tests

**Constraints**:
- MUST follow semver specification
- BREAKING changes forbidden in MINOR/PATCH
- ADDITIVE changes allowed in MINOR (not MAJOR)
- DOCUMENTATION-ONLY allowed in PATCH

**Example Compatibility Matrix**:
```
Client v1.2.0 compatible with:
  Schema v1.0.0 - YES (older patch)
  Schema v1.1.0 - YES (older minor)
  Schema v1.2.0 - YES (same)
  Schema v1.3.0 - YES (newer minor)
  Schema v2.0.0 - NO (breaking change)
```

**Test Coverage**: `tests/unit/test_schema_versioning.py`

**Traceability**:
- pydantic-contracts.md (versioning section)
- ADR-0016 (Platform Enforcement Architecture)

---

### REQ-312: OCI Layer Organization **[New]**

**Requirement**: System MUST organize artifact contents into logical OCI layers (manifest, policies, catalog, architecture) enabling granular updates and efficient caching.

**Rationale**: Layer organization enables caching only changed layers.

**Acceptance Criteria**:
- [ ] Layer 1: manifest.json (platform metadata)
- [ ] Layer 2: policies/ (governance, quality gates, classification)
- [ ] Layer 3: catalog/ (namespaces, schema registry)
- [ ] Layer 4: architecture/ (naming conventions, layer constraints)
- [ ] Each layer versioned independently
- [ ] Unchanged layers reused on subsequent pushes
- [ ] Layer sizes tracked for cost analysis
- [ ] Layer integrity verified per-layer

**Enforcement**:
- Layer organization tests
- Layer versioning tests
- Layer reuse tests
- Integrity verification tests

**Constraints**:
- MUST follow specified layer structure
- MUST NOT combine layers
- FORBIDDEN to skip layers

**Example OCI Structure**:
```
oci://registry.example.com/floe-platform:v1.2.3
├── manifest.json          (Layer 1: Metadata)
├── policies/              (Layer 2: Governance)
│   ├── classification.json
│   ├── access-control.json
│   └── quality-gates.json
├── catalog/               (Layer 3: Catalog Config)
│   ├── namespaces.json
│   └── schema-registry.json
└── architecture/          (Layer 4: Architecture Rules)
    ├── naming-rules.json
    └── layer-constraints.json
```

**Test Coverage**: `tests/unit/test_oci_layer_organization.py`

**Traceability**:
- platform-artifacts.md lines 38-107
- oci-registry-requirements.md

---

### REQ-313: Artifact Immutability Enforcement **[New]**

**Requirement**: System MUST prevent tag reassignment (immutable tags) once artifact is published, enabling safe version pinning.

**Rationale**: Immutable tags guarantee that `v1.2.3` always refers to the same artifact.

**Acceptance Criteria**:
- [ ] Semver tags (v1.2.3) immutable after push
- [ ] Attempt to re-push to existing tag returns error
- [ ] Overwrite prevention configurable per tag pattern
- [ ] Mutable tags allowed: `latest`, `dev`, `staging` (configurable)
- [ ] Registry-enforced: tag immutability via admission webhook
- [ ] Clear error message when attempting reassignment
- [ ] Audit log of reassignment attempts

**Enforcement**:
- Tag reassignment prevention tests
- Registry webhook tests
- Audit logging tests

**Constraints**:
- MUST prevent semver tag overwrite
- MUST allow mutable tag overwrite (with audit log)
- FORBIDDEN to silently ignore reassignment attempts

**Configuration**:
```yaml
# platform-manifest.yaml
artifacts:
  registry:
    immutable_tag_patterns:
      - "v*"            # Semver tags immutable
      - "release-*"     # Release tags immutable
    mutable_tag_patterns:
      - "latest"
      - "dev"
      - "staging"
```

**Test Coverage**: `tests/integration/test_tag_immutability.py`

**Traceability**:
- ADR-0040 (Artifact Immutability & GC)

---

### REQ-314: Artifact Provenance Metadata **[New]**

**Requirement**: System MUST embed provenance metadata (builder, build_id, build_timestamp, source_commit, signer) in artifact manifest.

**Rationale**: Enables audit trail and compliance verification.

**Acceptance Criteria**:
- [ ] Metadata fields: builder (user/CI), build_id (GitHub run ID), timestamp, commit (git hash), signer (cert identity)
- [ ] Builder tracked: `floe platform publish` by user or CI/CD system
- [ ] Build ID: GitHub Actions run ID, GitLab pipeline ID, etc.
- [ ] Build timestamp: ISO 8601 format (UTC)
- [ ] Source commit: git commit hash that triggered publish
- [ ] Signer: subject from signing certificate (for verification)
- [ ] Searchable: `floe platform list --filter=builder:ci-system`
- [ ] Audit trail queryable

**Enforcement**:
- Metadata capture tests
- Metadata validation tests
- Audit trail tests

**Constraints**:
- MUST capture builder at publish time
- MUST include source commit
- MUST be immutable after push
- FORBIDDEN to modify provenance after publication

**Example Provenance**:
```json
{
  "metadata": {
    "name": "acme-data-platform",
    "version": "1.2.3",
    "provenance": {
      "builder": "ci-system:github-actions",
      "build_id": "12345678-90ab-cdef",
      "build_timestamp": "2024-01-15T10:30:00Z",
      "source_commit": "abc123def456ghi789jkl",
      "signer": "CN=github-runner@acme.com"
    }
  }
}
```

**Test Coverage**: `tests/unit/test_artifact_provenance.py`

**Traceability**:
- ADR-0038 (Artifact Signing & Verification)
- platform-artifacts.md

---

### REQ-315: Artifact Discovery and Indexing **[New]**

**Requirement**: System MUST support searching and discovering platform artifacts by metadata (name, version, tags, plugins) without downloading each artifact.

**Rationale**: Enables efficient discovery without pulling all artifacts.

**Acceptance Criteria**:
- [ ] Search by name: `floe platform search --name=acme`
- [ ] Search by version: `floe platform search --version=1.2.*`
- [ ] Search by tags: `floe platform search --tags=prod,stable`
- [ ] Search by plugins: `floe platform search --compute=duckdb --orchestrator=dagster`
- [ ] List with metadata: version, created date, builder, plugins
- [ ] JSON output for programmatic use
- [ ] Caching of metadata index (TTL-based)
- [ ] Index refresh: `floe platform index --refresh`

**Enforcement**:
- Search functionality tests
- Metadata extraction tests
- Index caching tests
- Registry query tests

**Constraints**:
- MUST NOT require downloading full artifacts for discovery
- MUST support efficient filtering
- FORBIDDEN to hardcode artifact lists
- MUST support regex/wildcard patterns

**Example**:
```bash
$ floe platform search --compute=duckdb --orchestrator=dagster
Name                  Version  Created              Plugins
acme-data-platform    v1.2.3   2024-01-15 10:30:00  duckdb, dagster, polaris
acme-data-platform    v1.2.2   2024-01-10 14:45:00  duckdb, dagster, polaris
acme-data-platform    v1.1.0   2024-01-01 09:00:00  duckdb, dagster, polaris
```

**Test Coverage**: `tests/integration/test_artifact_discovery.py`

**Traceability**:
- oci-registry-requirements.md

---

## Domain Acceptance Criteria

OCI Operations and Schema Versioning (REQ-300 to REQ-315) is complete when:

- [ ] All 16 requirements have complete template fields
- [ ] OCI client implemented with ORAS library
- [ ] `floe platform publish` command implemented
- [ ] `floe init --platform=<version>` command implemented
- [ ] Artifact caching working (TTL and immutable handling)
- [ ] Schema validation via JSON Schema
- [ ] Multi-registry failover implemented
- [ ] Content-addressable digests verified on pull
- [ ] Tag immutability enforced
- [ ] Provenance metadata embedded and tracked
- [ ] Artifact discovery/search implemented
- [ ] All OCI operation tests pass (>80% coverage)
- [ ] Documentation updated
- [ ] Architecture docs backreference requirements

## Epic Mapping

These requirements are satisfied in **Epic 6: OCI Registry** Phase 4B-4C:
- Phase 4B: OCI artifact publishing (REQ-300 to REQ-309)
- Phase 4C: Schema versioning and artifact management (REQ-310 to REQ-315)
