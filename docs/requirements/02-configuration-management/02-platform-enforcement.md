# REQ-116 to REQ-130: Platform Enforcement and Governance

**Domain**: Configuration Management
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines the enforcement mechanisms that validate data products comply with platform governance rules at compile-time, preventing runtime violations.

**Key Principle**: Compile-time enforcement prevents non-compliant deployments

## Requirements

### REQ-116: PolicyEnforcer Core Module **[Updated]**

**Requirement**: System MUST define PolicyEnforcer module in `floe_core/enforcement/policy_enforcer.py` with required methods: validate_naming, validate_classification, validate_quality_gates, validate_governance.

**Rationale**: PolicyEnforcer is a core module (not plugin) that validates against rules configured in manifest.yaml.

> **Note:** PolicyEnforcer is now a **core module** in floe-core, not a plugin. Policy enforcement tooling is provided via DBTPlugin (linting), and rules are configured via manifest.yaml.

**Acceptance Criteria**:
- [ ] PolicyEnforcer module defined with required methods
- [ ] validate_naming(model: DbtModel, manifest: Manifest) → list[PolicyViolation]
- [ ] validate_classification(model: DbtModel, manifest: Manifest) → list[PolicyViolation]
- [ ] validate_quality_gates(model: DbtModel, manifest: Manifest) → list[PolicyViolation]
- [ ] validate_governance(product: DataProduct, manifest: Manifest) → list[PolicyViolation]
- [ ] Configuration via manifest.yaml governance section
- [ ] Core module (not pluggable via entry points)

**Enforcement**:
- Plugin interface compliance tests
- Abstract method validation tests
- Entry point registration tests

**Constraints**:
- MUST inherit from ABC with abstractmethod decorators
- MUST define clear PolicyViolation model
- FORBIDDEN to hardcode policies in core

**Test Coverage**: `tests/contract/test_policy_enforcer_plugin.py`

**Traceability**:
- platform-enforcement.md lines 128-147
- ADR-0016 (Platform Enforcement Architecture)
- Domain 01 (Plugin Architecture)

---

### REQ-117: Default PolicyEnforcer Implementation **[New]**

**Requirement**: System MUST provide default PolicyEnforcer implementation in `floe-policy-enforcer` package that validates naming conventions, classification compliance, and quality gates based on Manifest configuration.

**Rationale**: Provides baseline enforcement without requiring custom plugins.

**Acceptance Criteria**:
- [ ] DefaultPolicyEnforcer implements PolicyEnforcer interface
- [ ] validate_naming: enforces medallion pattern (bronze/silver/gold) or custom
- [ ] validate_classification: enforces PII tagging per manifest rules
- [ ] validate_quality_gates: enforces test coverage, doc requirements
- [ ] validate_governance: enforces data retention, audit logging
- [ ] Configurable via manifest governance field
- [ ] Clear error messages for violations

**Enforcement**:
- Policy enforcement tests
- Pattern matching tests
- Configuration tests

**Constraints**:
- MUST read policies from Manifest (not hardcoded)
- MUST support multiple patterns (medallion, others)
- FORBIDDEN to ignore policy violations

**Test Coverage**: `plugins/floe-policy-enforcer/tests/unit/test_default_enforcer.py`

**Traceability**:
- platform-enforcement.md lines 149-182
- REQ-116 (PolicyEnforcer Plugin Interface)

---

### REQ-118: Naming Convention Enforcement **[New]**

**Requirement**: System MUST enforce data architecture naming conventions defined in Manifest.data_architecture.naming (e.g., medallion: bronze_*, silver_*, gold_*).

**Rationale**: Enforces consistent naming across organization, enables layer-based governance.

**Acceptance Criteria**:
- [ ] data_architecture.naming field in Manifest: pattern, enforcement level
- [ ] pattern: "medallion" | "custom" | None
- [ ] enforcement: "off" | "warn" | "strict"
- [ ] Medallion pattern: bronze_*, silver_*, gold_* prefixes required
- [ ] Custom pattern: regex-based validation
- [ ] Compile-time check: reject non-conforming models when strict
- [ ] Clear error messages with suggestions

**Enforcement**:
- Naming validation tests
- Pattern matching tests
- Enforcement level tests
- Error message tests

**Constraints**:
- MUST validate all dbt models
- MUST support configurable patterns
- FORBIDDEN to allow unapproved names in strict mode

**Test Coverage**: `tests/contract/test_naming_enforcement.py`

**Traceability**:
- platform-enforcement.md lines 72-98
- ADR-0021 (Data Architecture Patterns)

---

### REQ-119: Data Classification Compliance **[New]**

**Requirement**: System MUST enforce data classification compliance by validating that PII and sensitive fields are tagged according to Manifest governance rules.

