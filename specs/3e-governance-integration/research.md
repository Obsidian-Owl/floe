# Phase 0 Research: Epic 3E — Governance Integration

**Date**: 2026-02-09
**Spec**: `specs/3e-governance-integration/spec.md`

## Research Questions & Findings

### RQ-1: How is the existing enforcement pipeline structured?

**Finding**: The compilation pipeline in `packages/floe-core/src/floe_core/compilation/stages.py` defines 6 stages via `CompilationStage` enum: LOAD, VALIDATE, RESOLVE, ENFORCE, COMPILE, GENERATE. Stage 4 (ENFORCE) in `compile_pipeline()` is a **placeholder** (lines 264-267) — actual enforcement runs via a standalone `run_enforce_stage()` function (line 341) called **after** dbt compilation.

`run_enforce_stage()` signature:
```python
def run_enforce_stage(
    governance_config: GovernanceConfig | None,
    dbt_manifest: dict[str, Any],
    *,
    dry_run: bool = False,
) -> EnforcementResult:
```

It instantiates `PolicyEnforcer(governance_config=governance_config)` and calls `enforcer.enforce(dbt_manifest, dry_run=dry_run)`. Wrapped in OTel span `"compile.enforce"`.

**Implication**: GovernanceIntegrator should replace or wrap the call site in `run_enforce_stage()`, becoming the new orchestration point for all governance checks.

### RQ-2: Is PolicyEnforcer extensible?

**Finding**: PolicyEnforcer in `enforcement/policy_enforcer.py` is **sealed**. The `_run_all_validators()` method (line 134) hardcodes 6 validators:
1. `NamingValidator` — if `governance_config.naming` is set
2. `CoverageValidator` — via `_run_quality_gate_validators()`
3. `DocumentationValidator` — if `quality_gates.require_descriptions`
4. `SemanticValidator` — always
5. `CustomRuleValidator` — if `governance_config.custom_rules`
6. `ContractValidator` — if contract_path or data_contracts configured

**No `add_validator()` or registration API exists.** This is intentional — PolicyEnforcer is a sealed orchestrator for dbt manifest validation.

**Implication**: GovernanceIntegrator sits ABOVE PolicyEnforcer, invoking it for existing checks, then running RBAC and secret scanning as separate phases. PolicyEnforcer remains unmodified.

### RQ-3: What types does the Violation model support?

**Finding**: `Violation.policy_type` at `enforcement/result.py:84-86`:
```python
policy_type: Literal["naming", "coverage", "documentation", "semantic", "custom", "data_contract"]
```

`VALID_POLICY_TYPES` frozenset at `schemas/governance.py:596`:
```python
VALID_POLICY_TYPES = frozenset({"naming", "coverage", "documentation", "semantic", "custom", "data_contract"})
```

**Implication**: Both must be extended with new types: `"rbac"`, `"secret_scanning"`, `"network_policy"`. This is a MINOR contract change (additive Literal extension, new optional `EnforcementSummary` counters).

### RQ-4: What GovernanceConfig fields exist vs. needed?

**Finding**: Current `GovernanceConfig` at `schemas/manifest.py:114` has:
- `pii_encryption`, `audit_logging`, `policy_enforcement_level`, `data_retention_days`
- `naming` (3A), `quality_gates` (3A), `custom_rules` (3B), `policy_overrides` (3B), `data_contracts` (3C)

**Missing for 3E**: `rbac`, `secret_scanning`, `network_policies`

`model_config = ConfigDict(frozen=True, extra="forbid")` — any new fields are a schema change.

**Implication**: Add 3 new optional fields to GovernanceConfig. Each will be a new Pydantic model: `RBACConfig`, `SecretScanningConfig`, `NetworkPoliciesConfig`.

### RQ-5: What is the IdentityPlugin interface?

**Finding**: `plugins/identity.py` defines:
- `UserInfo` dataclass: `subject`, `email`, `name`, `roles: list[str]`, `groups`, `claims`
- `TokenValidationResult` dataclass: `valid: bool`, `user_info: UserInfo | None`, `error: str`, `expires_at: str`
- `IdentityPlugin(PluginMetadata)` ABC with methods:
  - `authenticate(credentials: dict[str, Any]) -> str | None`
  - `get_user_info(token: str) -> UserInfo | None`
  - `validate_token(token: str) -> TokenValidationResult`
  - `get_oidc_config(realm: str | None = None) -> OIDCConfig`

Keycloak implementation at `plugins/floe-identity-keycloak/`, entry point `floe.identity`.

**Implication**: GovernanceIntegrator calls `IdentityPlugin.validate_token(token)` directly. Token comes from `FLOE_TOKEN` env var or `--token` CLI flag. Roles checked against `governance.rbac.required_role`.

### RQ-6: Does a SecretScannerPlugin ABC exist?

**Finding**: **No.** There is no `secret_scanner.py` in `packages/floe-core/src/floe_core/plugins/`. The `secrets.py` plugin (`SecretsPlugin`) is for credential management (get/set/list secrets in K8s/Infisical), not scanning.

**Implication**: Must create new `SecretScannerPlugin` ABC at `plugins/secret_scanner.py` with entry point group `floe.secret_scanners`.

### RQ-7: What CLI pattern is used?

**Finding**: `cli/main.py` uses Click groups. Root group `cli` registers subgroups: `platform`, `rbac`, `network`, `artifact`, `helm`, `sla`. Data team commands at root: `compile`, `validate`, `run`, `test`. Each group is a subdirectory with `__init__.py` defining `@click.group()`.

**Implication**: Create `cli/governance/` subdirectory with `status`, `audit`, `report` commands. Register `governance` group in `main.py`.

### RQ-8: What entry point pattern is used?

