# REQ-200 to REQ-220: Policy Enforcement and Validation

**Domain**: Data Governance
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines the PolicyEnforcer **core module** (not plugin), compile-time validation hooks, and enforcement mechanisms that ensure data products comply with platform-defined policies before runtime.

> **Note:** PolicyEnforcer is now a **core module** in floe-core, not a plugin. Policy enforcement tooling is provided via DBTPlugin (linting), and rules are configured via platform-manifest.yaml.

**Key Principle**: Non-compliant pipelines fail before runtime (ADR-0016)

## Requirements

### REQ-200: PolicyEnforcer Interface Definition **[New]**

**Requirement**: System MUST define PolicyEnforcer ABC with abstract methods for policy validation.

**Rationale**: Standardizes policy validation across different policy implementations.

**Acceptance Criteria**:
- [ ] PolicyEnforcer module defined in floe-core
- [ ] Methods: validate_data_product, enforce_naming, validate_data_contracts, check_classification_compliance, validate_product_identity
- [ ] PolicyEnforcer is a core module (not pluggable)
- [ ] Configuration via platform-manifest.yaml governance section
- [ ] Default implementation provided

**Enforcement**:
- Unit tests verify PolicyEnforcer interface
- Contract tests validate plugin compliance
- Architectural tests enforce abstraction

**Constraints**:
- MUST be abstract base class (ABC)
- MUST define all policy validation methods
- MUST NOT hardcode policy logic in interface
- FORBIDDEN to make policy implementation optional

**Test Coverage**: `tests/contract/test_policy_enforcer.py`

**Traceability**:
- platform-enforcement.md lines 129-147
- ADR-0016 (Platform Enforcement Architecture)
- ADR-0012 (Data Classification)

**Files to Create**:
- `floe-core/src/floe_core/plugin_interfaces.py` - Add PolicyEnforcer ABC

---

### REQ-201: Naming Convention Enforcement **[New]**

**Requirement**: PolicyEnforcer MUST enforce naming conventions defined in platform-manifest for data architecture pattern (medallion, kimball, lakehouse).

**Rationale**: Consistent naming enables automated classification and governance.

**Acceptance Criteria**:
- [ ] enforce_naming() method validates model names against architecture pattern
- [ ] Medallion pattern enforces bronze_*, silver_*, gold_* prefixes
- [ ] Kimball pattern enforces dim_*, fact_* prefixes
- [ ] Lakehouse pattern allows custom rules
- [ ] Enforcement levels: off, warn, strict
- [ ] Clear error messages with suggestions

**Enforcement**:
- Naming validation tests for each pattern
- Enforcement level tests (off/warn/strict)
- Migration path tests (stg_* → bronze_*)

**Constraints**:
- MUST support 3 patterns: medallion, kimball, lakehouse
- MUST provide actionable error messages
- FORBIDDEN to reject valid names without alternatives
- MUST allow configuration of custom patterns

**Test Coverage**: `tests/unit/test_naming_enforcement.py`

**Traceability**:
- platform-enforcement.md lines 75-98
- ADR-0021 (Data Architecture Patterns)

---

### REQ-202: Compile-Time Policy Validation Hook **[New]**

**Requirement**: Compiler MUST call PolicyEnforcer.validate_data_product() during `floe compile` to validate product against manifest.

**Rationale**: Early failure prevents non-compliant deployments.

**Acceptance Criteria**:
- [ ] floe compile invokes PolicyEnforcer during compilation
- [ ] Compilation fails if validation returns errors
- [ ] Validation errors are formatted as compile output
- [ ] PolicyEnforcer receives fully parsed Manifest and DataProduct
- [ ] Validation runs after parsing, before artifact generation

**Enforcement**:
- Compilation tests with PolicyEnforcer validation
- Error message formatting tests
- Manifest + DataProduct fixture tests

**Constraints**:
- MUST validate before artifact generation
- MUST NOT suppress validation errors
- FORBIDDEN to allow overrides of policy violations
- MUST provide CLI exit code 1 on validation failure

**Test Coverage**: `tests/integration/test_compile_policy_validation.py`

**Traceability**:
- platform-enforcement.md lines 75-99
- ADR-0016 (Platform Enforcement Architecture)