**Rationale**: Enables automated enforcement of data privacy policies.

**Acceptance Criteria**:
- [ ] governance.pii_encryption: "required" or "optional"
- [ ] governance.sensitive_fields: list of field patterns (email, ssn, phone)
- [ ] Validate: sensitive fields have classification tag
- [ ] Validate: PII fields are encrypted/masked in gold layer
- [ ] Compile-time error: missing classifications or encryption
- [ ] Integration with dbt model metadata

**Enforcement**:
- Classification validation tests
- Sensitive field detection tests
- Encryption verification tests

**Constraints**:
- MUST detect PII fields (email, ssn, phone, etc.)
- MUST enforce encryption requirements
- FORBIDDEN to allow untagged PII in production

**Test Coverage**: `tests/contract/test_classification_compliance.py`

**Traceability**:
- platform-enforcement.md lines 143-147
- ADR-0021 (Data Architecture Patterns)
- security.md

---

### REQ-120: Quality Gate Enforcement (Test Coverage, Documentation) **[New]**

**Requirement**: System MUST enforce quality gates defined in Manifest.governance.quality_gates: minimum_test_coverage, documentation_required, etc.

**Rationale**: Ensures data quality standards are met before deployment.

**Acceptance Criteria**:
- [ ] quality_gates field in Manifest: minimum_test_coverage, documentation_required
- [ ] minimum_test_coverage: percentage (default 80%)
- [ ] documentation_required: true/false
- [ ] Compile-time validation: check dbt model test coverage
- [ ] Compile-time validation: check model documentation exists
- [ ] Parse dbt manifest.json to extract test coverage
- [ ] Clear error: which tests are missing

**Enforcement**:
- Test coverage validation tests
- Documentation requirement tests
- dbt manifest parsing tests

**Constraints**:
- MUST parse dbt manifest.json for accurate coverage
- MUST reject under-tested models in strict mode
- FORBIDDEN to skip quality gate validation

**Test Coverage**: `tests/contract/test_quality_gates.py`

**Traceability**:
- platform-enforcement.md lines 149-159
- ADR-0021 (Data Architecture Patterns)

---

### REQ-121: Governance Violations with Actionable Error Messages **[New]**

**Requirement**: System MUST provide clear, actionable error messages when governance violations are detected, including: violation type, expected value, actual value, resolution steps.

**Rationale**: Enables data teams to quickly understand and fix violations.

**Acceptance Criteria**:
- [ ] Error message includes violation type (naming, classification, quality, governance)
- [ ] Error message includes model/field name
- [ ] Error message includes expected constraint
- [ ] Error message includes actual value
- [ ] Error message includes resolution suggestion
- [ ] Error message includes link to documentation
- [ ] Example template: see platform-enforcement.md lines 227-243

**Enforcement**:
- Error message quality tests
- Template validation tests
- Documentation accuracy tests

**Constraints**:
- MUST NOT expose internal implementation details
- MUST be actionable (not generic)
- FORBIDDEN to suppress violation errors

**Test Coverage**: `tests/contract/test_governance_error_messages.py`

**Traceability**:
- platform-enforcement.md lines 227-243
- REQ-107 (Policy Violation Error Messages)

---

### REQ-122: Runtime vs Compile-Time Enforcement Levels **[New]**

**Requirement**: System MUST support enforcement levels for policies: "off" (no enforcement), "warn" (log warnings, continue), "strict" (block on violation).

**Rationale**: Enables gradual adoption and migration from non-compliant state.

**Acceptance Criteria**:
- [ ] enforcement_level field: "off" | "warn" | "strict"
- [ ] "off": skip validation, log message
- [ ] "warn": validate, log warnings, continue compilation
- [ ] "strict": validate, fail compilation on violation
- [ ] Configurable per policy type (naming, classification, quality)
- [ ] CLI override: `floe compile --enforcement=warn`
- [ ] Default: "strict" for production

**Enforcement**:
- Enforcement level tests
- Level behavior tests
- CLI override tests

**Constraints**:
- MUST support CLI overrides
- MUST default to strict for critical policies
- FORBIDDEN to bypass security policies with "off"

**Test Coverage**: `tests/contract/test_enforcement_levels.py`

**Traceability**:
- platform-enforcement.md lines 172-182

---

### REQ-123: Data Architecture Pattern Support (Medallion and Custom) **[New]**

**Requirement**: System MUST support configurable data architecture patterns: built-in medallion (bronze/silver/gold) and custom patterns defined via regex.

**Rationale**: Enables organizations with different architecture approaches.

**Acceptance Criteria**:
- [ ] pattern field: "medallion" | "custom" | None
- [ ] Medallion: validates bronze_*, silver_*, gold_* prefixes
- [ ] Custom: regex pattern in governance.naming.custom_pattern
- [ ] None: no naming validation (backward compatibility)
- [ ] Clear documentation of each pattern
- [ ] Test patterns work with all layer names

