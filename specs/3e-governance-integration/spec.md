# Feature Specification: Governance Integration

**Epic**: 3E (Governance Integration)
**Feature Branch**: `3e-governance-integration`
**Created**: 2026-02-09
**Status**: Draft
**Input**: User description: "Epic 3E: Governance Integration - all other systems are implemented. If there are gaps (either in production code or in the test infra) it is in scope of this Epic to remediate and close the gaps. This is a CRITICAL keystone to tie together our platform and ensure modern, cutting edge security and data governance capabilities. We must hit our target architecture state."

## User Scenarios & Testing

### User Story 1 - Compile-Time Governance Enforcement (Priority: P0)

A platform operator runs `floe compile` and all governance checks execute automatically as part of the compilation pipeline. RBAC validates the caller's identity via Keycloak/OIDC, secrets are scanned across all config and SQL files, and custom policies evaluate against the spec. Violations block compilation unless explicitly overridden. The operator receives a clear, actionable enforcement summary.

**Why this priority**: This is the core integration point — without compile-time governance enforcement wired end-to-end, the platform has no security posture at the point where configurations become artifacts. Every downstream deployment depends on this gate being trustworthy.

**Independent Test**: Can be fully tested by running `floe compile` against a spec with intentional violations (leaked secret, missing RBAC role, policy rule breach) and verifying compilation fails with correct violation details in the EnforcementResultSummary.

**Acceptance Scenarios**:

1. **Given** a manifest with `governance.rbac.enabled: true` and a valid OIDC token in `FLOE_TOKEN` env var, **When** `floe compile` is run, **Then** `IdentityPlugin.validate_token()` passes, principal roles are checked against `governance.rbac.required_role`, and compilation proceeds.
2. **Given** a manifest with `governance.rbac.enabled: true` and no `FLOE_TOKEN` set and no `--principal` fallback, **When** `floe compile` is run, **Then** compilation fails with a clear RBAC violation ("No identity token or principal provided") in EnforcementResultSummary.
3. **Given** a manifest with `governance.rbac.enabled: true` and an expired OIDC token in `FLOE_TOKEN`, **When** `floe compile` is run, **Then** compilation fails with "Token expired" RBAC violation.
3. **Given** a floe.yaml referencing SQL files containing a hardcoded AWS access key, **When** `floe compile` is run with `governance.secret_scanning.enabled: true`, **Then** compilation fails with a secret violation identifying the file and pattern.
4. **Given** a manifest defining custom policies (e.g., `required_tags`, `naming_convention`), **When** `floe compile` evaluates a spec that violates those policies, **Then** violations are collected and reported based on policy severity (warn vs error vs block).
5. **Given** `floe compile --dry-run`, **When** governance violations exist, **Then** all violations are reported but compilation succeeds, producing a preview of what would be enforced.

---

### User Story 2 - Secret Scanning Module with Plugin Interface (Priority: P0)

A security engineer configures secret scanning in the platform manifest and runs compilation. The built-in regex scanner detects common secret patterns (AWS keys, API tokens, passwords, private keys) across config files and referenced SQL. Organizations with advanced needs can plug in external scanners (Gitleaks, TruffleHog) via the SecretScannerPlugin interface.

**Why this priority**: Hardcoded secrets in compiled artifacts are a critical security vulnerability. Without productized scanning integrated into the compilation pipeline, secrets can leak into OCI-published artifacts and downstream Helm values.

**Independent Test**: Can be fully tested by placing files with known secret patterns in a test project, running the scanner, and verifying all patterns are detected with correct file/line references.

**Acceptance Scenarios**:

1. **Given** a project with a Python file containing `AKIA` followed by 16 alphanumeric characters, **When** the secret scanner runs, **Then** it reports an "AWS Access Key ID" violation with file path and line number.
2. **Given** a project with a SQL file containing `password = 'mysecret'`, **When** the secret scanner runs, **Then** it reports a "Hardcoded password" violation.
3. **Given** `governance.secret_scanning.exclude_patterns: ["**/tests/**"]`, **When** test files contain secret-like patterns, **Then** those files are excluded from scanning.
4. **Given** a custom SecretScannerPlugin registered via entry points, **When** `floe compile` runs, **Then** both the built-in scanner and the plugin scanner execute, merging results.
5. **Given** `floe compile --allow-secrets`, **When** secrets are detected, **Then** violations are reported as warnings but compilation proceeds.

---

### User Story 3 - Policy-as-Code Framework (Priority: P1)