**Implementation**:
- Modify `floe_core/compiler.py` to call PolicyEnforcer

---

### REQ-203: Classification Metadata Validation **[New]**

**Requirement**: PolicyEnforcer MUST validate data classification metadata in dbt model YAML (floe: meta tags).

**Rationale**: Ensures sensitive data is properly classified before reaching production.

**Acceptance Criteria**:
- [ ] check_classification_compliance() validates dbt meta.floe.classification
- [ ] Validates classification values: public, internal, confidential, pii, phi, financial
- [ ] Validates pii_type for PII classifications: email, phone, ssn, address, name, dob, ip_address
- [ ] Validates sensitivity levels: low, medium, high, critical
- [ ] Enforces required classifications for models containing sensitive data
- [ ] Reports misclassified columns with remediation suggestions

**Enforcement**:
- Classification validation tests
- Classification schema tests
- dbt manifest parsing tests

**Constraints**:
- MUST validate all classification types
- MUST require classification for regulated data
- FORBIDDEN to allow unclassified PII/PHI columns
- MUST support custom classifications via policy

**Test Coverage**: `tests/unit/test_classification_validation.py`

**Traceability**:
- ADR-0012 (Data Classification and Governance Architecture) lines 36-57

---

### REQ-204: Platform Policy Resolution **[New]**

**Requirement**: PolicyEnforcer MUST resolve and merge policies from enterprise manifest, domain manifest, and data product.

**Rationale**: Supports three-tier governance with policy inheritance.

**Acceptance Criteria**:
- [ ] Enterprise manifest defines base policies (non-negotiable)
- [ ] Domain manifest inherits from enterprise, can strengthen only
- [ ] Data product inherits from domain, can strengthen only
- [ ] Policy merging follows conflict resolution rules
- [ ] Violations detected if child weakens parent policy

**Enforcement**:
- Three-tier policy inheritance tests
- Policy conflict detection tests
- Weakening prevention tests

**Constraints**:
- MUST prevent weakening (lower tiers cannot reduce restrictions)
- MUST merge policies correctly across tiers
- FORBIDDEN to allow policy override without parent scope
- MUST provide clear error messages for conflicts

**Test Coverage**: `tests/unit/test_policy_resolution.py`

**Traceability**:
- platform-enforcement.md lines 249-291
- ADR-0016 (Platform Enforcement Architecture)

---

### REQ-205: dbt Structure Validation via dbt-checkpoint **[Updated]**

**Requirement**: PolicyEnforcer MUST validate dbt project structure (test coverage, documentation, property files) using dbt-checkpoint pre-commit hooks.

**Rationale**: Enforces dbt best practices at compile-time (test coverage >= X%, documentation required, property files exist).

