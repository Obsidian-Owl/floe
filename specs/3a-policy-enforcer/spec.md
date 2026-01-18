# Feature Specification: Policy Enforcer Core

**Epic**: 3A (Policy Enforcer)
**Feature Branch**: `3a-policy-enforcer`
**Created**: 2026-01-19
**Status**: Draft
**Input**: User description: "Epic 3A: Policy Enforcer Core - Compile-time governance enforcement engine for validating data products against platform-defined policies"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Policy Evaluation at Compile Time (Priority: P1)

A platform operator defines governance policies in their manifest.yaml (naming conventions, test coverage thresholds, documentation requirements). When a data engineer runs `floe compile`, the PolicyEnforcer validates the dbt manifest against these policies and blocks compilation if violations exist in strict mode.

**Why this priority**: This is the core value proposition - ensuring non-compliant pipelines fail before runtime, preventing governance violations from reaching production.

**Independent Test**: Can be fully tested by compiling a dbt project with known policy violations and verifying compilation fails with actionable error messages.

**Acceptance Scenarios**:

1. **Given** a manifest.yaml with `governance.naming.enforcement: strict` and `governance.naming.pattern: medallion`, **When** a data engineer compiles a project with model `stg_payments` (violates medallion naming), **Then** compilation fails with error code FLOE-E201 including the expected pattern, actual value, and remediation suggestion.

2. **Given** a manifest.yaml with `governance.quality_gates.minimum_test_coverage: 80`, **When** a data engineer compiles a project where model `customers` has 50% test coverage, **Then** compilation fails with a clear error stating the coverage gap and which tests to add.

3. **Given** a manifest.yaml with `governance.policy_enforcement_level: warn`, **When** the same violations occur, **Then** compilation succeeds but logs warnings with full violation details.

---

### User Story 2 - Policy Configuration via Manifest (Priority: P1)

Platform teams define all governance policies in the manifest.yaml `governance` section. These policies are inherited by domain and data product manifests following the 3-tier inheritance model where child manifests can only strengthen (never weaken) parent policies.

**Why this priority**: Single source of truth for platform policies is foundational - without proper configuration, enforcement cannot occur.

**Independent Test**: Can be fully tested by creating enterprise → domain → product manifest chains and validating inheritance rules.

**Acceptance Scenarios**:

1. **Given** an enterprise manifest with `governance.quality_gates.minimum_test_coverage: 80`, **When** a domain manifest attempts to set `minimum_test_coverage: 60`, **Then** validation fails with SecurityPolicyViolationError indicating the policy cannot be weakened.

2. **Given** an enterprise manifest with `governance.naming.enforcement: warn`, **When** a domain manifest sets `governance.naming.enforcement: strict`, **Then** validation succeeds because strict > warn (strengthening allowed).

3. **Given** a complete governance configuration, **When** the manifest is loaded, **Then** the GovernanceConfig Pydantic model validates all fields with proper types and constraints.

---

### User Story 3 - Naming Convention Enforcement (Priority: P2)

Platform teams enforce naming conventions (medallion, kimball, or custom patterns) to ensure consistent data architecture. The PolicyEnforcer validates model names match the configured pattern and provides migration suggestions for violations.

**Why this priority**: Naming conventions enable automated classification, governance, and data mesh organization - critical for scaling data platforms.

**Independent Test**: Can be fully tested by validating models against each naming pattern and verifying correct pass/fail behavior with actionable suggestions.

**Acceptance Scenarios**:

1. **Given** `governance.naming.pattern: medallion`, **When** validating model names, **Then** `bronze_orders`, `silver_customers`, `gold_revenue` pass while `stg_payments`, `dim_product` fail.

2. **Given** `governance.naming.pattern: kimball`, **When** validating model names, **Then** `dim_customer`, `fact_orders`, `bridge_order_product` pass while `bronze_orders` fails.

3. **Given** `governance.naming.pattern: custom` with `custom_patterns: ["^raw_.*$", "^clean_.*$", "^agg_.*$"]`, **When** validating model names, **Then** models matching any pattern pass.

---

### User Story 4 - Test Coverage Enforcement (Priority: P2)

Platform teams enforce minimum test coverage (percentage of columns with dbt tests) per model and per layer. The PolicyEnforcer calculates coverage and reports gaps with suggestions for missing tests.

