# Feature Specification: CLI Unification

**Epic**: 11 (CLI Unification)
**Feature Branch**: `11-cli-unification`
**Created**: 2026-01-20
**Status**: Draft
**Input**: Unify floe CLI architecture by migrating all commands to a single Click-based implementation in floe-core, eliminating conflicting entry points between floe-cli and floe-core packages

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Platform Compile with Enforcement Export (Priority: P1)

As a Platform Team member, I want to run `floe platform compile` with enforcement report options so that I can validate governance policies and export compliance reports in various formats for CI/CD integration.

**Why this priority**: This is the primary blocker for Epic 3B (Policy Validation). Without CLI integration, enforcement reports cannot be generated via the command line, blocking the entire governance validation workflow.

**Independent Test**: Can be fully tested by running `floe platform compile --spec floe.yaml --manifest manifest.yaml --enforcement-report report.sarif --enforcement-format sarif` and verifying the SARIF file is created with valid content.

**Acceptance Scenarios**:

1. **Given** valid floe.yaml and manifest.yaml files exist, **When** I run `floe platform compile --spec floe.yaml --manifest manifest.yaml`, **Then** compilation succeeds and CompiledArtifacts are written to target/compiled_artifacts.json
2. **Given** valid configuration files with enforcement policies defined, **When** I run `floe platform compile --enforcement-report report.json --enforcement-format json`, **Then** an enforcement report is written to the specified path in JSON format
3. **Given** valid configuration with policy violations, **When** I run `floe platform compile --enforcement-report report.sarif --enforcement-format sarif`, **Then** the SARIF report contains violations with rule IDs and help URLs
4. **Given** the output directory does not exist, **When** I specify `--enforcement-report deep/nested/report.html`, **Then** the directories are created and the HTML report is written

---

### User Story 2 - RBAC Command Migration (Priority: P2)

As a Platform Team member, I want to use `floe rbac *` commands from the unified CLI so that all RBAC management (generate, validate, audit, diff) works after CLI unification without changing my existing workflows.

**Why this priority**: RBAC commands are actively used for Kubernetes security management. Breaking these commands would disrupt production workflows.

**Independent Test**: Can be fully tested by running each RBAC subcommand (`floe rbac generate`, `floe rbac validate`, `floe rbac audit`, `floe rbac diff`) and verifying output matches pre-migration behavior.

**Acceptance Scenarios**:

1. **Given** a valid manifest.yaml with RBAC configuration, **When** I run `floe rbac generate --config manifest.yaml`, **Then** RBAC manifests are generated in target/rbac/
2. **Given** generated RBAC manifests exist, **When** I run `floe rbac validate`, **Then** manifests are validated and status is reported
3. **Given** a Kubernetes cluster is accessible, **When** I run `floe rbac audit`, **Then** the audit report shows namespace summaries and security findings
4. **Given** manifests and cluster access, **When** I run `floe rbac diff`, **Then** differences between expected and deployed RBAC are displayed

---

### User Story 3 - Discoverable Command Help (Priority: P2)

As a new floe user, I want to run `floe --help` and see all available command groups organized logically so that I can discover available functionality without reading documentation.

**Why this priority**: CLI discoverability directly impacts user adoption and reduces support burden. A confusing CLI structure leads to user frustration.

**Independent Test**: Can be fully tested by running `floe --help`, `floe platform --help`, and `floe rbac --help` and verifying help text is clear and complete.

**Acceptance Scenarios**:

1. **Given** floe is installed, **When** I run `floe --help`, **Then** I see top-level command groups including `platform` and `rbac`
2. **Given** floe is installed, **When** I run `floe platform --help`, **Then** I see subcommands: compile, test, publish, deploy, status
3. **Given** floe is installed, **When** I run `floe rbac --help`, **Then** I see subcommands: generate, validate, audit, diff
4. **Given** any command, **When** I run it with `--help`, **Then** I see clear descriptions, required/optional arguments, and examples

