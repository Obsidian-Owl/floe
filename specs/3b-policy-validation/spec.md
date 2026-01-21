# Feature Specification: Policy Validation Enhancement

**Epic**: 3B (Policy Validation)
**Feature Branch**: `3b-policy-validation`
**Created**: 2026-01-20
**Status**: Draft
**Input**: User description: "floe-03b-policy-validation - ensure you deeply understand the architecture as well as the current state of policy implementation in the codebase"

## Context: Current State

Epic 3A (Policy Enforcer) is complete and provides the foundation:

**Implemented in `packages/floe-core/src/floe_core/enforcement/`:**
- `PolicyEnforcer` - Core orchestrator that coordinates validators
- `NamingValidator` - Validates model names against medallion/kimball/custom patterns
- `CoverageValidator` - Validates column-level test coverage against thresholds
- `DocumentationValidator` - Validates model/column descriptions
- `Violation`, `EnforcementResult`, `EnforcementSummary` - Result models
- Error codes: FLOE-E201 (naming), FLOE-E210/E211 (coverage), FLOE-E220-E222 (documentation)

**Architecture (ADR-0015):**
- PolicyEnforcer is a CORE MODULE, not a plugin (rules are configuration, not implementations)
- Operates at compile-time on dbt manifest.json
- Three enforcement levels: off, warn, strict
- Supports dry-run mode for impact preview

**What Epic 3B Adds:**
Epic 3B extends the validation framework with advanced rules, better error handling, custom policy extension points, and tighter compilation pipeline integration.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Semantic Model Validation (Priority: P1)

As a Platform Engineer, I want to validate semantic relationships between models (e.g., foreign key references, dependency ordering) so that data contracts are enforced at compile-time.

**Why this priority**: Semantic validation catches data model issues that naming/coverage checks miss. These are critical for data quality and cross-team collaboration.

**Independent Test**: Can be fully tested by running `floe compile` on a dbt project with misconfigured relationships and verifying FLOE-E3xx errors are generated with actionable suggestions.

**Acceptance Scenarios**:

1. **Given** a model references another model via `ref()`, **When** the referenced model doesn't exist in the manifest, **Then** a FLOE-E301 error is generated with the missing model name and suggestion.
2. **Given** a model has a circular dependency, **When** validation runs, **Then** a FLOE-E302 error identifies all models in the cycle.
3. **Given** a model uses `source()` referencing an undefined source, **When** validation runs, **Then** a FLOE-E303 error identifies the undefined source.

---

### User Story 2 - Custom Policy Rules via Configuration (Priority: P1)

As a Platform Engineer, I want to define custom validation rules in `manifest.yaml` using declarative configuration so that I can enforce organization-specific policies without writing Python code.

**Why this priority**: Organizations have unique standards (e.g., "all gold_ models must have tags", "models in marts/ must have freshness tests"). Custom rules enable self-service governance.

**Independent Test**: Can be fully tested by adding custom_rules to manifest.yaml governance section and verifying PolicyEnforcer applies them correctly.

**Acceptance Scenarios**:

1. **Given** a custom rule `require_tags_for_prefix: ["gold_"]`, **When** a gold_customers model has no tags, **Then** a FLOE-E400 error is generated.
2. **Given** a custom rule `require_meta_field: ["owner"]`, **When** a model is missing the `owner` meta field, **Then** a FLOE-E401 error identifies the model and missing field.
3. **Given** a custom rule with invalid syntax, **When** manifest is loaded, **Then** a ValidationError is raised with clear syntax guidance.

---

### User Story 3 - Severity Overrides (Priority: P2)

As a Data Engineer, I want to override violation severity for specific models or patterns so that legacy models can be gradually migrated to compliance.

**Why this priority**: Real-world migrations require flexibility. Blocking all violations immediately prevents incremental adoption.

**Independent Test**: Can be fully tested by adding override rules to governance config and verifying specific models bypass strict enforcement.

**Acceptance Scenarios**:

1. **Given** an override with `pattern: "legacy_*"` and `action: downgrade`, **When** a legacy_orders model fails naming, **Then** severity is downgraded to warning (not error).
2. **Given** an override with `pattern: "test_*"` and `action: exclude`, **When** a test_fixture model is validated, **Then** it is skipped entirely (no violation generated).
3. **Given** an override with an `expires` date, **When** the date passes, **Then** the override is ignored and full enforcement applies.

---

### User Story 4 - Detailed Violation Context (Priority: P2)

As a Data Engineer, I want violations to include rich context (affected downstream models, historical compliance, related violations) so that I can prioritize fixes effectively.

**Why this priority**: Context helps engineers understand impact. "This model has 15 downstream dependents" is more actionable than just "naming violation".

**Independent Test**: Can be fully tested by generating violations and verifying context fields are populated correctly from manifest data.

**Acceptance Scenarios**:

1. **Given** a model has naming violation and downstream dependents, **When** the violation is generated, **Then** it includes `downstream_impact: ["model_a", "model_b", ...]`.
2. **Given** a model had compliance issues in previous runs, **When** a new violation is generated, **Then** it includes `first_detected` timestamp and `occurrences` count.
3. **Given** multiple violations affect the same model, **When** results are returned, **Then** violations are grouped by model with a summary.

---

### User Story 5 - Validation Report Export (Priority: P3)

As a Platform Engineer, I want to export validation results in multiple formats (JSON, SARIF, HTML) so that results integrate with CI/CD tools and dashboards.

**Why this priority**: Integration with existing tooling (GitHub Code Scanning, SonarQube, dashboards) enables automated governance.