A platform operator defines custom governance policies in `manifest.yaml` under `governance.policies`. Each policy specifies a name, a condition to evaluate, an action (warn/error/block), and a human-readable message. Built-in policies cover common governance requirements (required tags, naming conventions, maximum transform count). The framework is extensible to support OPA/Rego evaluation in the future.

**Why this priority**: Custom policies enable organizations to encode their specific governance requirements into the compilation pipeline. Without this, governance is limited to the built-in validators and cannot adapt to organizational needs.

**Independent Test**: Can be tested by defining 3-4 custom policies in a manifest, compiling specs that both satisfy and violate each policy, and verifying correct action (warn/error/block) for each case.

**Acceptance Scenarios**:

1. **Given** a policy `required_tags` with `action: error` requiring a "domain" tag, **When** a spec without a "domain" tag is compiled, **Then** compilation fails with a policy violation.
2. **Given** a policy `naming_convention` with `action: warn`, **When** a spec with an uppercase name is compiled, **Then** a warning is emitted but compilation succeeds.
3. **Given** a policy `max_transforms` with `action: block` and `threshold: 50`, **When** a spec with 60 transforms is compiled, **Then** compilation is blocked with a clear message.
4. **Given** `governance.policies` is empty or not defined, **When** compilation runs, **Then** no custom policy checks execute and compilation proceeds normally.

---

### User Story 4 - Network Policy Generation in Helm (Priority: P1)

A platform operator enables network policy generation via `governance.network_policies.enabled: true` in the manifest. During `floe compile` or Helm template rendering, Kubernetes NetworkPolicy resources are generated that implement default-deny posture with explicit allow rules for platform services (Polaris, PostgreSQL, MinIO, OTel Collector). The generated policies are validated as part of CI.

**Why this priority**: Network segmentation is a fundamental security control. While the floe-network-security-k8s plugin already generates policies, this story ensures the governance configuration in the manifest drives the generation and integrates with the compilation pipeline.

**Independent Test**: Can be tested by enabling network policies in the manifest, rendering Helm templates, and verifying the generated NetworkPolicy YAML includes default-deny and correct allow rules.

**Acceptance Scenarios**:

1. **Given** `governance.network_policies.enabled: true` and `governance.network_policies.default_deny: true`, **When** Helm templates are rendered, **Then** a default-deny NetworkPolicy is generated for the release namespace.
2. **Given** platform services (Polaris, OTel Collector, PostgreSQL) are configured, **When** network policies are generated, **Then** explicit egress rules allow communication to each configured platform service.
3. **Given** `governance.network_policies.enabled: false`, **When** Helm templates are rendered, **Then** no NetworkPolicy resources are generated.
4. **Given** custom egress rules defined in the manifest, **When** network policies are generated, **Then** custom rules are merged with platform defaults without duplication.

---

### User Story 5 - Governance CLI Commands (Priority: P2)

A platform operator uses `floe governance` subcommands to inspect, audit, and manage governance state. Commands include `floe governance status` (show enforcement summary), `floe governance audit` (run all checks without compiling), and `floe governance report` (export SARIF/JSON/HTML reports). These commands provide visibility into governance posture without requiring a full compilation cycle.

**Why this priority**: Operators need to inspect governance state independently of compilation. Audit commands support compliance workflows, CI checks, and troubleshooting.

**Independent Test**: Can be tested by running each CLI command against a configured project and verifying correct output format and content.

**Acceptance Scenarios**:

1. **Given** a project with governance configured, **When** `floe governance status` is run, **Then** it displays a summary of enabled checks, last enforcement result, and violation counts.
2. **Given** a project with policy violations, **When** `floe governance audit` is run, **Then** all governance checks execute and violations are reported without modifying artifacts.
3. **Given** `floe governance report --format sarif`, **When** violations exist, **Then** a SARIF v2.1.0 compliant report is written to the output path.
4. **Given** `floe governance report --format html`, **When** violations exist, **Then** a human-readable HTML report is generated.

---

### User Story 6 - Contract Monitoring Integration Tests (Priority: P1)

Contract monitoring (Epic 3D) is code-complete but lacks integration tests that validate the system works with real database connections, real check scheduling, and real alert routing. This story adds integration tests that exercise the monitoring orchestrator, check runners, and alert router against a live PostgreSQL database.

**Why this priority**: Without integration tests, the contract monitoring system cannot be trusted for production use. This is a test infrastructure gap that must be closed before the governance subsystem can be considered production-ready.

**Independent Test**: Can be tested by running the monitoring integration test suite against a Kind cluster with PostgreSQL and verifying all check types execute, alerts fire, and SLA metrics are recorded.

