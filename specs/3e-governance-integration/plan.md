# Implementation Plan: Epic 3E — Governance Integration

**Branch**: `3e-governance-integration` | **Date**: 2026-02-09 | **Spec**: `specs/3e-governance-integration/spec.md`
**Input**: Feature specification from `/specs/3e-governance-integration/spec.md`
**Research**: Phase 0 findings in `/specs/3e-governance-integration/research.md`

## Summary

Epic 3E is a keystone integration epic that wires together all governance subsystems (RBAC, secret scanning, policy enforcement, network policies, contract monitoring) into a unified compile-time governance pipeline. The core deliverable is a **GovernanceIntegrator** module that sits above the sealed PolicyEnforcer and orchestrates: (1) existing policy validators via PolicyEnforcer, (2) RBAC identity validation via IdentityPlugin, and (3) secret scanning via a new SecretScannerPlugin ABC. All violations merge into a unified EnforcementResultSummary. Additionally, this epic closes the integration test gap for contract monitoring (3D) and adds governance CLI commands.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: pydantic>=2.0, structlog>=24.0, opentelemetry-api>=1.0, click>=8.0, httpx>=0.25.0
**Storage**: PostgreSQL (asyncpg + SQLAlchemy) for contract monitoring integration tests
**Testing**: pytest, IntegrationTestBase, Kind cluster (K8s-native)
**Target Platform**: Linux/macOS (CLI tool), K8s (integration tests)
**Project Type**: Monorepo — packages/floe-core (primary), plugins/ (new secret scanner plugin)
**Performance Goals**: All governance checks complete in <10s for typical project (50 transforms, 10 SQL files); RBAC token validation <2s
**Constraints**: Zero silent skips; collect-all pattern (never fail-fast); backward-compatible contract changes only
**Scale/Scope**: 33 functional requirements, 6 user stories, 8 success criteria

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core for governance, plugins/ for secret scanner)
- [x] No SQL parsing/validation in Python (dbt owns SQL — governance scans files, never parses SQL)
- [x] No orchestration logic outside floe-dagster (GovernanceIntegrator orchestrates checks, not pipeline execution)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (SecretScannerPlugin ABC)
- [x] Plugin registered via entry point (`floe.secret_scanners`)
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (OTel traces on every governance check)
- [x] Pluggable choices documented (secret scanner plugins selectable in manifest.yaml)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (EnforcementResultSummary stored in artifacts)
- [x] Pydantic v2 models for all schemas (RBACConfig, SecretScanningConfig, NetworkPoliciesConfig)
- [x] Contract changes follow versioning rules (MINOR bump — additive fields only)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (contract monitoring + governance integration)
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (all new config models)
- [x] Credentials use SecretStr (tokens never logged)
- [x] No shell=True, no dynamic code execution on untrusted data (secret scanner uses regex, not eval)

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → GovernanceConfig → checks)
- [x] Layer ownership respected (Platform Team owns governance config; Data Team cannot weaken)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (span per governance check: rbac, secrets, policies)
- [x] OpenLineage events not applicable (governance is enforcement, not data transformation)

## Project Structure

### Documentation (this feature)