**Enforcement**:
- Pattern matching tests
- Custom regex validation tests
- Medallion pattern tests

**Constraints**:
- MUST support arbitrary patterns via regex
- MUST be case-insensitive or configurable
- FORBIDDEN to hardcode single pattern

**Test Coverage**: `tests/contract/test_data_architecture_patterns.py`

**Traceability**:
- platform-enforcement.md lines 40-43
- ADR-0021 (Data Architecture Patterns)

---

### REQ-124: Catalog Namespace Validation **[New]**

**Requirement**: System MUST validate that compiled data products can claim their assigned catalog namespace (domain.product format), preventing namespace collisions.

**Rationale**: Prevents multiple products claiming the same namespace, causing data corruption.

**Acceptance Criteria**:
- [ ] Product namespace: {domain}.{product_name}
- [ ] Compile-time validation: namespace available or owned by current repo
- [ ] Error if namespace owned by different repository
- [ ] Atomic registration in catalog (compare-and-swap)
- [ ] Clear error message with namespace owner contact
- [ ] Support all Iceberg catalogs (Polaris, Unity, Glue, Nessie)

**Enforcement**:
- Namespace validation tests
- Conflict detection tests
- Atomic registration tests
- Catalog-specific tests

**Constraints**:
- MUST use atomic operations to prevent race conditions
- MUST detect namespace collisions early
- FORBIDDEN to allow data corruption from namespace conflicts

**Test Coverage**: `tests/contract/test_namespace_validation.py`

**Traceability**:
- platform-enforcement.md lines 422-607
- ADR-0030 (Namespace-Based Identity)

---

### REQ-125: Access Control Enforcement via Catalog RBAC **[New]**

**Requirement**: System MUST enforce access control by leveraging catalog RBAC (role-based access control) to restrict who can create, modify, or delete products in their domain namespace.

**Rationale**: Ensures only authorized teams can manage their data products.

**Acceptance Criteria**:
- [ ] Catalog principal (service account) scoped to domain namespace
- [ ] Only domain members can modify products in domain namespace
- [ ] Cross-domain products require explicit approval
- [ ] Runtime check: principal has permission before execution
- [ ] Clear error: permission denied on unauthorized access

**Enforcement**:
- RBAC validation tests
- Permission checking tests
- Cross-domain authorization tests

**Constraints**:
- MUST integrate with catalog RBAC (Polaris, Unity, Glue)
- MUST fail compilation if principal lacks permissions
- FORBIDDEN to execute without proper permissions

**Test Coverage**: `tests/contract/test_access_control.py`

**Traceability**:
- platform-enforcement.md
- ADR-0022 (Security & RBAC Model)

---

### REQ-126: SLA Enforcement (Freshness, Availability) **[New]**

**Requirement**: System MUST support SLA (Service Level Agreement) enforcement by validating that data products declare required freshness and availability SLAs matching or exceeding domain/enterprise minimums.

**Rationale**: Ensures consistent data quality SLAs across organization.

**Acceptance Criteria**:
- [ ] governance.slas: freshness (hours), availability (percentage)
- [ ] Enterprise sets minimum SLAs
- [ ] Domain can require stricter SLAs
- [ ] Product declares SLAs in schedule/monitoring config
- [ ] Compile-time validation: product SLAs >= domain minimums
- [ ] Error if product SLAs below required minimums

**Enforcement**:
- SLA validation tests
- Minimum enforcement tests
- Inheritance tests

**Constraints**:
- MUST reject products with insufficient SLAs
- MUST support domain-specific SLAs
- FORBIDDEN to allow weaker SLAs than parent

**Test Coverage**: `tests/contract/test_sla_enforcement.py`

**Traceability**:
- platform-enforcement.md lines 285-291
- ADR-0026 (Data Contract Architecture)

---

### REQ-127: Schema Stability and Evolution Rules **[New]**

**Requirement**: System MUST enforce schema evolution rules defined in Manifest to control breaking changes in data contracts.

**Rationale**: Prevents downstream breakage when schema changes.