**Acceptance Scenarios**:

1. **Given** a PostgreSQL database and configured data contracts, **When** the ContractMonitor runs freshness checks, **Then** check results are persisted to the database with correct timestamps.
2. **Given** a contract with a schema drift check, **When** the schema changes between runs, **Then** a drift violation is detected and an alert is routed to the configured channel.
3. **Given** SLA thresholds defined in a contract, **When** violations exceed the SLA threshold, **Then** SLA compliance metrics are updated and an incident is created.
4. **Given** a webhook alert channel configured, **When** a violation triggers an alert, **Then** the webhook receives a correctly formatted payload.

---

### Edge Cases

- What happens when the identity provider (Keycloak) is unreachable during compile-time RBAC check? Compilation fails with a clear connectivity error, not a silent pass.
- What happens when a secret pattern matches a false positive (e.g., test fixture with `AKIA` prefix)? Exclude patterns in manifest take precedence; per-file inline suppression comments supported.
- What happens when multiple policy violations occur simultaneously? All violations are collected and reported in a single EnforcementResultSummary, not fail-fast on the first.
- What happens when governance is completely unconfigured (no governance section in manifest)? All governance checks are skipped; compilation proceeds as before. Governance is opt-in.
- What happens when a SecretScannerPlugin raises an exception during scanning? The error is captured as a scanner-level violation; other scanners continue. The error is logged with full context.
- What happens when network policy generation conflicts with existing manually-applied policies in the cluster? Generated policies are additive; floe never deletes manually-created policies. `floe governance audit` can detect drift.

## Requirements

### Functional Requirements

#### Compile-Time Governance Enforcement

- **FR-001**: System MUST execute all enabled governance checks (RBAC, secrets, policies, contracts) as Stage 6 of the compilation pipeline, after transform resolution and before artifact generation. The default enforcement level is `warn` (violations reported but do not block compilation). Platform operators can escalate to `strict` (violations block compilation) via `governance.policy_enforcement_level: strict`. In 3-tier mode (enterprise -> domain), enforcement level is configurable at each tier and inherits downward (enterprise sets floor, domain can escalate but not relax).
- **FR-002**: System MUST validate the caller's identity via the configured IdentityPlugin (Keycloak/OIDC) when `governance.rbac.enabled` is true. The token is provided via `FLOE_TOKEN` environment variable or `--token` CLI flag. GovernanceIntegrator calls `IdentityPlugin.validate_token()` to obtain `TokenValidationResult` including `user_info.roles`. Compilation fails if the token is invalid, expired, or the principal lacks the required role.
- **FR-003**: System MUST support `--principal` CLI flag and `FLOE_PRINCIPAL` environment variable as a static fallback when no IdentityPlugin is configured or no token is provided. This supports CI/CD pipelines and offline use cases where OIDC is unavailable.
- **FR-004**: System MUST collect all violations across all governance checks before reporting, never failing on the first violation (collect-all pattern).
- **FR-005**: System MUST persist governance results in `EnforcementResultSummary` within `CompiledArtifacts` for audit trail purposes.
- **FR-006**: System MUST support `--dry-run` mode where all governance checks execute and report violations but compilation succeeds regardless.
- **FR-007**: System MUST emit OpenTelemetry spans for each governance check (rbac, secrets, policies) with timing and result attributes.

#### Secret Scanning

- **FR-008**: System MUST provide a built-in regex-based secret scanner in `floe_core/governance/secrets.py` that detects at minimum: AWS access key IDs, hardcoded passwords, API keys/tokens, private keys (RSA/EC), and generic high-entropy strings.
- **FR-009**: System MUST define a `SecretScannerPlugin` ABC with entry point `floe.secret_scanners` for pluggable external scanners (Gitleaks, TruffleHog, etc.).
- **FR-010**: System MUST scan all files referenced by the FloeSpec (SQL models, YAML configs, Python modules) plus the manifest.yaml itself.
- **FR-011**: System MUST support configurable exclude patterns via `governance.secret_scanning.exclude_patterns` (snake_case, consistent with existing GovernanceConfig fields) to skip test directories, fixtures, and known false positives.
- **FR-012**: System MUST report secret violations with file path, line number, pattern name, and severity.
- **FR-013**: System MUST support `--allow-secrets` CLI flag that downgrades secret violations from errors to warnings.
- **FR-014**: System MUST export secret scan results in SARIF v2.1.0 format for integration with CI tools (GitHub Advanced Security, GitLab SAST).

#### Policy-as-Code Framework