---

### User Story 4 - Artifact Push Command Migration (Priority: P3)

As a Platform Team member, I want `floe artifact push` to work from the unified CLI so that I can push CompiledArtifacts to OCI registries using the new command structure.

**Why this priority**: Artifact push is part of the CI/CD pipeline but is used less frequently than compile and RBAC commands. Existing argparse implementation can be migrated incrementally.

**Independent Test**: Can be fully tested by running `floe artifact push` with valid artifacts and verifying push succeeds to an OCI registry.

**Acceptance Scenarios**:

1. **Given** CompiledArtifacts exist at target/compiled_artifacts.json, **When** I run `floe artifact push --artifact target/compiled_artifacts.json --registry ghcr.io/org/floe`, **Then** the artifact is pushed to the registry
2. **Given** valid credentials are configured, **When** I run the push command, **Then** authentication succeeds and artifact is uploaded

---

### User Story 5 - Data Team Compile Stub (Priority: P4)

As a Data Engineer, I want a `floe compile` command (distinct from `floe platform compile`) so that I can validate my floe.yaml against platform constraints in the future.

**Why this priority**: Data Team CLI is lower priority for initial unification. Stub implementation acceptable to establish command structure without full implementation.

**Independent Test**: Can be tested by running `floe compile --help` and verifying the command exists with appropriate help text.

**Acceptance Scenarios**:

1. **Given** floe is installed, **When** I run `floe compile --help`, **Then** I see help text indicating this command validates Data Team floe.yaml
2. **Given** floe is installed, **When** I run `floe compile`, **Then** I get the message "This command is not yet implemented. See floe platform compile for Platform Team usage." to stderr with exit code 0

---

### Edge Cases

- What happens when both floe-cli and floe-core packages are installed during transition? The unified CLI should take precedence.
- What happens when a user runs an old command syntax (e.g., `floe compile` instead of `floe platform compile`)? Provide helpful migration message to stderr.
- How does the system handle missing optional dependencies (e.g., kubernetes package for audit/diff)? Plain text error to stderr with install instructions, exit code 1.
- What happens when --enforcement-report path is not writable? Plain text error to stderr before starting compilation, exit code 1.

## Requirements *(mandatory)*

### Functional Requirements

#### Core CLI Structure
- **FR-001**: System MUST provide a single `floe` entry point using Click framework
- **FR-002**: System MUST organize commands into hierarchical groups: `platform`, `rbac`, `artifact`, and root-level data team commands
- **FR-003**: System MUST display consistent, formatted help text for all commands and subcommands
- **FR-004**: System MUST support `--version` flag showing package version
- **FR-005**: System MUST output errors as plain text to stderr with appropriate non-zero exit codes for CI/CD integration

#### Platform Commands (floe platform *)
- **FR-010**: `floe platform compile` MUST accept `--spec` and `--manifest` options for input files
- **FR-011**: `floe platform compile` MUST accept `--output` option for CompiledArtifacts output path (default: target/compiled_artifacts.json)
- **FR-012**: `floe platform compile` MUST accept `--enforcement-report` option for enforcement report output path
- **FR-013**: `floe platform compile` MUST accept `--enforcement-format` option with choices: json, sarif, html
- **FR-014**: `floe platform compile` MUST create parent directories if --enforcement-report path doesn't exist
- **FR-015**: `floe platform compile` MUST return exit code 0 on success, non-zero on failure
- **FR-016**: `floe platform test` MUST exist as a command stub (full implementation deferred)
- **FR-017**: `floe platform publish` MUST exist as a command stub (full implementation deferred)
- **FR-018**: `floe platform deploy` MUST exist as a command stub (full implementation deferred)
- **FR-019**: `floe platform status` MUST exist as a command stub (full implementation deferred)