```text
specs/3e-governance-integration/
├── plan.md              # This file
├── research.md          # Phase 0 research findings
├── data-model.md        # Phase 1 data model design
├── quickstart.md        # Phase 1 quickstart guide
├── contracts/           # Phase 1 contract definitions
└── tasks.md             # Phase 2 task breakdown (via /speckit.tasks)
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── governance/                          # NEW: Governance integration module
│   ├── __init__.py                      # Public API exports
│   ├── integrator.py                    # GovernanceIntegrator orchestrator (FR-031)
│   ├── rbac_checker.py                  # RBAC identity validation (FR-002, FR-003)
│   ├── secrets.py                       # Built-in regex secret scanner (FR-008)
│   └── types.py                         # GovernanceCheckResult, SecretViolation types
│
├── plugins/
│   └── secret_scanner.py                # NEW: SecretScannerPlugin ABC (FR-009)
│
├── schemas/
│   ├── manifest.py                      # MODIFIED: Add rbac, secret_scanning, network_policies to GovernanceConfig
│   ├── governance.py                    # MODIFIED: Extend VALID_POLICY_TYPES frozenset
│   └── compiled_artifacts.py            # MODIFIED: Extend EnforcementResultSummary (MINOR bump)
│
├── enforcement/
│   ├── result.py                        # MODIFIED: Extend Violation.policy_type Literal
│   ├── policy_enforcer.py               # UNCHANGED (sealed)
│   └── exporters/
│       └── sarif_exporter.py            # MODIFIED: Add E5xx/E6xx rule definitions
│
├── cli/
│   ├── main.py                          # MODIFIED: Register governance group
│   └── governance/                      # NEW: Governance CLI commands (FR-024–FR-026)
│       ├── __init__.py                  # Click group definition
│       ├── status.py                    # floe governance status
│       ├── audit.py                     # floe governance audit
│       └── report.py                    # floe governance report --format sarif|json|html
│
└── compilation/
    └── stages.py                        # MODIFIED: Wire GovernanceIntegrator into run_enforce_stage()

testing/
└── fixtures/
    └── governance.py                    # NEW: Reusable governance test fixtures (FR-033)

packages/floe-core/tests/
├── unit/
│   └── governance/                      # NEW: Unit tests for governance module
│       ├── test_integrator.py
│       ├── test_rbac_checker.py
│       ├── test_secrets.py
│       └── conftest.py
├── unit/
│   └── contracts/monitoring/            # EXISTING: 19 unit test files (unchanged)
└── integration/
    └── contracts/monitoring/            # NEW: Integration tests for 3D (FR-027–FR-030)
        ├── test_monitor_integration.py
        ├── test_check_types.py
        ├── test_sla_compliance.py
        ├── test_alert_routing.py
        └── conftest.py

tests/
└── contract/
    └── test_governance_contract.py      # NEW: Cross-package governance contract tests
```

**Structure Decision**: Existing monorepo structure. New code goes into `packages/floe-core/src/floe_core/governance/` (new module), with modifications to existing schemas, enforcement, and CLI modules. Integration tests for 3D contract monitoring at package level. Cross-package contract tests at root level.

## Integration Design

### GovernanceIntegrator Architecture

```
run_enforce_stage() [compilation/stages.py]
        │
        ▼
GovernanceIntegrator [governance/integrator.py]
        │
        ├──► PolicyEnforcer.enforce()          # Existing 6 validators (sealed)
        │    Returns: EnforcementResult         #   naming, coverage, docs, semantic, custom, contracts
        │
        ├──► RBACChecker.check()               # NEW: Identity validation
        │    Uses: IdentityPlugin.validate_token()
        │    Returns: list[Violation]           #   policy_type="rbac"
        │
        └──► SecretScanner.scan()              # NEW: Secret scanning
             Uses: SecretScannerPlugin instances
             Returns: list[Violation]           #   policy_type="secret_scanning"
                     │
                     ▼
              Merge all violations → EnforcementResult
                     │
                     ▼
              create_enforcement_summary() → EnforcementResultSummary
                     │
                     ▼
              Store in CompiledArtifacts.enforcement_result
```

### Contract Changes (MINOR Version Bump)

**1. Violation.policy_type Literal** (`enforcement/result.py`):
```python
# Before:
policy_type: Literal["naming", "coverage", "documentation", "semantic", "custom", "data_contract"]

# After:
policy_type: Literal[
    "naming", "coverage", "documentation", "semantic", "custom", "data_contract",
    "rbac", "secret_scanning", "network_policy",
]
```

**2. VALID_POLICY_TYPES** (`schemas/governance.py`):
```python
# Extend frozenset with new types
VALID_POLICY_TYPES = frozenset({
    "naming", "coverage", "documentation", "semantic", "custom", "data_contract",
    "rbac", "secret_scanning", "network_policy",
})
```

**3. EnforcementSummary** (`enforcement/result.py`):
```python
# Add new optional counters
rbac_violations: int = Field(default=0, ge=0)
secret_violations: int = Field(default=0, ge=0)
network_policy_violations: int = Field(default=0, ge=0)
```

**4. EnforcementResultSummary** (`schemas/compiled_artifacts.py`):
```python
# Add new optional fields
rbac_principal: str | None = Field(default=None, description="Authenticated principal if RBAC enabled")
secrets_scanned: int = Field(default=0, ge=0, description="Number of files scanned for secrets")
```

**5. GovernanceConfig** (`schemas/manifest.py`):
```python
# Add 3 new optional fields
rbac: RBACConfig | None = Field(default=None, description="RBAC configuration (NEW in Epic 3E)")
secret_scanning: SecretScanningConfig | None = Field(default=None, description="Secret scanning (NEW in Epic 3E)")
network_policies: NetworkPoliciesConfig | None = Field(default=None, description="Network policy generation (NEW in Epic 3E)")
```