**Independent Test**: Can be fully tested by running validation and exporting to each format, verifying output matches expected schema.

**Acceptance Scenarios**:

1. **Given** validation completes with violations, **When** `--output-format=sarif` is specified, **Then** output conforms to SARIF 2.1.0 schema for GitHub Code Scanning integration.
2. **Given** validation completes, **When** `--output-format=html` is specified, **Then** a human-readable HTML report is generated with violation details and charts.
3. **Given** validation completes, **When** `--output-format=json` is specified, **Then** output matches EnforcementResult JSON schema.

---

### Edge Cases

- **Malformed manifest**: System validates dbt manifest structure at load time. Unsupported versions (pre-dbt 1.0) raise ValidationError with clear message.
- **Custom rule conflicts**: Custom rules run AFTER built-in rules. They add violations, they cannot suppress built-in violations. No conflict possible.
- **Override patterns match nothing**: System logs a warning "Override pattern 'xyz' matched 0 models" for visibility but does not fail.
- **Duplicate violations**: Violations are deduplicated by (model_name, error_code, column_name) tuple before being added to results.
- **Export directory missing**: System creates output directory if it doesn't exist (FR-023). Permission errors raise IOError with path info.

---

## Requirements *(mandatory)*

### Functional Requirements

**Semantic Validation (US1)**

- **FR-001**: System MUST validate model references (via `ref()`) resolve to existing models in the manifest
- **FR-002**: System MUST detect circular dependencies between models and report the cycle path
- **FR-003**: System MUST validate source references (via `source()`) resolve to defined sources
- **FR-004**: System MUST assign error codes FLOE-E301, FLOE-E302, FLOE-E303 for semantic violations

**Custom Policy Rules (US2)**

- **FR-005**: System MUST support `custom_rules` configuration section in manifest.yaml governance block
- **FR-006**: System MUST support rule type `require_tags_for_prefix` to enforce tags on models matching prefix patterns
- **FR-007**: System MUST support rule type `require_meta_field` to enforce specific meta fields on all/filtered models
- **FR-008**: System MUST support rule type `require_tests_of_type` to enforce specific test types (not_null, unique, etc.)
- **FR-009**: System MUST validate custom rule syntax at manifest load time and provide clear error messages
- **FR-010**: System MUST assign error codes FLOE-E4xx for custom rule violations

**Severity Overrides (US3)**

- **FR-011**: System MUST support `policy_overrides` configuration section for exception handling
- **FR-012**: System MUST support `action: downgrade` to convert error-severity violations to warnings for matched patterns
- **FR-013**: System MUST support `action: exclude` to skip validation entirely for matched patterns
- **FR-014**: System MUST support `expires` date field after which overrides are ignored
- **FR-015**: System MUST log warnings when overrides are applied for audit purposes

**Violation Context (US4)**

- **FR-016**: Violation model MUST include optional `downstream_impact` field listing affected downstream models
- **FR-017**: Violation model MUST include optional `first_detected` timestamp for historical tracking
- **FR-018**: EnforcementResult MUST include `violations_by_model` grouping for easier consumption
- **FR-019**: System MUST populate downstream_impact by traversing manifest parent_map/child_map

**Report Export (US5)**

- **FR-020**: System MUST support `--output-format` CLI flag with values: json, sarif, html
- **FR-021**: SARIF output MUST conform to SARIF 2.1.0 schema for GitHub Code Scanning integration
- **FR-022**: HTML output MUST include violation summary, charts, and detailed violation list
- **FR-023**: System MUST create output directory if it doesn't exist

**Pipeline Integration**

- **FR-024**: PolicyEnforcer.enforce() MUST be callable from compilation pipeline (floe_core.compilation.stages)
- **FR-025**: Enforcement results MUST be stored in CompiledArtifacts for downstream consumption
- **FR-026**: `floe compile` MUST fail with non-zero exit code when enforcement fails and block_on_failure=true

### Key Entities

- **CustomRule**: Represents a user-defined validation rule with type, target (model pattern), parameters
- **PolicyOverride**: Represents an exception to normal enforcement with pattern, action (downgrade/exclude), expiration
- **ViolationContext**: Extended violation metadata including downstream_impact, first_detected, occurrences
- **ValidationReport**: Export-ready representation of EnforcementResult in specified format

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 5 built-in validators (naming, coverage, documentation, semantic, custom) execute in under 500ms for manifests with 500 models (excludes lazy downstream_impact computation)
- **SC-002**: Custom rules can be added to manifest.yaml without code changes, validated by configuration-only test suite
- **SC-003**: SARIF export integrates with GitHub Code Scanning, verified by successful upload in CI workflow
- **SC-004**: 100% of violations include actionable suggestions (no violation without suggestion field)
- **SC-005**: Override patterns achieve 100% accuracy (no false positives/negatives) verified by unit tests with edge cases

---

## Assumptions

1. Epic 3A PolicyEnforcer implementation is stable and can be extended (not replaced)
2. Custom rules are applied AFTER built-in rules (order: naming -> coverage -> documentation -> semantic -> custom). This ordering prevents conflicts - custom rules cannot override built-in rule results.
3. SARIF export targets SARIF 2.1.0 (current GitHub standard)
4. Override expiration uses ISO-8601 date format (YYYY-MM-DD)
5. Downstream impact is computed lazily (only when requested) for performance
6. Manifest.yaml governance schema can be extended without breaking existing configurations
7. `first_detected` and `occurrences` fields are schema placeholders in v1 (always None). Historical tracking requires persistent state and will be implemented in a future version.
8. HTML report "charts" refers to inline summary tables/statistics, not external charting libraries. No JavaScript dependencies required.