#### RBAC Commands (floe rbac *)
- **FR-020**: `floe rbac generate` MUST accept `--config`, `--output`, and `--dry-run` options
- **FR-021**: `floe rbac generate` MUST produce YAML manifests for Namespace, ServiceAccount, Role, RoleBinding
- **FR-022**: `floe rbac validate` MUST accept `--config`, `--manifest-dir`, and `--output` (text/json) options
- **FR-023**: `floe rbac validate` MUST return validation status with issue details
- **FR-024**: `floe rbac audit` MUST accept `--namespace`, `--output`, and `--kubeconfig` options
- **FR-025**: `floe rbac audit` MUST report security findings (wildcard permissions, missing resource names)
- **FR-026**: `floe rbac diff` MUST accept `--manifest-dir`, `--namespace`, `--output`, and `--kubeconfig` options
- **FR-027**: `floe rbac diff` MUST show added, removed, and modified resources between expected and deployed

#### Artifact Commands (floe artifact *)
- **FR-030**: `floe artifact push` MUST accept `--artifact` and `--registry` options
- **FR-031**: `floe artifact push` MUST support authentication via environment variables (`FLOE_REGISTRY_USERNAME`, `FLOE_REGISTRY_PASSWORD`) or Docker credential helpers

#### Data Team Commands (floe *)
- **FR-040**: `floe compile` MUST exist as a stub command for Data Team spec validation
- **FR-041**: `floe validate` MUST exist as a stub command for Data Team floe.yaml validation
- **FR-042**: `floe run` MUST exist as a stub command for pipeline execution
- **FR-043**: `floe test` MUST exist as a stub command for dbt test execution

#### Migration and Deprecation
- **FR-050**: System MUST deprecate the floe-cli package after migration
- **FR-051**: System MUST remove floe-cli entry point after migration
- **FR-052**: System MUST preserve all existing RBAC command functionality during migration

### Key Entities

- **Command Group**: Hierarchical organization of CLI commands (e.g., `platform`, `rbac`)
- **Command**: Individual CLI action with options and arguments (e.g., `compile`, `generate`)
- **Option**: Command-line flag that modifies command behavior (e.g., `--enforcement-report`)
- **Entry Point**: Python package script definition that maps `floe` to CLI main function

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All users can run `floe --help` and see complete command hierarchy within 1 second
- **SC-002**: `floe platform compile` with enforcement export completes for 500+ model manifests in under 5 seconds
- **SC-003**: All 4 RBAC commands (generate, validate, audit, diff) produce identical output before and after migration, verified via golden file comparison
- **SC-004**: Zero entry point conflicts when floe-core is installed (floe-cli package deprecated)
- **SC-005**: All existing CLI tests pass after migration (no regressions)
- **SC-006**: CLI help text readability verified (clear command descriptions, option documentation)
- **SC-007**: 100% of existing floe compile functionality preserved in floe platform compile

## Clarifications

- Q: Which approach should be used to verify RBAC output equivalence? A: Capture golden files before migration for regression testing
- Q: What error output format should CLI commands use? A: Structured stderr with exit codes (plain text errors to stderr, non-zero exit)

## Assumptions

- Click framework is the standard for Python CLIs (consistent with dbt, Dagster, Prefect)
- Users are willing to update scripts from `floe compile` to `floe platform compile`
- The kubernetes Python package is an optional runtime dependency for audit/diff commands
- Stub commands are acceptable for Data Team CLI (full implementation in future epic)
- Rich library is an optional dependency for enhanced terminal output (colors, tables); CLI MUST function without it installed

## Dependencies

- **ADR-0047**: CLI Architecture decision (accepted)
- **Epic 3B**: Policy Validation Enhancement (blocked by this epic)
- **Epic 7B**: K8s RBAC Plugin (provides RBAC generation logic)

## Out of Scope

- Full implementation of Data Team CLI commands (compile, validate, run, test)
- New command functionality beyond what exists in current floe-cli and floe-core
- Changes to RBAC generation logic (only migrating CLI bindings)
- Plugin discovery or registration commands
- Interactive CLI modes or wizards
