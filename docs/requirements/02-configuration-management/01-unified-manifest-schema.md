# REQ-100 to REQ-115: Unified Manifest Schema with 2-Tier and 3-Tier Support

**Domain**: Configuration Management
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines the unified Manifest schema that supports both 2-tier (single platform) and 3-tier (Data Mesh) configurations without breaking changes.

**Key Principle**: One Pydantic model for all scopes (ADR-0038, ADR-0037)

## Requirements

### REQ-100: Unified Manifest Schema with Scope Field **[New]**

**Requirement**: System MUST define Manifest as a single Pydantic v2 model with optional scope field (`Literal["enterprise", "domain"] | None`) that determines usage mode (2-tier or 3-tier).

**Rationale**: Single schema supports both startup (2-tier) and Data Mesh (3-tier) without breaking changes when scaling.

**Acceptance Criteria**:
- [ ] Manifest schema defined in `floe_core/schemas/manifest.py`
- [ ] scope field: `Literal["enterprise", "domain"] | None = None`
- [ ] All fields compatible with 2-tier (scope: None) and 3-tier (scope: "enterprise"/"domain")
- [ ] Pydantic v2 syntax with model_config and field_validator
- [ ] JSON Schema exportable for IDE autocomplete
- [ ] Backward compatible with existing 2-tier manifests

**Enforcement**:
- Schema validation tests
- Backward compatibility tests
- JSON Schema export tests

**Constraints**:
- MUST use Pydantic v2 syntax (BaseModel, Field, model_config)
- MUST be serializable to YAML and JSON
- MUST include metadata (apiVersion, kind)
- FORBIDDEN to create separate ManifestV1 and ManifestV2 types

**Test Coverage**: `tests/contract/test_manifest_schema.py::test_unified_manifest_scope_field`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) lines 102-135
- platform-enforcement.md lines 1-50
- MIGRATION-ROADMAP.md

---

### REQ-101: Plugin Approval Schema with approved_plugins Field **[New]**

**Requirement**: System MUST support `approved_plugins` field in Enterprise and Domain manifests to define whitelists of allowed plugins per category (compute, orchestrator, catalog, etc.).

**Rationale**: Enables enterprise to control which plugins are allowed, domains to select from approved list.

**Acceptance Criteria**:
- [ ] approved_plugins field: `dict[str, list[str]] | None = None`
- [ ] Keys: compute, orchestrator, catalog, semantic_layer, ingestion, storage, observability, identity, secrets
- [ ] Values: list of plugin names (e.g., ["duckdb", "snowflake"])
- [ ] Only Enterprise manifests can DEFINE approved_plugins
- [ ] Domain and Product manifests INHERIT approved_plugins
- [ ] Compile-time validation: domain plugins in enterprise whitelist
- [ ] Clear error messages when plugin not approved

**Enforcement**:
- Plugin approval validation tests
- Whitelist inheritance tests
- Rejection tests for unapproved plugins

**Constraints**:
- MUST reject domains using plugins not in enterprise whitelist
- MUST support partial whitelists (some categories restricted, others not)
- FORBIDDEN for domains to override approved_plugins

**Test Coverage**: `tests/contract/test_manifest_schema.py::test_approved_plugins_inheritance`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) lines 138-195
- platform-enforcement.md lines 247-281

---

### REQ-102: Three-Tier Inheritance Resolution Algorithm **[New]**

**Requirement**: System MUST implement manifest resolution algorithm that loads and merges Enterprise → Domain → Product manifests in correct precedence order, validating security policies are not weakened.

**Rationale**: Enables Data Mesh while preventing domain/product from bypassing enterprise governance.

**Acceptance Criteria**:
- [ ] resolve_manifest(product: DataProduct) → ResolvedManifest
- [ ] Detects scope field to determine 2-tier vs 3-tier
- [ ] If 3-tier: loads enterprise and domain, validates chain
- [ ] If 2-tier: loads platform manifest only
- [ ] Validates domain plugins in enterprise whitelist
- [ ] Validates product in domain approved_products
- [ ] Returns ResolvedManifest with all inherited config
- [ ] Clear error messages for resolution failures

**Enforcement**:
- Resolution algorithm tests
- Precedence order tests
- Error case handling tests