**Architectural Clarification**:
- **dbt-checkpoint** validates dbt PROJECT STRUCTURE, NOT SQL syntax ([research confirmed](https://github.com/dbt-checkpoint/dbt-checkpoint))
- Validates: test coverage, column documentation, property files, source freshness, model naming
- Does NOT validate: SQL syntax, SQL style, SQL correctness (those are handled by DBTPlugin.lint_project() - see REQ-097)

**Acceptance Criteria**:
- [ ] PolicyEnforcer.validate_dbt_structure() wraps dbt-checkpoint
- [ ] Supports structure rules: check-model-has-tests, check-model-has-description, check-source-has-freshness
- [ ] Validates test coverage >= platform-configured threshold (e.g., 80%)
- [ ] Validates column documentation completeness
- [ ] Configuration via platform-manifest.yaml (enforcement level: off, warn, strict)
- [ ] dbt-checkpoint violations block compilation (when enforcement=strict)
- [ ] Reports detailed structure violations with suggestions

**Enforcement**:
- dbt-checkpoint integration tests
- Structure validation tests (test coverage, documentation)
- Configuration override tests

**Constraints**:
- MUST use dbt-checkpoint v1.x
- MUST report structure violations clearly (e.g., "Model 'customers' missing tests")
- FORBIDDEN to suppress dbt-checkpoint errors when enforcement=strict
- MUST support custom checkpoint rules via .dbt-checkpoint.yaml

**Example Violations**:
```
❌ Model 'customers' has 0 tests (minimum: 2 required)
❌ Column 'customers.email' missing description
❌ Source 'raw.orders' missing freshness check
```

**Test Coverage**: `tests/integration/test_dbt_structure_validation.py`

**Traceability**:
- platform-enforcement.md
- ADR-0009 (dbt Owns SQL)
- **Cross-reference**: REQ-097 (SQLFluff SQL linting via DBTPlugin)

**Files to Create**:
- `floe-core/src/floe_core/validators/dbt_structure_validator.py`

**Related Requirements**:
- **REQ-097**: SQL style linting (SQLFluff) via DBTPlugin.lint_project()
- **REQ-098**: SQL semantic validation (dbt Fusion) via DBTPlugin.lint_project()

---

### REQ-206: SQL Linting Enforcement via DBTPlugin **[Updated - Architectural Clarification]**

**Requirement**: Platform teams MUST enforce SQL linting policies via DBTPlugin.lint_project() integration. PolicyEnforcer validates that linting was executed and enforces platform-configured linting policy (error/warning/disabled).

**Rationale**: SQL linting is a DBT responsibility per ADR-0009 ("dbt owns SQL") and ADR-0043 (dbt Compilation Abstraction). PolicyEnforcer ensures linting policy compliance, but delegates actual SQL validation to DBTPlugin.

**Architectural Clarification**:
- **SQL linting ownership**: DBTPlugin.lint_project() (see REQ-097, REQ-098)
  - LocalDBTPlugin uses SQLFluff for SQL style validation
  - DBTFusionPlugin uses built-in static analysis (30x faster)
  - DBTCloudPlugin uses dbt Cloud linting API (future)
- **PolicyEnforcer responsibility**: Validate that linting was executed and policy was enforced
  - Check linting results exist
  - Enforce platform linting policy (error/warning/disabled)
  - Block compilation if linting errors exist and policy=error

**Acceptance Criteria**:
- [ ] PolicyEnforcer.validate_sql_linting_policy() checks DBTPlugin linting was executed
- [ ] Validates linting results against platform-manifest.yaml policy (error/warning/disabled)
- [ ] If policy=error and linting errors exist → block compilation
- [ ] If policy=warning and linting errors exist → log warnings, continue
- [ ] If policy=disabled → skip linting validation
- [ ] Reports linting violations with file path, line number, rule code

**Enforcement**:
- SQL linting policy validation tests
- Enforcement level tests (error/warning/disabled)
- Integration tests with DBTPlugin.lint_project()

**Constraints**:
- MUST NOT implement SQL linting (that's DBTPlugin's responsibility)
- MUST validate linting policy enforcement
- FORBIDDEN to bypass linting when policy=error
- MUST support platform-configured enforcement levels

**Example Configuration (platform-manifest.yaml)**:
```yaml
plugins:
  dbt_compiler:
    provider: fusion  # or local
    config:
      sql_linting:
        enabled: true
        enforcement: error  # error | warning | disabled
        rules:
          max_line_length: 100
```

**Example PolicyEnforcer Validation**:
```python
def validate_sql_linting_policy(
    self,
    lint_result: ProjectLintResult,
    policy: SQLLintingPolicy
) -> None:
    """Validate SQL linting policy compliance."""
    if policy.enforcement == "disabled":
        return

    if policy.enforcement == "error" and not lint_result.passed:
        raise CompilationError(
            f"SQL linting failed with {lint_result.errors} errors. "
            f"Fix issues or set enforcement=warning."
        )

    if policy.enforcement == "warning" and not lint_result.passed:
        logger.warning(
            f"SQL linting found {lint_result.errors} errors, "
            f"{lint_result.warnings} warnings"
        )
```

**Test Coverage**: `tests/integration/test_sql_linting_policy.py`

**Traceability**:
- platform-enforcement.md
- ADR-0009 (dbt Owns SQL)
- ADR-0043 (dbt Compilation Abstraction)
- **Cross-reference**: REQ-097 (SQLFluff integration in LocalDBTPlugin)
- **Cross-reference**: REQ-098 (Fusion static analysis in DBTFusionPlugin)
- **Cross-reference**: REQ-099 (Platform linting configuration)

**Files to Create**:
- `floe-core/src/floe_core/validators/sql_linting_policy_validator.py`

**Related Requirements**:
- **REQ-097**: SQLFluff integration (DBTPlugin owns SQL linting)
- **REQ-098**: dbt Fusion static analysis (alternative SQL linting)
- **REQ-099**: Platform-configurable linting enforcement levels
- **REQ-100**: Pre-compilation linting hook in OrchestratorPlugin

---

### REQ-207: Great Expectations Integration **[New]**

**Requirement**: DataQualityPlugin MUST support Great Expectations for data quality validation at both compile-time and runtime.

**Rationale**: Enables sophisticated quality checks beyond dbt tests through unified quality plugin interface.

**Acceptance Criteria**:
**Compile-Time** (via DataQualityPlugin.validate_config()):
- [ ] Validate Great Expectations expectation suite YAML syntax
- [ ] Validate expectation types are valid (table, column, multicolumn)
- [ ] Validate column references exist in dbt manifest
- [ ] Validate configuration completeness
- [ ] Report configuration errors clearly

**Runtime** (via DataQualityPlugin.execute_checks()):
- [ ] Execute GX expectations against live data
- [ ] Support table, column, and multicolumn expectations
- [ ] Emit OpenLineage FAIL events on violations
- [ ] Return QualityCheckResult with pass/fail per expectation

**Enforcement**:
- Great Expectations plugin implementation tests
- Compile-time config validation tests
- Runtime execution tests with real data
- OpenLineage integration tests

**Constraints**:
- MUST separate compile-time (config) and runtime (data) validation
- MUST NOT execute GX validations at compile-time (no data access)
- MUST report GX errors clearly with context
- MUST support custom GX expectation suites

**Test Coverage**:
- `plugins/floe-dq-great-expectations/tests/unit/test_config_validation.py`
- `plugins/floe-dq-great-expectations/tests/integration/test_runtime_execution.py`

**Traceability**:
- ADR-0044 (Unified Data Quality Plugin Architecture)
- ADR-0012 (Data Classification and Governance)
- Epic 7: Great Expectations Implementation

---

### REQ-208: Policy Violation Reporting **[New]**

**Requirement**: PolicyEnforcer MUST report policy violations with severity levels and remediation guidance.

**Rationale**: Clear error messages enable quick compliance.

**Acceptance Criteria**:
- [ ] Violations include severity: ERROR (blocking), WARNING (non-blocking), INFO (informational)
- [ ] Error messages include: violation code, description, resolution
- [ ] Suggests fixes (e.g., naming suggestions for violated conventions)
- [ ] Groups violations by category (naming, classification, quality, contracts)
- [ ] Formatted output suitable for CI/CD logs

**Enforcement**:
- Error message formatting tests
- Severity level tests
- Remediation suggestion tests

**Constraints**:
- MUST NOT suppress violations in strict mode
- MUST provide actionable remediation
- FORBIDDEN to blame data engineers for platform policies
- MUST reference documentation for policy details

**Test Coverage**: `tests/unit/test_violation_reporting.py`

**Traceability**:
- platform-enforcement.md lines 223-243

---

### REQ-209: Policy Override Prevention **[New]**

**Requirement**: System MUST prevent data engineers from overriding platform policies (no escape hatches in strict mode).

**Rationale**: Ensures governance is non-negotiable in production.

**Acceptance Criteria**:
- [ ] No floe.yaml directive to override platform policies
- [ ] No environment variable to disable governance
- [ ] No CLI flag to bypass validation (except --dry-run for testing)
- [ ] Compilation fails definitively on policy violation in strict mode
- [ ] Policy decisions only made by platform team

**Enforcement**:
- Override prevention tests
- Configuration override tests
- CLI bypass prevention tests

**Constraints**:
- MUST NOT provide override mechanisms in strict mode
- FORBIDDEN to add --skip-validation or similar flags
- MUST require policy updates through proper governance channels
- FORBIDDEN to allow secrets/credentials to bypass policies

**Test Coverage**: `tests/integration/test_override_prevention.py`

**Traceability**:
- platform-enforcement.md
- ADR-0016 (Platform Enforcement Architecture)

---

### REQ-210: Runtime Policy Enforcement Hooks **[New]**

**Requirement**: System MUST provide hooks for runtime policy enforcement in orchestrator plugins.

**Rationale**: Enables runtime validation beyond compile-time checks.

**Acceptance Criteria**:
- [ ] OrchestratorPlugin can invoke PolicyEnforcer at job execution time
- [ ] Runtime hooks available for: job_start, job_complete, task_failure
- [ ] Hooks receive job metadata and can emit observability events
- [ ] Violations logged via OpenTelemetry and OpenLineage
- [ ] Violations do not block job execution (monitoring only)

**Enforcement**:
- Runtime hook tests
- Orchestrator plugin hook tests
- Observability integration tests

**Constraints**:
- MUST NOT block job execution on runtime violations
- MUST log violations with full context
- FORBIDDEN to modify job behavior based on policy
- MUST emit OpenLineage FAIL events on violations

**Test Coverage**: `tests/integration/test_runtime_hooks.py`

**Traceability**:
- ADR-0016 (Platform Enforcement Architecture)

---

### REQ-211: Platform Identity Validation **[New]**

**Requirement**: PolicyEnforcer MUST validate product identity to prevent namespace collisions in distributed environments.

**Rationale**: Ensures multiple teams can independently create data products without naming conflicts.

**Acceptance Criteria**:
- [ ] validate_product_identity() prevents namespace registration conflicts
- [ ] Namespace format: {domain}.{product}
- [ ] Atomic registration prevents race conditions
- [ ] Catalog properties store: floe.product.name, floe.product.repo, floe.product.owner
- [ ] Clear error messages on conflict with resolution guidance

**Enforcement**:
- Identity validation tests
- Race condition prevention tests
- Catalog property tests

**Constraints**:
- MUST use atomic catalog operations (compare-and-swap)
- MUST prevent concurrent registration conflicts
- FORBIDDEN to allow namespace takeover
- MUST require repository proof (git URL)

**Test Coverage**: `tests/integration/test_product_identity.py`

**Traceability**:
- platform-enforcement.md lines 422-537
- ADR-0030 (Namespace-Based Identity)

---

### REQ-212: Policy Configuration via platform-manifest **[New]**

**Requirement**: Platform team MUST define all policies in platform-manifest.yaml (governance section).

**Rationale**: Single source of truth for platform policies.

**Acceptance Criteria**:
- [ ] Manifest schema includes governance section
- [ ] Governance section: classification, policies, quality_gates, data_contracts
- [ ] All policy enforcement levels configurable
- [ ] Policies inherited by domain/product manifests
- [ ] Manifest validation via Pydantic schemas

**Enforcement**:
- Manifest schema validation tests
- Governance section parsing tests
- Policy inheritance tests

**Constraints**:
- MUST define policies in manifest, not elsewhere
- MUST NOT allow policies in floe.yaml
- FORBIDDEN to scatter policies across multiple files
- MUST validate policy syntax at manifest compile time

**Test Coverage**: `tests/unit/test_governance_manifest.py`

**Traceability**:
- platform-enforcement.md lines 14-49
- ADR-0016 (Platform Enforcement Architecture)

**Files to Update**:
- `floe-core/src/floe_core/schemas.py` - Add GovernanceConfig schema

---

### REQ-213: Layer-Specific Quality Requirements **[New]**

**Requirement**: PolicyEnforcer MUST support layer-specific quality gate requirements (bronze, silver, gold).

**Rationale**: Different layers have different data quality expectations.

**Acceptance Criteria**:
- [ ] Quality gates configurable per layer
- [ ] Bronze: minimal requirements (freshness, not null for PKs)
- [ ] Silver: medium requirements (documentation, foreign key tests)
- [ ] Gold: strict requirements (100% test coverage, documentation)
- [ ] PolicyEnforcer assigns layer based on naming convention
- [ ] Quality violations reported with layer-specific remediation

**Enforcement**:
- Layer quality validation tests
- Per-layer requirement tests
- Remediation suggestion tests

**Constraints**:
- MUST support configurable per-layer rules
- MUST NOT allow gold-layer models with bronze-level quality
- FORBIDDEN to apply same requirements to all layers
- MUST enforce quality escalation

**Test Coverage**: `tests/unit/test_layer_quality_gates.py`

**Traceability**:
- ADR-0012 (Data Classification and Governance) lines 211-244
- ADR-0021 (Data Architecture Patterns)

---

### REQ-214: Compile-Time Validation Summary **[New]**

**Requirement**: Compiler output MUST include summary of all validation checks performed by PolicyEnforcer.

**Rationale**: Audit trail and transparency of governance enforcement.

**Acceptance Criteria**:
- [ ] Compilation summary includes validation checks performed
- [ ] Summary shows: policies checked, violations found, enforcement level
- [ ] Example: "Naming enforcement: PASS (24 models checked)"
- [ ] Summary output suitable for CI/CD logs and reports
- [ ] JSON output format available for parsing

**Enforcement**:
- Summary generation tests
- Output format tests
- CI/CD integration tests

**Constraints**:
- MUST include all validation checks
- MUST NOT hide failures in summary
- FORBIDDEN to omit violation count
- MUST include enforcement level in summary

**Test Coverage**: `tests/unit/test_validation_summary.py`

**Traceability**:
- platform-enforcement.md lines 75-99

---

### REQ-215: Policy Exception Handling **[New]**

**Requirement**: PolicyEnforcer MUST fail gracefully with clear error messages when policy validation encounters unexpected conditions.

**Rationale**: Prevents opaque failures and enables debugging.

**Acceptance Criteria**:
- [ ] PolicyEnforcer exceptions inherit from FloeError
- [ ] Exception messages include: policy type, model name, violation reason
- [ ] dbt manifest parsing errors reported clearly
- [ ] Classification metadata parsing errors reported clearly
- [ ] Graceful degradation if optional validations unavailable

**Enforcement**:
- Exception handling tests
- Error message clarity tests
- Degradation mode tests

**Constraints**:
- MUST NOT swallow exceptions silently
- MUST include context in error messages
- FORBIDDEN to expose stack traces to end users
- MUST suggest next steps in error message

**Test Coverage**: `tests/unit/test_policy_exceptions.py`

**Traceability**:
- ADR-0025 (Exception Handling)

---

### REQ-216: Test Coverage Enforcement **[New]**

**Requirement**: PolicyEnforcer MUST validate that dbt models have sufficient test coverage (minimum_test_coverage from manifest).

**Rationale**: Ensures data quality through automated testing.

**Acceptance Criteria**:
- [ ] Enforces minimum_test_coverage percentage from manifest
- [ ] Calculates: tested_columns / total_columns × 100
- [ ] Reports coverage per model and per layer
- [ ] Suggestions for missing tests (not_null, unique, freshness)
- [ ] Enforces layer-specific coverage requirements

**Enforcement**:
- Test coverage calculation tests
- Enforcement threshold tests
- Coverage report tests

**Constraints**:
- MUST count only valid dbt tests
- MUST NOT count tests on documentation only
- FORBIDDEN to allow incomplete test coverage in strict mode
- MUST support per-column test tracking

**Test Coverage**: `tests/unit/test_coverage_enforcement.py`

**Traceability**:
- ADR-0012 (Data Classification and Governance) lines 211-331

---

### REQ-217: Documentation Validation **[New]**

**Requirement**: PolicyEnforcer MUST validate that models and columns have required documentation.

**Rationale**: Documentation is governance artifact for compliance.

**Acceptance Criteria**:
- [ ] Validates model descriptions exist (dbt description field)
- [ ] Validates column descriptions exist for sensitive columns
- [ ] Enforces documentation for gold-layer models
- [ ] Reports missing documentation with suggestions
- [ ] Integrates with dbt model YAML structure

**Enforcement**:
- Documentation presence tests
- Description quality tests
- Layer-specific tests

**Constraints**:
- MUST require documentation for gold layers
- MUST NOT allow empty descriptions ("TBD")
- FORBIDDEN to enforce documentation for bronze/silver unless policy-specified
- MUST validate dbt YAML structure

**Test Coverage**: `tests/unit/test_documentation_validation.py`

**Traceability**:
- ADR-0012 (Data Classification and Governance)

---

### REQ-218: Custom Policy Plugins **[New]**

**Requirement**: PolicyEnforcer MUST be extensible to support custom policy implementations via pluggable validators.

**Rationale**: Enables platform teams to add organization-specific policies.

**Acceptance Criteria**:
- [ ] PolicyValidator plugin interface defined
- [ ] PolicyValidator methods: validate_policy_rule, get_policy_name
- [ ] PolicyEnforcer loads validators from entry points (floe.policy_validators)
- [ ] Custom validators receive DataProduct + Manifest context
- [ ] Exceptions from validators propagated with context

**Enforcement**:
- Plugin loading tests
- Custom validator tests
- Exception propagation tests

**Constraints**:
- MUST support custom validators via entry points
- MUST NOT break if custom validator unavailable
- FORBIDDEN to hardcode policies
- MUST provide clear API for custom validators

**Test Coverage**: `tests/unit/test_custom_policy_plugins.py`

**Traceability**:
- ADR-0016 (Platform Enforcement Architecture)

---

### REQ-219: Policy Audit Trail **[New]**

**Requirement**: All policy enforcement decisions MUST be logged with structured context for audit purposes.

**Rationale**: Compliance and debugging.

**Acceptance Criteria**:
- [ ] All PolicyEnforcer calls logged with: policy_type, model_name, result, timestamp
- [ ] Violations logged with: violation_code, severity, remediation
- [ ] Structured logging format (JSON compatible)
- [ ] Logs include manifest version and product identity
- [ ] Audit logs distinct from debug logs

**Enforcement**:
- Audit logging tests
- Structured format tests
- Log completeness tests

**Constraints**:
- MUST log all policy decisions
- MUST NOT log sensitive data
- FORBIDDEN to omit violation details
- MUST include timestamp and user context

**Test Coverage**: `tests/unit/test_policy_audit_trail.py`

**Traceability**:
- security.md (Logging Standards)

---

### REQ-220: Enforcement Level Compliance **[New]**

**Requirement**: PolicyEnforcer MUST respect enforcement levels (off, warn, strict) defined in manifest.

**Rationale**: Enables gradual policy rollout and experimentation.

**Acceptance Criteria**:
- [ ] off: No enforcement, no errors, no warnings
- [ ] warn: Log violations, continue compilation
- [ ] strict: Block compilation on violations (return errors)
- [ ] Enforcement level configurable per-policy
- [ ] Violations reported consistently across levels

**Enforcement**:
- Enforcement level tests
- Per-policy level tests
- Compilation outcome tests

**Constraints**:
- MUST respect enforcement levels from manifest
- FORBIDDEN to ignore manifest level settings
- MUST apply consistent severity across all policies
- FORBIDDEN to have side effects based on enforcement level

**Test Coverage**: `tests/unit/test_enforcement_levels.py`

**Traceability**:
- platform-enforcement.md lines 170-182
- ADR-0016 (Platform Enforcement Architecture)

---

## Domain Acceptance Criteria

Policy Enforcement and Validation (REQ-200 to REQ-220) is complete when:

- [ ] All 21 requirements have complete template fields
- [ ] PolicyEnforcer ABC defined and documented
- [ ] All 11 enforcement methods implemented
- [ ] dbt-checkpoint integration working
- [ ] SQLFluff integration working
- [ ] Great Expectations integration working
- [ ] Compile-time validation hook implemented
- [ ] Unit tests pass with >80% coverage
- [ ] Integration tests validate governance workflows
- [ ] Contract tests validate plugin boundaries
- [ ] Documentation updated:
  - [ ] platform-enforcement.md backreferences requirements
  - [ ] ADR-0012 backreferences requirements
  - [ ] ADR-0016 backreferences requirements
  - [ ] ADR-0021 backreferences requirements

## Epic Mapping

These requirements are satisfied in **Epic 6: Governance Foundation**:
- Phase 1: Define PolicyEnforcer interface
- Phase 2: Implement compile-time validation hooks
- Phase 3: Integrate dbt-checkpoint, SQLFluff, Great Expectations
- Phase 4: Enable custom policy plugins
