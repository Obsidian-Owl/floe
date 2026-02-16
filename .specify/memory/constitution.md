<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.1.0 (MINOR: added principle)
Modified principles: None
Added sections:
  - Principle IX: Escalation Over Workaround (NON-NEGOTIABLE)
Removed sections: None
Templates requiring updates:
  - .specify/templates/plan-template.md - no changes needed (escalation is behavioral)
  - .specify/templates/spec-template.md - no changes needed
  - .specify/templates/tasks-template.md - no changes needed
Follow-up TODOs:
  - Audit existing codebase for workaround anti-patterns (pytest.skip, except:pass, weak assertions)
  - Review all Skills for escalation trigger integration
-->

# floe Constitution

## Core Principles

### I. Technology Ownership (NON-NEGOTIABLE)

Each technology owns its domain exclusively. Python code MUST NOT cross these boundaries.

| Technology | Owns | Python MUST NOT |
|------------|------|-----------------|
| **dbt** | ALL SQL compilation, dialect translation | Parse, validate, or transform SQL |
| **Dagster** | Orchestration, assets, schedules | Manage Iceberg tables directly |
| **Iceberg** | Storage format, ACID, time travel | Define orchestration |
| **Polaris** | Catalog management (REST API) | Write to storage directly |
| **Cube** | Semantic layer, consumption APIs | Orchestrate pipelines |

**Rationale**: Technology boundaries prevent duplication of responsibility and ensure each tool does what it does best. dbt has proven SQL handling; Dagster has proven orchestration. Crossing boundaries creates maintenance burden and defeats the purpose of using these tools.

### II. Plugin-First Architecture

All configurable components MUST use the plugin system with entry point discovery.

- **Entry Points**: All plugins register via `pyproject.toml` entry points (`floe.computes`, `floe.orchestrators`, etc.)
- **Interface > Implementation**: Define ABCs (ComputePlugin, OrchestratorPlugin, etc.), not concrete classes in core
- **15 Plugin Types**: Catalog, Compute, DBT, Identity, Ingestion, Lineage, NetworkSecurity, Orchestrator, Quality, RBAC, Secrets, SemanticLayer, Storage, Telemetry, PluginLoader. 12 have concrete implementations; 3 are ABC-only (Ingestion, Semantic, Storage)
- **PluginMetadata**: Every plugin MUST declare name, version, and floe_api_version

**Rationale**: Plugin architecture enables flexibility without configuration sprawl. Entry points ensure consistent discovery. ABCs enforce contracts while allowing multiple implementations.

### III. Enforced vs Pluggable Boundaries

Some standards are non-negotiable; others are Platform Team choices.

**ENFORCED** (cannot change):
- Apache Iceberg (table format)
- OpenTelemetry (observability)
- OpenLineage (data lineage)
- dbt (transformation)
- Kubernetes-native (deployment)

**PLUGGABLE** (Platform Team selects once):
- Compute: DuckDB, Snowflake, Spark, BigQuery, Databricks
- Orchestrator: Dagster, Airflow 3.x, Prefect
- Catalog: Polaris, AWS Glue, Hive
- Storage: S3, GCS, Azure Blob, MinIO
- And 7 more plugin types...

**Rationale**: Enforced standards define floe's identity and enable guarantees (all tables Iceberg, all telemetry OTel). Pluggable components respect organizational investments and different scale requirements.

### IV. Contract-Driven Integration

Cross-package communication MUST use defined contracts, not direct coupling.

- **CompiledArtifacts**: The SOLE contract between floe-core and other packages
- **Pydantic v2**: ALL schemas use Pydantic with `model_config = ConfigDict(frozen=True, extra="forbid")`
- **JSON Schema Export**: All contracts export JSON Schema for IDE autocomplete
- **Contract Versioning**: MAJOR (breaking), MINOR (additive), PATCH (docs only)

**FORBIDDEN**: Passing FloeSpec directly to floe-dagster; creating ad-hoc integration formats.

**Rationale**: Contracts enable independent package testing and evolution. Pydantic provides runtime validation. JSON Schema enables tooling support without runtime coupling.

### V. K8s-Native Testing (NON-NEGOTIABLE)

All integration and E2E tests MUST run in Kubernetes for production parity.

- **Kind Cluster**: Local testing uses Kind; CI uses managed K8s
- **Tests FAIL, Never Skip**: `pytest.skip()` is FORBIDDEN except for `importorskip` or platform impossibility
- **Requirement Traceability**: 100% of integration tests MUST have `@pytest.mark.requirement()` markers
- **Contract Tests**: Cross-package contracts MUST have root-level tests in `tests/contract/`
- **Pre-PR Review**: `/speckit.test-review` MUST pass before PR creation
- **Coverage**: >80% overall, >70% integration

**Rationale**: K8s-native testing ensures production parity (same DNS, networking, secrets). Skipped tests hide infrastructure rot. Traceability ensures requirements are tested.

### VI. Security First

Security is not optional; it is built into every component.

- **Input Validation**: ALL external input MUST use Pydantic models
- **Secrets**: ALL credentials MUST use `SecretStr` and environment variables
- **FORBIDDEN Constructs**: Dynamic code execution on untrusted data, `shell=True` in subprocess
- **Structured Logging**: Use structlog with trace context; NEVER log secrets or PII
- **Dependency Security**: Update within 7 days of CVE disclosure; run `pip-audit` in CI

**Rationale**: Security vulnerabilities in data platforms can expose sensitive business data. Pydantic prevents injection; SecretStr prevents accidental logging; dependency scanning prevents supply chain attacks.

### VII. Four-Layer Architecture

Configuration flows DOWNWARD ONLY through the four-layer model.