**Acceptance Criteria**:
- [ ] governance.schema_evolution: "strict" | "additive" | "any"
- [ ] "strict": no changes allowed (immutable schema)
- [ ] "additive": only new fields allowed (backward compatible)
- [ ] "any": any changes allowed (at consumer's risk)
- [ ] Validate against previous schema version
- [ ] Error: breaking schema changes in strict mode

**Enforcement**:
- Schema comparison tests
- Evolution rule tests
- Backward compatibility tests

**Constraints**:
- MUST detect breaking changes
- MUST enforce evolution rules
- FORBIDDEN to silently break downstream contracts

**Test Coverage**: `tests/contract/test_schema_evolution.py`

**Traceability**:
- ADR-0026 (Data Contract Architecture)
- ADR-0027 (ODCS Standard Adoption)

---

### REQ-128: Cross-Domain Data Product Dependencies **[New]**

**Requirement**: System MUST allow data products to depend on other domains' products via explicit data contracts, while enforcing that dependencies are declared and tracked.

**Rationale**: Enables data mesh architectures where products consume from other domains.

**Acceptance Criteria**:
- [ ] Product can declare dependencies: depends_on: [domain.product]
- [ ] Dependency validation: target product must exist and export
- [ ] Dependency tracking: lineage includes cross-domain lineage
- [ ] Access control: consumer must have permission to access
- [ ] SLA inheritance: dependent product inherits upstream SLAs
- [ ] Error: missing or inaccessible dependencies

**Enforcement**:
- Dependency validation tests
- Access control tests
- SLA inheritance tests
- Lineage tests

**Constraints**:
- MUST validate dependencies are accessible
- MUST track cross-domain lineage
- FORBIDDEN to create circular dependencies

**Test Coverage**: `tests/contract/test_cross_domain_dependencies.py`

**Traceability**:
- platform-enforcement.md lines 247-281
- ADR-0030 (Namespace-Based Identity)

---

### REQ-129: GitOps Workflow for Manifest Updates **[New]**

**Requirement**: System MUST support GitOps workflow where platform manifest updates are version-controlled and deployed via CI/CD (Git as source of truth).

**Rationale**: Enables auditable, reversible platform changes with proper approval workflow.

**Acceptance Criteria**:
- [ ] Platform manifests stored in Git repository
- [ ] CI/CD pipeline: test → publish OCI artifact → deploy
- [ ] Version tag: Git tag triggers OCI artifact publication
- [ ] Rollback: previous manifest version accessible via Git
- [ ] Audit trail: all manifest changes recorded in Git
- [ ] Approval workflow: PR review before manifest changes

**Enforcement**:
- Git workflow tests
- CI/CD integration tests
- Rollback functionality tests
- Audit trail validation tests

**Constraints**:
- MUST store manifests in Git
- MUST publish versioned OCI artifacts
- FORBIDDEN to modify manifests manually in production

**Test Coverage**: `tests/e2e/test_gitops_workflow.py`

**Traceability**:
- ADR-0037 (Composability Principle)
- MIGRATION-ROADMAP.md

---

### REQ-130: Manifest Validation and Dry-Run Testing **[New]**

**Requirement**: System MUST support `floe manifest validate` and `floe manifest test` commands to validate manifest syntax and test policy enforcement without modifying state.

**Rationale**: Enables safe testing of manifest changes before deployment.

**Acceptance Criteria**:
- [ ] `floe manifest validate`: syntax and schema validation
- [ ] `floe manifest test`: dry-run all policy checks against sample products
- [ ] Output: detailed report of all policies
- [ ] Exit code: non-zero on validation failure
- [ ] Supports manifest URL: --manifest=oci://...
- [ ] Supports local files: --manifest=./manifest.yaml

**Enforcement**:
- Validation command tests
- Dry-run tests
- Exit code tests
- Report format tests

**Constraints**:
- MUST NOT modify state during validation
- MUST support all policy checks
- FORBIDDEN to skip validation steps

**Test Coverage**: `tests/unit/test_manifest_validation_commands.py`

**Traceability**:
- REQ-116 to REQ-129
- platform-enforcement.md

---

## Domain Acceptance Criteria

Platform Enforcement and Governance (REQ-116 to REQ-130) is complete when:

- [ ] All 15 requirements have complete template fields
- [ ] PolicyEnforcer plugin interface defined
- [ ] Default PolicyEnforcer implementation
- [ ] Naming convention enforcement working
- [ ] Classification compliance validation
- [ ] Quality gate enforcement
- [ ] SLA enforcement
- [ ] Schema evolution rules
- [ ] Cross-domain dependencies
- [ ] GitOps workflow support
- [ ] Manifest validation commands
- [ ] Unit tests pass with >80% coverage
- [ ] Contract tests validate enforcement behavior
- [ ] Documentation updated:
  - [ ] platform-enforcement.md backreferences requirements
  - [ ] ADR-0016 backreferences requirements
  - [ ] ADR-0021 backreferences requirements

## Epic Mapping

These requirements are satisfied in **Epic 6: Platform Enforcement Engine**:
- Phase 1: PolicyEnforcer plugin interface
- Phase 2: Policy implementations (naming, quality gates)
- Phase 3: Data governance (classification, SLAs)
- Phase 4: Cross-domain enforcement