**Constraints**:
- MUST load manifests from OCI registry (parent_manifest: oci://...)
- MUST validate inheritance chain (no circular references)
- MUST cache resolved manifests (avoid repeated loads)
- FORBIDDEN to allow domain to weaken security policies

**Test Coverage**: `tests/contract/test_manifest_resolution.py`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) lines 262-335
- platform-enforcement.md lines 247-281

---

### REQ-103: Immutable Enterprise Security Policies **[New]**

**Requirement**: System MUST enforce that Enterprise manifest security policies are IMMUTABLE - domains CANNOT override approved_plugins, pii_encryption, or audit_logging settings.

**Rationale**: Prevents security bypasses where domain weakens enterprise governance.

**Acceptance Criteria**:
- [ ] compile-time validation: domain policy_enforcement_level >= enterprise level
- [ ] compile-time validation: domain pii_encryption >= enterprise requirement
- [ ] compile-time validation: domain audit_logging >= enterprise requirement
- [ ] Clear error: "Cannot override security policy" when violation detected
- [ ] Domains can STRENGTHEN (make stricter), not weaken
- [ ] Testing validates immutability at each tier

**Enforcement**:
- Security policy override detection tests
- Weakening prevention tests
- Error message validation tests

**Constraints**:
- MUST reject manifests with weaker security policies
- MUST log security policy violation attempts
- FORBIDDEN to allow domain to disable security

**Test Coverage**: `tests/contract/test_manifest_security.py::test_immutable_enterprise_policies`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) lines 176-192
- platform-enforcement.md lines 247-281
- security.md

---

### REQ-104: Domain Plugin Validation Against Enterprise Whitelist **[New]**

**Requirement**: System MUST validate at compile-time that each Domain's selected plugins are in Enterprise approved_plugins list.

**Rationale**: Ensures domains respect enterprise governance without requiring manual review.

**Acceptance Criteria**:
- [ ] During manifest resolution: check domain.plugins[*] against enterprise.approved_plugins[*]
- [ ] For each plugin: validate plugin name and plugin type in enterprise whitelist
- [ ] Error if plugin not approved: "Plugin 'custom-compute' not in enterprise approved: ['duckdb', 'snowflake']"
- [ ] Support partial whitelists (some categories unrestricted)
- [ ] Clear actionable error messages

**Enforcement**:
- Plugin approval validation tests
- Whitelist subset validation tests
- Error message clarity tests

**Constraints**:
- MUST validate all plugin categories
- MUST reject unapproved plugins before compilation
- FORBIDDEN to load unapproved plugins at runtime

**Test Coverage**: `tests/contract/test_manifest_schema.py::test_domain_plugin_validation`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) lines 336-342
- platform-enforcement.md lines 247-281

---

### REQ-105: Product Approval by Domain (approved_products) **[New]**

**Requirement**: System MUST support `approved_products` field in Domain manifests, and validate that compiled products are in their domain's approved_products list.

**Rationale**: Enables domains to control which products are allowed to execute, preventing rogue or unapproved products.

**Acceptance Criteria**:
- [ ] approved_products field in Domain manifest: `list[str] | None = None`
- [ ] During product compilation: validate product.name in domain.approved_products
- [ ] Error if product not approved: "Product 'customer-360' not approved by domain 'sales'"
- [ ] Domains can define approval criteria (e.g., code review, security audit)
- [ ] Products inherit domain's approved_products (cannot override)

**Enforcement**:
- Product approval validation tests
- Domain approval list tests
- Rejection of unapproved products tests

**Constraints**:
- MUST validate product approval before compilation
- FORBIDDEN for products to override domain approval
- MUST log product approval violations

**Test Coverage**: `tests/contract/test_manifest_schema.py::test_approved_products_validation`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) lines 158-162
- platform-enforcement.md

---

### REQ-106: Manifest Merge Strategy with Override/Extend/Forbid **[New]**

**Requirement**: System MUST define merge strategy for inheritable fields: OVERRIDE (child replaces parent), EXTEND (child adds to parent), FORBID (parent immutable).

**Rationale**: Clear merge semantics prevent ambiguity in three-tier resolution.