```
Layer 4: DATA (Ephemeral Jobs)     - Owner: Data Engineers, Config: floe.yaml
Layer 3: SERVICES (Long-lived)     - Owner: Platform Engineers, Deploy: floe platform deploy
Layer 2: CONFIGURATION (Enforcement) - Owner: Platform Engineers, Storage: OCI Registry
Layer 1: FOUNDATION (Framework)    - Owner: floe Maintainers, Distribution: PyPI/Helm
```

**FORBIDDEN**: Layer 4 modifying Layer 2 configuration; Data Engineers overriding Platform Team plugin choices.

**Rationale**: Separation of concerns between Platform Team (governance, guardrails) and Data Team (pipelines, transforms). OCI registry ensures immutable, versioned platform artifacts.

### VIII. Observability By Default

Every operation MUST be observable via enforced telemetry standards.

- **OpenTelemetry**: ALL traces, metrics, and logs flow through OTLP Collector
- **OpenLineage**: ALL data transformations emit lineage events
- **Trace Context**: W3C standard propagation through all pipeline stages
- **Backend Pluggable**: Jaeger, Datadog, Grafana Cloud via TelemetryBackendPlugin

**Rationale**: Data platforms are complex distributed systems. Without observability, debugging production issues is impossible. OpenTelemetry and OpenLineage are industry standards with broad tool support.

### IX. Escalation Over Assumption (NON-NEGOTIABLE)

ALL design decisions, trade-offs, and assumptions MUST be escalated to the user. AI agents are autonomous ONLY for mechanical tasks with objectively correct outcomes. Everything involving judgment requires explicit user approval.

- **Design Decisions**: Any choice between valid approaches (technology, architecture, scope, configuration, error handling) MUST be presented to the user via `AskUserQuestion` with options and trade-offs. Claude MUST NOT silently choose an approach.
- **Assumptions**: Any assumption about user intent, infrastructure behavior, or project conventions MUST be confirmed before acting on it. "Probably" and "I assume" are escalation triggers, not action triggers.
- **Test Integrity**: Tests are the hard quality gate that validates design decisions. NEVER weaken assertions to make failing tests pass. If a test fails, the code is wrong, not the test.
- **Workaround Prohibition**: Monkey-patches, exception swallowing, mock substitution, and complexity-absorbing code are FORBIDDEN without explicit user approval.
- **Tracking**: When escalation identifies a problem that won't be fixed immediately, create a GitHub Issue with label `tech-debt` or `architecture`.

**FORBIDDEN**: Making design choices silently, embedding assumptions without confirming, softening tests, introducing workarounds without user approval, reducing planned scope.

**Rationale**: Silent design decisions compound into architectural drift. Hidden workarounds compound into systemic quality debt. A 30-second `AskUserQuestion` costs nothing; a wrong assumption embedded in the codebase costs hours to find and fix. The user is the architect — Claude is the implementer.

## Technology Ownership

**Detailed Boundaries for Implementation**:

| Component | Responsibility | Integration Pattern |
|-----------|---------------|---------------------|
| **floe-core** | Schemas, validation, compilation | Produces CompiledArtifacts |
| **floe-dagster** | Asset definitions, scheduling | Consumes CompiledArtifacts |
| **floe-dbt** | SQL model compilation, profiles.yml | Invoked by orchestrator plugins |
| **floe-iceberg** | PyIceberg integration, IOManager | Used by storage and catalog plugins |
| **Plugins** | Single responsibility per plugin | Register via entry points |

**See**: `.claude/rules/component-ownership.md` for complete ownership matrix

## Development Workflow

### Pre-Implementation Checklist

Before writing any code, verify:

1. [ ] **Technology Ownership**: Am I putting this code in the right package?
2. [ ] **Plugin vs Core**: Should this be a plugin or core module?
3. [ ] **Contract Impact**: Does this change CompiledArtifacts schema?
4. [ ] **Test Strategy**: Do I need unit, contract, or integration tests?

### Implementation Requirements

- **TDD Pattern**: Tests written → Tests fail → Implementation → Tests pass
- **Type Safety**: `mypy --strict` MUST pass; `from __future__ import annotations` required
- **Code Review**: All PRs require review; constitution compliance verified
- **Atomic Commits**: 300-600 LOC max per commit; meaningful commit messages

### Quality Gates

| Gate | Tool | Threshold |
|------|------|-----------|
| Type Checking | mypy --strict | 0 errors |
| Linting | ruff | 0 errors |
| Security | bandit, pip-audit | 0 high/critical |
| Coverage | pytest-cov | >80% |
| Traceability | testing.traceability | 100% |

## Governance

### Constitution Authority

This constitution supersedes all other development practices. When in conflict, the constitution wins.

### Amendment Process

1. Propose amendment via PR with rationale
2. Review by project maintainers
3. Update version according to semantic versioning:
   - **MAJOR**: Remove/redefine principle
   - **MINOR**: Add principle or expand guidance
   - **PATCH**: Clarify wording, fix typos
4. Update all dependent templates (plan-template.md, etc.)
5. Communicate change to all contributors

### Compliance Review

- All PRs MUST verify constitutional compliance
- `/speckit.test-review` performs automated compliance checks
- Violations require explicit justification in PR description
- Repeated violations trigger process review

### Reference Documents

- **Architecture**: `docs/architecture/ARCHITECTURE-SUMMARY.md`
- **Testing**: `TESTING.md`
- **Security**: `.claude/rules/security.md`
- **Component Ownership**: `.claude/rules/component-ownership.md`

**Version**: 1.1.0 | **Ratified**: 2026-01-08 | **Last Amended**: 2026-02-05