- **FR-015**: System MUST support custom policy definitions in `manifest.yaml` under `governance.policies` with fields: `name`, `condition`, `action` (warn/error/block), and `message`.
- **FR-016**: System MUST provide built-in policies: `required_tags` (enforce metadata tags), `naming_convention` (enforce naming patterns), and `max_transforms` (limit transform count).
- **FR-017**: System MUST evaluate custom policies against the resolved FloeSpec and report violations with the configured action level.
- **FR-018**: System MUST support policy condition expressions using a safe, sandboxed evaluator (no eval/exec; Pydantic-validated condition DSL).
- **FR-019**: System MUST integrate custom policy evaluation via the GovernanceIntegrator, which delegates to the existing PolicyEnforcer (Epic 3A) for custom rules while keeping PolicyEnforcer sealed and unmodified.

#### Network Policy Generation

- **FR-020**: System MUST generate Kubernetes NetworkPolicy resources when `governance.network_policies.enabled` is true, driven by governance configuration in the manifest.
- **FR-021**: System MUST generate a default-deny NetworkPolicy when `governance.network_policies.default_deny` is true.
- **FR-022**: System MUST generate explicit allow rules for each configured platform service (Polaris, PostgreSQL, MinIO, OTel Collector) based on the resolved platform configuration.
- **FR-023**: System MUST integrate with the floe-network-security-k8s plugin (Epic 7C) to delegate actual NetworkPolicy generation, ensuring the governance configuration in the manifest drives the plugin's behavior.

#### Governance CLI

- **FR-024**: System MUST provide `floe governance status` command that displays enabled governance checks, last enforcement result, and violation summary.
- **FR-025**: System MUST provide `floe governance audit` command that executes all governance checks without producing compiled artifacts.
- **FR-026**: System MUST provide `floe governance report` command supporting `--format` flag with options: `sarif`, `json`, `html`.

#### Contract Monitoring Integration Tests

- **FR-027**: System MUST have integration tests for the ContractMonitor orchestrator validating check execution, result persistence, and alert routing against a real PostgreSQL database.
- **FR-028**: System MUST have integration tests for each check type (freshness, schema drift, quality, availability) verifying correct detection and reporting.
- **FR-029**: System MUST have integration tests for SLA compliance tracking verifying threshold evaluation and incident creation.
- **FR-030**: System MUST have integration tests for the AlertRouter verifying correct delivery to configured channels (webhook at minimum).

#### Gap Remediation

- **FR-031**: System MUST wire the `governance/integration.py` GovernanceIntegrator as the single entry point called from the compilation pipeline's ENFORCE stage. GovernanceIntegrator sits above PolicyEnforcer (which remains sealed/unmodified) and orchestrates: (1) PolicyEnforcer for existing validators, (2) RBAC checker for identity validation, (3) Secret scanner for credential detection. All violations are merged into a unified EnforcementResultSummary.
- **FR-032**: System MUST ensure all governance violations are serializable to JSON and included in CompiledArtifacts for downstream consumption.
- **FR-033**: System MUST provide a `testing/fixtures/governance.py` module with reusable test fixtures for governance scenarios (valid/invalid tokens, secret-laden files, policy violations).

### Key Entities

- **GovernanceConfig**: Configuration block in manifest.yaml controlling all governance features (RBAC, secrets, policies, network). Extends existing schema from Epic 3A/3B/3C. New fields use snake_case to match existing convention: `rbac`, `secret_scanning`, `network_policies`.
- **EnforcementResultSummary**: Persisted in CompiledArtifacts. Contains violation list, pass/fail status, policy count, check durations, and scanner metadata.
- **PolicyViolation**: Individual violation record with policy name, message, severity, file path, line number, and error code.
- **SecretScannerPlugin**: ABC for pluggable secret scanning backends. Default implementation: built-in regex scanner.
- **GovernanceIntegrator**: Higher-level orchestrator module (`governance/integration.py`) that sits above PolicyEnforcer and coordinates all governance checks. Calls PolicyEnforcer for existing validators (naming, coverage, documentation, semantic, custom rules, data contracts), then separately invokes the RBAC checker and secret scanner. Merges all violations into the unified EnforcementResultSummary. PolicyEnforcer remains sealed and unmodified.

## Integration Points

**Entry Points**:
- `floe compile` CLI command (Stage 6 governance enforcement)
- `floe governance status|audit|report` CLI commands (floe-cli package)
- `floe.secret_scanners` entry point group (plugin discovery)