**Acceptance Criteria**:
- [ ] OVERRIDE: child value replaces parent (e.g., plugins.compute)
- [ ] EXTEND: child adds to parent (e.g., governance rules)
- [ ] FORBID: parent immutable, child cannot change (e.g., approved_plugins)
- [ ] Merge strategy defined per field in schema documentation
- [ ] Validation enforces merge strategy
- [ ] Clear error when merge violates strategy

**Enforcement**:
- Merge strategy validation tests
- Field-by-field merge tests
- Strategy violation tests

**Constraints**:
- MUST document merge strategy for every field
- MUST reject merges that violate strategy
- FORBIDDEN to silently merge incompatible values

**Test Coverage**: `tests/contract/test_manifest_merging.py`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) lines 298-334
- platform-enforcement.md

---

### REQ-107: Policy Violation Error Messages **[New]**

**Requirement**: System MUST provide clear, actionable error messages when compilation fails due to policy violations, including: violation type, expected value, actual value, resolution steps.

**Rationale**: Enables data teams to quickly understand and fix governance violations.

**Acceptance Criteria**:
- [ ] Error includes violation type (policy/plugin/security/approval)
- [ ] Error includes parent/domain scope context
- [ ] Error includes expected constraint
- [ ] Error includes actual value provided
- [ ] Error includes resolution suggestion
- [ ] Error includes link to documentation
- [ ] Example message template documented

**Enforcement**:
- Error message quality tests
- Template validation tests
- Documentation accuracy tests

**Constraints**:
- MUST NOT expose internal implementation details
- MUST be actionable (not generic)
- FORBIDDEN to suppress policy violation errors

**Test Coverage**: `tests/contract/test_manifest_errors.py`

**Traceability**:
- platform-enforcement.md lines 223-243
- ADR-0037 (Composability Principle)

---

### REQ-108: OCI Registry Manifest Loading (parent_manifest) **[New]**

**Requirement**: System MUST support loading parent manifests from OCI registry via `parent_manifest: oci://...` field in Domain and Platform manifests.

**Rationale**: Enables versioned, immutable manifest distribution via industry-standard OCI registry.

**Acceptance Criteria**:
- [ ] parent_manifest field: `str | None = None` (URI format)
- [ ] Support URI: `oci://registry.example.com/floe-enterprise-manifest:v1.0.0`
- [ ] Support registries: DockerHub, Artifactory, ECR, GCR, etc.
- [ ] Cache loaded manifests (avoid repeated downloads)
- [ ] Validate registry certificate (TLS)
- [ ] Clear error messages for missing/invalid manifests

**Enforcement**:
- OCI registry loading tests
- URI parsing tests
- Caching validation tests
- TLS validation tests

**Constraints**:
- MUST use OCI Image spec for manifest artifacts
- MUST validate registry certificates
- MUST support registry authentication (config.json)
- FORBIDDEN to load from HTTP (only HTTPS)

**Test Coverage**: `tests/contract/test_oci_manifest_loading.py`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) lines 154-175
- oci-registry-requirements.md
- MIGRATION-ROADMAP.md

---

### REQ-109: Delegation Model via parent_ref Inheritance **[New]**

**Requirement**: System MUST support Enterprise → Domain delegation via parent_ref field, allowing Enterprise to delegate specific responsibilities to Domain-level manifests while maintaining strict hierarchy.

**Rationale**: Enables controlled delegation without environment-specific overrides, maintaining environment-agnostic compute (ADR-0016) and immutability principles.

**Acceptance Criteria**:
- [ ] Domain manifest includes `parent_ref` field pointing to Enterprise manifest
- [ ] Enterprise manifest can delegate: plugin whitelist selection, resource quotas, quality gate thresholds
- [ ] Domain inherits all Enterprise policies and can only strengthen (never weaken)
- [ ] Conflict resolution: Enterprise always wins (strict hierarchy)
- [ ] NO environment-specific overrides (env_overrides field removed)
- [ ] Validation: Domain cannot weaken Enterprise policies
- [ ] Clear error messages when delegation violated

**Enforcement**:
- Delegation model tests
- Policy inheritance tests
- Conflict resolution tests (Enterprise wins)