**Finding**: All 20+ plugin implementations register via `pyproject.toml`:
```toml
[project.entry-points."floe.<group>"]
name = "module_path:ClassName"
```

Groups include: `floe.computes`, `floe.catalogs`, `floe.rbac`, `floe.identity`, `floe.network_security`, `floe.secrets`, `floe.alert_channels`, `floe.secret_scanners` (NEW).

**Implication**: New `floe.secret_scanners` entry point group. Built-in regex scanner can be an optional default registered in floe-core's own pyproject.toml or auto-discovered.

### RQ-9: What test fixtures exist?

**Finding**: `testing/fixtures/` has 15 fixture modules: catalog, dagster, data, duckdb, ingestion, lineage, minio, namespaces, polaris, polling, postgres, semantic, services, telemetry. **No `governance.py`.**

**Implication**: Create `testing/fixtures/governance.py` with reusable fixtures for governance testing (valid/invalid tokens, secret-laden files, policy violations, governance configs).

### RQ-10: What SARIF exporter exists?

**Finding**: `enforcement/exporters/sarif_exporter.py` exports SARIF v2.1.0 compliant reports. `RULE_DEFINITIONS` dict covers error codes E201-E402. Main function: `export_sarif(result: EnforcementResult, output_path: Path) -> Path`. Also has JSON and HTML exporters.

**Implication**: Extend `RULE_DEFINITIONS` with new error codes for RBAC (E5xx) and secret scanning (E6xx). The existing `export_sarif()` function works with `EnforcementResult` which holds `list[Violation]`, so extending `Violation.policy_type` automatically supports new violation types in SARIF export.

### RQ-11: What is the contract monitoring (3D) test gap?

**Finding**: 19 unit test files exist at `packages/floe-core/tests/unit/contracts/monitoring/`. **Zero integration tests.** The monitoring system uses async PostgreSQL (asyncpg + SQLAlchemy) and alert channels that need real service testing.

Key modules needing integration coverage:
- `ContractMonitor` orchestrator (check execution, result persistence)
- Individual checks (freshness, schema_drift, quality, availability)
- `AlertRouter` (webhook delivery)
- SLA compliance (threshold evaluation, incident creation)
- Database persistence (repository + migrations)

**Implication**: Add integration tests at `packages/floe-core/tests/integration/contracts/monitoring/` using `IntegrationTestBase` with PostgreSQL fixtures.

### RQ-12: What NetworkSecurityPlugin interface is available?

**Finding**: `plugins/network_security.py` defines `NetworkSecurityPlugin(PluginMetadata)` with methods:
- `generate_network_policy(config: NetworkPolicyConfig) -> dict[str, Any]`
- `generate_default_deny_policies(namespace: str) -> list[dict[str, Any]]`

K8s implementation at `plugins/floe-network-security-k8s/`, entry point `floe.network_security`.

CLI commands exist at `cli/network/` (generate, check-cni, validate, audit, diff).

**Implication**: GovernanceIntegrator can delegate to `NetworkSecurityPlugin` when `governance.network_policies.enabled`. The network CLI already exists — governance CLI wraps/references it rather than duplicating.

### RQ-13: How does EnforcementResultSummary integrate into CompiledArtifacts?

**Finding**: `EnforcementResultSummary` at `schemas/compiled_artifacts.py:440`:
```python
class EnforcementResultSummary(BaseModel):
    passed: bool
    error_count: int  # ge=0
    warning_count: int  # ge=0
    policy_types_checked: list[str]
    models_validated: int  # ge=0
    enforcement_level: Literal["off", "warn", "strict"]
```

Stored in `CompiledArtifacts.enforcement_result: EnforcementResultSummary | None` (line 643).

Helper function `create_enforcement_summary()` at `enforcement/result.py:496` converts full `EnforcementResult` to summary.

**Implication**: `EnforcementResultSummary` already has `policy_types_checked: list[str]` which naturally accommodates new types. May need additional fields for RBAC principal info and secret scan counts. This is a MINOR version bump of CompiledArtifacts.

## Resolved Unknowns

| # | Unknown | Resolution |
|---|---------|------------|
| 1 | PolicyEnforcer extensibility | Sealed. GovernanceIntegrator wraps it. |
| 2 | OIDC auth flow | Token-based via `FLOE_TOKEN` / `--token` |
| 3 | YAML field casing | snake_case (existing convention) |
| 4 | Default enforcement level | `warn`, configurable per 3-tier hierarchy |
| 5 | Integration pattern | GovernanceIntegrator as higher-level orchestrator |
| 6 | Stage numbering | ENFORCE is Stage 4 (placeholder), actual run is post-dbt |
| 7 | Secret scanner ABC | Does not exist yet — must create |
| 8 | Governance CLI | Does not exist yet — must create |
| 9 | Test fixtures | No governance fixtures — must create |
| 10 | 3D test gap | 19 unit tests, 0 integration tests |
| 11 | Violation type extension | MINOR contract change: extend Literal + frozenset |
| 12 | Network policy CLI | Already exists at `cli/network/` — governance wraps it |
| 13 | SARIF extension | Add rule definitions; export function handles new types automatically |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| `Violation.policy_type` Literal extension breaks existing validators | Medium | Additive-only change; existing validators unaffected |
| GovernanceConfig `extra="forbid"` rejects unknown fields | Low | All new fields are added to the model, not passed as extras |
| EnforcementResultSummary schema change in CompiledArtifacts | Medium | MINOR version bump; additive fields only; backward-compatible |
| Token-based OIDC may fail in offline environments | Low | `--principal` fallback for CI/CD without OIDC |
| Secret scanner false positives on test fixtures | Low | `exclude_patterns` config + inline suppression comments |