**Dependencies**:
- floe-core: PolicyEnforcer (3A), ContractValidator (3C), EnforcementResultSummary, GovernanceConfig
- floe-core/compilation: stages.py (ENFORCE stage hook)
- floe-core/rbac: RBACGenerator (7B)
- floe-core/contracts/monitoring: ContractMonitor (3D)
- plugins/floe-identity-keycloak: IdentityPlugin (7A) for OIDC token validation
- plugins/floe-network-security-k8s: NetworkSecurityPlugin (7C) for policy generation
- plugins/floe-secrets-k8s: SecretsPlugin (7A) for credential resolution

**Produces**:
- `GovernanceIntegrator` module (new, in floe-core governance/)
- `SecretScannerPlugin` ABC (new, in floe-core plugin interfaces)
- `SecretScanner` built-in implementation (new, in floe-core governance/)
- Updated `EnforcementResultSummary` with secret scan and RBAC fields
- `testing/fixtures/governance.py` (new, test utilities)
- Integration tests for Epic 3D contract monitoring

## Success Criteria

### Measurable Outcomes

- **SC-001**: All governance checks (RBAC, secrets, policies, contracts, network) execute within a single `floe compile` invocation, completing in under 10 seconds for a typical project (50 transforms, 10 SQL files).
- **SC-002**: Secret scanning detects 100% of the defined pattern categories (AWS keys, passwords, API tokens, private keys) with a false positive rate below 5% on the standard test corpus.
- **SC-003**: RBAC enforcement via Keycloak/OIDC validates tokens in under 2 seconds including network round-trip, with clear error messages for all failure modes (expired, invalid, missing role).
- **SC-004**: All governance violations are captured in EnforcementResultSummary with sufficient detail (file, line, policy, severity) that an operator can fix each violation without additional investigation.
- **SC-005**: The governance subsystem achieves >80% unit test coverage and >70% integration test coverage, with 100% requirement traceability via `@pytest.mark.requirement()`.
- **SC-006**: Contract monitoring integration tests pass against a real PostgreSQL instance in a Kind cluster, covering all 4 check types and alert routing.
- **SC-007**: SARIF export from secret scanning and policy enforcement is compliant with SARIF v2.1.0 schema and consumable by GitHub Advanced Security.
- **SC-008**: Zero governance checks silently skip or swallow errors — every check either passes, fails with a violation, or fails with a clear infrastructure error.

## Assumptions

- The Keycloak identity plugin (Epic 7A) provides `validate_token(token: str) -> TokenValidationResult` which returns `valid: bool`, `user_info: UserInfo | None` (with `roles: list[str]`), `error: str`, and `expires_at: str`. The RBAC checker uses this exact interface. Token is provided via `FLOE_TOKEN` env var or `--token` CLI flag (token-based flow; no credential-based authentication at compile time).
- The existing PolicyEnforcer (Epic 3A) is sealed with hardcoded validators (naming, coverage, documentation, semantic, custom rules, data contracts). It does NOT expose an `add_validator()` API. The GovernanceIntegrator will orchestrate PolicyEnforcer as-is and add RBAC/secret scanning as separate check phases above it.
- The existing SARIF exporter (Epic 3A) can be extended to include secret scan results without breaking backward compatibility.
- PostgreSQL is available in the Kind cluster for contract monitoring integration tests (via existing test infrastructure).
- The compilation pipeline stages are numbered and ordered; adding governance as Stage 6 does not require renumbering existing stages (the ENFORCE stage already exists and will be extended).

## Clarifications

- Q: PolicyEnforcer is sealed with hardcoded validators (no add_validator() API). How should RBAC and secret scanning integrate?: A: GovernanceIntegrator as a higher-level orchestrator that calls PolicyEnforcer for existing checks, then RBAC checker, then secret scanner separately. PolicyEnforcer remains sealed and unmodified.
- Q: How should operators provide OIDC identity to `floe compile` at compile-time?: A: Token-based flow. Operator obtains token externally (e.g., `floe auth login` or CI OIDC token), passes via `FLOE_TOKEN` env var or `--token` flag. GovernanceIntegrator calls `IdentityPlugin.validate_token()`.
- Q: Should new GovernanceConfig fields use snake_case or camelCase in manifest.yaml?: A: snake_case, matching existing GovernanceConfig fields (policy_enforcement_level, data_retention_days, custom_rules).
- Q: What is the default enforcement behavior when governance is enabled?: A: `warn` (violations reported but do not block compilation). Configurable at platform/domain level via `governance.policy_enforcement_level`. In 3-tier mode, enforcement level inherits downward (enterprise sets floor, domain can escalate but not relax).