**Why this priority**: Automated testing is the primary defense against data quality issues - enforcing coverage ensures data reliability.

**Independent Test**: Can be fully tested by calculating coverage from a dbt manifest and verifying threshold enforcement.

**Acceptance Scenarios**:

1. **Given** `governance.quality_gates.minimum_test_coverage: 80` and a model with 10 columns where 6 have tests, **When** PolicyEnforcer validates, **Then** it fails with "60% coverage (6/10 columns) - requires 80%".

2. **Given** layer-specific requirements (`bronze: 50`, `silver: 80`, `gold: 100`), **When** validating a gold-layer model with 95% coverage, **Then** validation fails with guidance to achieve 100%.

3. **Given** a model passing coverage requirements, **When** PolicyEnforcer validates, **Then** the validation summary shows "Test coverage: PASS (85% >= 80%)".

---

### User Story 5 - Documentation Validation (Priority: P2)

Platform teams require documentation (model descriptions, column descriptions) at configurable levels. The PolicyEnforcer validates dbt YAML has required descriptions and reports missing documentation with templates.

**Why this priority**: Documentation is a governance artifact required for compliance, discoverability, and onboarding - essential for data mesh adoption.

**Independent Test**: Can be fully tested by validating dbt manifests with varying documentation completeness.

**Acceptance Scenarios**:

1. **Given** `governance.quality_gates.require_descriptions: true`, **When** validating a model without a description field, **Then** validation fails with "Model 'customers' missing description".

2. **Given** `governance.quality_gates.require_column_descriptions: true` for gold-layer models, **When** validating a gold model where column `email` lacks description, **Then** validation fails with "Column 'customers.email' missing description".

3. **Given** a model with descriptions that are placeholder text ("TBD", "TODO"), **When** PolicyEnforcer validates, **Then** these are treated as missing documentation.

---

### User Story 6 - Audit Logging for Compliance (Priority: P3)

All policy enforcement decisions are logged with structured context (policy type, model name, result, timestamp) for audit and compliance purposes. Logs integrate with OpenTelemetry traces.

**Why this priority**: Audit trails are required for compliance in regulated industries and for debugging governance issues.

**Independent Test**: Can be fully tested by running policy validation and verifying structured log output contains all required fields.

**Acceptance Scenarios**:

1. **Given** PolicyEnforcer is configured with audit logging, **When** any validation runs, **Then** structured logs include: `policy_type`, `model_name`, `result`, `timestamp`, `manifest_version`, `enforcement_level`.

2. **Given** a violation occurs, **When** logged, **Then** the log includes: `violation_code`, `severity`, `remediation`, `documentation_url`.

3. **Given** OpenTelemetry is configured, **When** PolicyEnforcer runs, **Then** validation spans are emitted with policy context as span attributes.

---

### User Story 7 - Dry-Run Mode for Policy Testing (Priority: P3)

Platform operators can test policies before enforcing them using `floe compile --dry-run` which shows what would be enforced without blocking compilation.

**Why this priority**: Safe rollout of new policies requires preview capability - prevents accidentally breaking existing workflows.

**Independent Test**: Can be fully tested by running dry-run compilation and verifying violations are reported but compilation succeeds.

**Acceptance Scenarios**:

1. **Given** `--dry-run` flag is passed to `floe compile`, **When** policy violations exist, **Then** all violations are reported but compilation completes with exit code 0.

2. **Given** a new policy is being added, **When** platform operator runs dry-run, **Then** they see which existing models would fail the new policy.

---

### Edge Cases

- What happens when dbt manifest parsing fails? PolicyEnforcer gracefully reports the parsing error with file location and suggestions.
- What happens when a model has zero columns? Coverage calculation handles division by zero (reports 100% or N/A as configured).
- What happens when governance config is missing from manifest? PolicyEnforcer uses default enforcement level (warn) and logs warning about missing config.
- What happens when custom naming patterns have invalid regex? Manifest validation fails at load time with regex syntax error details.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define PolicyEnforcer as a core module (not plugin) in `packages/floe-core/src/floe_core/enforcement/` with methods: `enforce()`, `validate_naming()`, `validate_coverage()`, `validate_documentation()`.