**Constraints**:
- MUST enforce strict hierarchy (Enterprise > Domain > Product)
- MUST NOT allow Domain to weaken Enterprise policies
- FORBIDDEN to support environment-specific overrides
- MUST maintain environment-agnostic compute (ADR-0016)

**Test Coverage**: `tests/contract/test_delegation_model.py`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) - Three-tier inheritance
- ADR-0016 (Environment-Agnostic Compute)
- ADR-0037 (Composability Principle)
- platform-enforcement.md

---

### REQ-110: Backward Compatibility with 2-Tier Manifests **[New]**

**Requirement**: System MUST support existing 2-tier configurations (platform-manifest.yaml with scope: None or missing) without breaking changes.

**Rationale**: Allows incremental adoption of 3-tier without forcing migration.

**Acceptance Criteria**:
- [ ] Existing platform-manifest.yaml loads without scope field
- [ ] Existing floe.yaml loads unchanged
- [ ] platform.ref resolves to 2-tier manifest
- [ ] parent_manifest field optional
- [ ] approved_plugins field optional
- [ ] Two-tier resolution algorithm (no enterprise/domain)
- [ ] No breaking schema changes

**Enforcement**:
- Backward compatibility tests
- Migration tests (2-tier → 3-tier)
- Schema evolution tests

**Constraints**:
- MUST support scope: None or missing scope
- MUST NOT require new fields for 2-tier configs
- FORBIDDEN to break existing manifests

**Test Coverage**: `tests/contract/test_backward_compatibility.py`

**Traceability**:
- ADR-0038 (Data Mesh Architecture) lines 194-210
- MIGRATION-ROADMAP.md

---

### REQ-111: Manifest Schema Versioning (apiVersion) **[New]**

**Requirement**: System MUST define `apiVersion: "floe.dev/v1"` field in Manifest to enable future schema changes with clear versioning.

**Rationale**: Enables forward compatibility and graceful handling of future schema changes.

**Acceptance Criteria**:
- [ ] apiVersion field: `Literal["floe.dev/v1"]`
- [ ] kind field: `Literal["Manifest"]`
- [ ] Current version: v1
- [ ] Future version: v2 would be backward incompatible
- [ ] Migration guide documented for version upgrades
- [ ] Validation: reject unknown apiVersions

**Enforcement**:
- Version validation tests
- Schema version tests
- Unknown version rejection tests

**Constraints**:
- MUST follow `domain.dev/vMAJOR` format
- MUST define version constants in floe_core
- FORBIDDEN to accept unknown versions

**Test Coverage**: `tests/contract/test_manifest_versioning.py`

**Traceability**:
- ADR-0037 (Composability Principle)
- pydantic-contracts.md

---

### REQ-112: Manifest Metadata (name, version, owner) **[New]**

**Requirement**: System MUST support metadata fields in Manifest: name, version, owner, description to enable audit trail and ownership tracking.

**Rationale**: Enables tracking of manifest versions, ownership, and audit history.

**Acceptance Criteria**:
- [ ] metadata.name: required, alphanumeric + hyphens
- [ ] metadata.version: required, semver (MAJOR.MINOR.PATCH)
- [ ] metadata.owner: required, email or team name
- [ ] metadata.description: optional, human-readable purpose
- [ ] Version used for OCI artifact tags
- [ ] Owner used for RBAC in future releases
- [ ] Validation: semver format, email format

**Enforcement**:
- Metadata validation tests
- Version format tests
- Owner format tests

**Constraints**:
- MUST validate semver format
- MUST validate email or team name format
- FORBIDDEN to allow empty metadata

**Test Coverage**: `tests/contract/test_manifest_metadata.py`

**Traceability**:
- ADR-0037 (Composability Principle)
- platform-enforcement.md

---

### REQ-113: Scope Field Validation and Constraints **[New]**

**Requirement**: System MUST validate scope field values and enforce constraints based on scope (e.g., parent_manifest required for domain scope, approved_plugins only for enterprise scope).

**Rationale**: Prevents misconfiguration of scope-specific fields.