### New Pydantic Models

**RBACConfig**:
```python
class RBACConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    enabled: bool = False
    required_role: str | None = None  # Role required for compilation
    allow_principal_fallback: bool = True  # Allow --principal when no OIDC
```

**SecretScanningConfig**:
```python
class SecretScanningConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    enabled: bool = False
    exclude_patterns: list[str] = Field(default_factory=list)  # Glob patterns to skip
    custom_patterns: list[SecretPattern] | None = None  # Additional regex patterns
    severity: Literal["error", "warning"] = "error"
```

**NetworkPoliciesConfig**:
```python
class NetworkPoliciesConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    enabled: bool = False
    default_deny: bool = True
    custom_egress_rules: list[dict[str, Any]] = Field(default_factory=list)
```

### SecretScannerPlugin ABC

```python
class SecretScannerPlugin(PluginMetadata):
    """ABC for pluggable secret scanning backends."""

    @abstractmethod
    def scan_file(self, file_path: Path, content: str) -> list[SecretFinding]:
        """Scan a single file for secrets."""
        ...

    @abstractmethod
    def scan_directory(self, directory: Path, exclude_patterns: list[str]) -> list[SecretFinding]:
        """Scan a directory tree for secrets."""
        ...
```

Entry point group: `floe.secret_scanners`

### SARIF Extension

New error code ranges:
- **E5xx**: RBAC violations (E501 = missing token, E502 = expired token, E503 = insufficient role)
- **E6xx**: Secret scanning violations (E601 = AWS key, E602 = password, E603 = API token, E604 = private key, E605 = high-entropy string)

### CLI Commands

| Command | Description | Implementation |
|---------|-------------|----------------|
| `floe governance status` | Display enabled checks + last result | Reads CompiledArtifacts or runs quick check |
| `floe governance audit` | Run all governance checks (no artifacts) | Calls GovernanceIntegrator in audit mode |
| `floe governance report --format sarif\|json\|html` | Export enforcement report | Delegates to existing exporters |

### Token Flow

```
FLOE_TOKEN env var  ─┐
--token CLI flag     ─┤──► GovernanceIntegrator
--principal fallback ─┘         │
                                ▼
                    IdentityPlugin.validate_token(token)
                                │
                                ▼
                    TokenValidationResult
                    ├── valid: True → check roles against rbac.required_role
                    └── valid: False → Violation(policy_type="rbac", error="...")
```

## Implementation Phases

### Phase A: Foundation (Schema + Types)
1. Extend `Violation.policy_type` Literal with new types
2. Extend `VALID_POLICY_TYPES` frozenset
3. Add `RBACConfig`, `SecretScanningConfig`, `NetworkPoliciesConfig` models
4. Add new fields to `GovernanceConfig`
5. Add counters to `EnforcementSummary`
6. Add fields to `EnforcementResultSummary`
7. Create `governance/types.py` with shared types
8. Contract tests for schema stability

### Phase B: Core Modules
1. Create `SecretScannerPlugin` ABC at `plugins/secret_scanner.py`
2. Create `governance/secrets.py` built-in regex scanner
3. Create `governance/rbac_checker.py` RBAC identity checker
4. Create `governance/integrator.py` GovernanceIntegrator
5. Wire GovernanceIntegrator into `run_enforce_stage()`
6. Unit tests for each module

### Phase C: CLI + Exporters
1. Create `cli/governance/` command group (status, audit, report)
2. Register in `cli/main.py`
3. Extend SARIF exporter with E5xx/E6xx rules
4. Unit tests for CLI commands

### Phase D: Test Infrastructure
1. Create `testing/fixtures/governance.py`
2. Contract monitoring integration tests (FR-027–FR-030)
3. Governance integration tests
4. Cross-package contract tests

### Phase E: Network Policy Integration
1. Wire `NetworkSecurityPlugin` into GovernanceIntegrator
2. Generate network policies from governance config
3. Unit + integration tests

## Complexity Tracking

> No constitution violations. All new code follows existing patterns.

| Decision | Rationale |
|----------|-----------|
| GovernanceIntegrator wraps PolicyEnforcer (not extends) | PolicyEnforcer is sealed by design; wrapping preserves its integrity |
| New `governance/` module (not in `enforcement/`) | Governance is broader than enforcement — includes RBAC, secrets, network policies |
| MINOR contract version bump | All changes are additive (new optional fields, extended Literal) |
| Built-in regex scanner (not external tool) | Zero-dependency default; external scanners pluggable via ABC |