- **FR-002**: System MUST integrate PolicyEnforcer into the compilation pipeline (compiler.py) to validate dbt manifests before artifact generation.

- **FR-003**: PolicyEnforcer MUST enforce naming conventions for three patterns: `medallion` (bronze_*, silver_*, gold_*), `kimball` (dim_*, fact_*, bridge_*), and `custom` (user-defined regex patterns).

- **FR-004**: PolicyEnforcer MUST calculate test coverage at column-level as `(columns_with_at_least_one_test / total_columns) * 100` and enforce against `governance.quality_gates.minimum_test_coverage` threshold. This aligns with the industry-standard dbt-coverage approach where each column either has test coverage (1+ tests) or not.

- **FR-005**: PolicyEnforcer MUST validate model descriptions and column descriptions exist when required by `governance.quality_gates.require_descriptions` and `require_column_descriptions`.

- **FR-006**: System MUST support three enforcement levels: `off` (no validation), `warn` (log violations, continue), `strict` (block compilation on violations).

- **FR-007**: Policy violations MUST include structured error messages with: `error_code`, `message`, `field_name`, `expected`, `actual`, `suggestion`, `severity`, `documentation` URL.

- **FR-008**: System MUST resolve and merge policies from 3-tier hierarchy (enterprise → domain → product) where child manifests can only strengthen parent policies.

- **FR-009**: System MUST prevent policy override mechanisms in strict mode (no CLI flags, env vars, or floe.yaml directives to bypass validation).

- **FR-010**: System MUST log all policy decisions with structured context: `policy_type`, `model_name`, `result`, `timestamp`, `manifest_version` for audit purposes.

- **FR-011**: System MUST provide `--dry-run` mode that reports violations without blocking compilation.

- **FR-012**: PolicyEnforcer MUST support layer-specific quality requirements (different thresholds for bronze, silver, gold layers based on naming convention).

- **FR-013**: Manifest schema MUST include `governance` section with: `naming` (enforcement, pattern, custom_patterns), `quality_gates` (minimum_test_coverage, require_descriptions, require_column_descriptions, block_on_failure).

- **FR-014**: PolicyEnforcer exceptions MUST inherit from FloeError and include context (policy_type, model_name, violation_reason) for debugging.

- **FR-015**: System MUST provide validation summary output showing all checks performed, violations found, and enforcement level per policy category.

### Key Entities *(include if feature involves data)*

- **GovernanceConfig**: Platform governance settings including naming enforcement, quality gates, and enforcement levels. Inheritable with monotonic strengthening constraint.

- **NamingConfig**: Naming convention configuration with pattern type (medallion/kimball/custom), enforcement level, and optional custom regex patterns.

- **QualityGatesConfig**: Quality gate thresholds including minimum test coverage percentage, documentation requirements, and failure behavior.

- **PolicyEnforcer**: Core module that validates dbt manifests against governance configuration. Returns EnforcementResult with violations.

- **EnforcementResult**: Result of policy enforcement containing list of Violation objects, overall pass/fail status, and summary statistics.

- **Violation**: Individual policy violation with error code, severity, model/column reference, expected value, actual value, and remediation suggestion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Platform operators can define governance policies in manifest.yaml and have them enforced at compile time within 5 seconds for projects with up to 500 dbt models.

- **SC-002**: Policy violations produce actionable error messages that enable data engineers to remediate issues without additional documentation lookup in 90% of cases.

- **SC-003**: 3-tier policy inheritance correctly prevents weakening in 100% of test cases (enterprise → domain → product strengthening only).

- **SC-004**: Test coverage calculation matches dbt manifest test counts with 100% accuracy.

- **SC-005**: Dry-run mode allows platform teams to preview policy impact before enforcement, showing all violations without blocking compilation.

- **SC-006**: All policy decisions are logged with complete audit context, enabling compliance teams to trace enforcement history.

- **SC-007**: PolicyEnforcer handles malformed dbt manifests gracefully, reporting parsing errors with file location and recovery suggestions.

## Clarifications

- Q: Which coverage calculation approach should PolicyEnforcer use (column-level, model-level, or hybrid)? A: Column-level coverage (`columns_with_tests / total_columns`) - aligns with industry-standard dbt-coverage tool for granular enforcement.