**Acceptance Criteria**:
- [ ] scope: `Literal["enterprise", "domain"] | None`
- [ ] If scope="enterprise": parent_manifest MUST be None
- [ ] If scope="domain": parent_manifest MUST be set
- [ ] If scope="domain": approved_plugins inherited (optional)
- [ ] If scope=None: parent_manifest MUST be None (2-tier)
- [ ] If scope=None: approved_plugins ignored (2-tier)
- [ ] Clear error messages for scope constraint violations

**Enforcement**:
- Scope field validation tests
- Constraint validation tests
- Error message tests

**Constraints**:
- MUST reject invalid scope values
- MUST reject scope constraint violations
- FORBIDDEN to mix scope and parent_manifest incorrectly

**Test Coverage**: `tests/contract/test_manifest_scope_validation.py`

**Traceability**:
- ADR-0038 (Data Mesh Architecture)

---

### REQ-114: Governance Configuration Schema (data_retention_days, pii_encryption, etc.) **[New]**

**Requirement**: System MUST define governance configuration schema supporting: data_retention_days, pii_encryption (required/optional), audit_logging, policy_enforcement_level.

**Rationale**: Enables platform to enforce governance policies consistently.

**Acceptance Criteria**:
- [ ] governance field: `GovernanceConfig | None = None`
- [ ] data_retention_days: `int | None` (minimum, can be overridden stricter)
- [ ] pii_encryption: `Literal["required", "optional"]` (immutable)
- [ ] audit_logging: `Literal["enabled", "disabled"]` (immutable if enabled)
- [ ] policy_enforcement_level: `Literal["off", "warn", "strict"]`
- [ ] Validation: retention_days >= 0
- [ ] Validation: policy_enforcement_level can only strengthen

**Enforcement**:
- Governance config validation tests
- Immutability enforcement tests
- Strengthening-only tests

**Constraints**:
- MUST NOT allow weakening of governance policies
- MUST validate retention days are reasonable
- FORBIDDEN to disable audit logging if enabled at parent

**Test Coverage**: `tests/contract/test_governance_config.py`

**Traceability**:
- platform-enforcement.md
- ADR-0037 (Composability Principle)

---

### REQ-115: Parent Manifest Reference Validation **[New]**

**Requirement**: System MUST validate parent_manifest references are valid, accessible, and form a proper inheritance chain (no cycles, proper versioning).

**Rationale**: Prevents broken inheritance chains and circular references.

**Acceptance Criteria**:
- [ ] parent_manifest URI format: oci://registry/name:version
- [ ] Registry must be accessible and have valid TLS certificate
- [ ] Manifest must exist in registry
- [ ] Manifest must have scope="enterprise" for domain parent_manifest
- [ ] No circular references (domain → enterprise → domain)
- [ ] Version compatibility (semantic versioning)
- [ ] Clear error messages for invalid references

**Enforcement**:
- Parent reference validation tests
- Circular reference detection tests
- Registry accessibility tests
- Version validation tests

**Constraints**:
- MUST validate registry is accessible
- MUST detect and reject circular references
- FORBIDDEN to load manifests with broken parent references

**Test Coverage**: `tests/contract/test_parent_manifest_validation.py`

**Traceability**:
- REQ-108 (OCI Registry Manifest Loading)
- ADR-0038 (Data Mesh Architecture)

---

## Domain Acceptance Criteria

Unified Manifest Schema (REQ-100 to REQ-115) is complete when:

- [ ] All 16 requirements have complete template fields
- [ ] Manifest schema implemented in Pydantic v2 with scope field
- [ ] Three-tier inheritance resolution algorithm implemented
- [ ] Security policy immutability enforced
- [ ] Plugin approval validation working
- [ ] OCI registry manifest loading implemented
- [ ] Backward compatibility with 2-tier configs
- [ ] Unit tests pass with >80% coverage
- [ ] Contract tests validate schema behavior
- [ ] Documentation updated:
  - [ ] platform-enforcement.md backreferences requirements
  - [ ] ADR-0038 backreferences requirements
  - [ ] ADR-0037 backreferences requirements

## Epic Mapping

These requirements are satisfied in **Epic 2: Configuration Layer Modernization**:
- Phase 1: Define unified Manifest schema with scope field
- Phase 2: Implement three-tier inheritance resolution
- Phase 3: Add OCI registry manifest loading
- Phase 4: Enable Data Mesh configuration
