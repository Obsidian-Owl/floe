Snapshot: 2026-03-19T14:15:00Z
Files: 1104 | Modules: 12

# Floe Codebase Landscape

## Architecture

Four-layer model: Foundation (PyPI packages) → Configuration (OCI artifacts) → Services (K8s Deployments) → Data (K8s Jobs). Config flows DOWN only.

Two-file configuration: `manifest.yaml` (platform team, rarely changes) + `floe.yaml` (data engineers, frequent changes). Compiled via `floe compile` into `CompiledArtifacts` — the sole cross-package contract.

Plugin-first architecture: 14 plugin categories via ABCs in `floe_core.plugins`. ENFORCED: Iceberg, dbt, OTel, OpenLineage, K8s. PLUGGABLE: compute, catalog, orchestrator, semantic, ingestion, storage, etc.

Technology ownership: dbt=SQL, Dagster=orchestration, Iceberg=storage, Polaris=catalog, Cube=semantic. Never cross boundaries.

## Modules

### `packages/floe-core/` — Core Platform Package

The central package. Schemas, compilation, CLI, plugins, telemetry, governance, RBAC.

| Submodule | Purpose | Key Files |
|-----------|---------|-----------|
| `schemas/` | Pydantic v2 models for FloeSpec, CompiledArtifacts, manifest, governance, RBAC | `floe_spec.py`, `compiled_artifacts.py`, `manifest.py`, `rbac.py` |
| `compilation/` | FloeSpec → CompiledArtifacts pipeline | `builder.py`, `stages.py`, `resolver.py`, `dbt_profiles.py` |
| `cli/` | Click-based CLI (`floe` command) | `main.py`, `platform/`, `rbac/`, `governance/`, `helm/`, `network/` |
| `plugins/` | 14 plugin ABCs + discovery + lifecycle | `compute.py`, `catalog.py`, `orchestrator.py`, `dbt.py`, `discovery.py` |
| `telemetry/` | OTel tracing/metrics init, structlog, tracer factory | `initialization.py`, `tracer_factory.py`, `logging.py`, `metrics.py` |
| `governance/` | Policy evaluation, RBAC checks, secret scanning | `integrator.py`, `policy_evaluator.py`, `rbac_checker.py` |
| `rbac/` | RBAC generation, validation, audit, diff | `generator.py`, `validate.py`, `audit.py`, `diff.py` |
| `contracts/` | Data contract monitoring | `generator.py`, `monitoring/` |
| `enforcement/` | Boundary enforcement (Iceberg, OTel, dbt, K8s) | — |
| `validation/` | Input validation, schema validation | — |

Public API: `compile_floe_spec()`, `FloeSpec`, `CompiledArtifacts`, `ensure_telemetry_initialized()`, `reset_telemetry()`, `get_tracer()`, plugin ABCs.

### `packages/floe-iceberg/` — Iceberg Storage Package

PyIceberg integration: table management, schema evolution, compaction, drift detection.

| File | Purpose |
|------|---------|
| `manager.py` | IcebergTableManager — CRUD, snapshot ops |
| `_schema_manager.py` | Schema evolution (add/drop/rename columns) |
| `_compaction_manager.py` | Table compaction (rewrite data files) |
| `_snapshot_manager.py` | Snapshot management (rollback, expire) |
| `drift_detector.py` | Schema drift detection vs expected |
| `models.py` | Pydantic models for Iceberg config |

### `plugins/` — 21 Plugin Implementations

Each plugin implements an ABC from `floe_core.plugins`. Standard structure: `src/{name}/plugin.py` + `tests/unit/`.

| Category | Plugins | ABC |
|----------|---------|-----|
| Compute | `floe-compute-duckdb` | `ComputePlugin` |
| Orchestrator | `floe-orchestrator-dagster` | `OrchestratorPlugin` |
| Catalog | `floe-catalog-polaris` | `CatalogPlugin` |
| dbt | `floe-dbt-core`, `floe-dbt-fusion` | `DbtPlugin` |
| Semantic | `floe-semantic-cube` | `SemanticPlugin` |
| Ingestion | `floe-ingestion-dlt` | `IngestionPlugin` |
| Quality | `floe-quality-dbt`, `floe-quality-gx` | `QualityPlugin` |
| Telemetry | `floe-telemetry-console`, `floe-telemetry-jaeger` | `TelemetryPlugin` |
| Lineage | `floe-lineage-marquez` | `LineagePlugin` |
| Secrets | `floe-secrets-infisical`, `floe-secrets-k8s` | `SecretsPlugin` |
| Identity | `floe-identity-keycloak` | `IdentityPlugin` |
| RBAC | `floe-rbac-k8s` | `RBACPlugin` |
| Network | `floe-network-security-k8s` | `NetworkSecurityPlugin` |
| Alerts | `floe-alert-alertmanager`, `-email`, `-slack`, `-webhook` | `AlertChannelPlugin` |

Plugin discovery: entry points in `pyproject.toml` → `floe_core.plugins.discovery`.

### `charts/floe-platform/` — Helm Chart

K8s deployment: Dagster, Polaris, Marquez, OTel Collector, PostgreSQL, MinIO, contract monitor.

Key templates: `deployment-*.yaml`, `configmap-*.yaml`, `job-polaris-bootstrap.yaml`, `networkpolicy.yaml`, `externalsecret.yaml`.

Sub-charts: `charts/floe-jobs/` (batch jobs), `charts/cognee-platform/` (memory), `charts/examples/`.

### `testing/` — Test Infrastructure

Shared test utilities used across all packages.

| Dir | Purpose |
|-----|---------|
| `base_classes/` | `IntegrationTestBase` — K8s-aware test base with infra checks, namespace gen |
| `fixtures/` | Service fixtures, polling utilities, K8s helpers |
| `traceability/` | Requirement traceability checker (`@pytest.mark.requirement`) |
| `k8s/` | K8s-specific test helpers, port-forward management |
| `ci/` | CI-specific test configuration |

### `tests/` — Root-Level Tests (Cross-Package)

| Dir | Purpose |
|-----|---------|
| `contract/` | Cross-package contract tests (CompiledArtifacts schema stability) |
| `e2e/` | Full platform E2E tests (compile → deploy → run → validate) |
| `integration/` | Cross-package integration tests |
| `unit/` | Root-level unit tests (shared utilities) |
| `fixtures/` | Shared test fixtures |

### `demo/` — Demo Data Products

Three demo products: `customer-360/`, `financial-risk/`, `iot-telemetry/`. Each has dbt models, seeds, and schema tests. Root `floe.yaml` + `manifest.yaml` + `datacontract.yaml`.

### `scripts/` — Developer Scripts

Memory management (`memory-save`, `memory-search`), architecture checks (`check-architecture-drift`), pre-commit helpers (`pre-commit-no-sleep.sh`, `pre-commit-constitution.sh`), Helm validation, agent tooling.

### `devtools/agent-memory/` — Agent Memory System

Cognee Cloud integration for persistent agent memory across sessions. Includes MCP server, CLI (`memory-save`, `memory-search`), contract tests for Cognee API field names (camelCase, not snake_case).

## Conventions

- `from __future__ import annotations` at top of every `.py` file
- Type hints on ALL functions (`mypy --strict`)
- Pydantic v2 syntax: `@field_validator`, `model_config = ConfigDict(...)`, `model_json_schema()`
- Structured logging via `structlog` (never `print()` or `logging`)
- Google-style docstrings on all public functions
- `ruff` for linting + formatting, `bandit` for security
- Tests: `@pytest.mark.requirement()` on all, no `pytest.skip()`, no `time.sleep()`
- Plugin structure: `src/{name}/plugin.py` implementing ABC, entry point registered
- Error hierarchy: `FloeError` base → domain-specific exceptions
- Secrets: `SecretStr` for passwords/keys, never hardcode, never log

## Integration Points

- **CompiledArtifacts**: sole cross-package contract (floe-core → all consumers)
- **Plugin ABCs**: `floe_core.plugins.*` → plugin implementations via entry points
- **OTel**: `ensure_telemetry_initialized()` bootstraps TracerProvider + MeterProvider; `get_tracer()` returns auto-upgrading proxies
- **Helm values**: `values.yaml` → Go templates → K8s resources; `values-test.yaml` for Kind cluster
- **CLI**: `floe` Click group → subcommands in `cli/platform/`, `cli/rbac/`, etc.
- **Testing**: `IntegrationTestBase` → K8s services; `@pytest.mark.requirement()` → traceability

## Gotchas

1. **PyIceberg server overrides**: `_fetch_config` merge order is `server_defaults < client_props < server_overrides`. Client-side `s3.endpoint` is IGNORED for table IO — server config wins.
2. **Dagster `context.metadata` deprecated**: Use `definition_metadata` + `output_metadata` in Dagster 2.0.
3. **`hasattr(context, "partition_key")` always True**: Returns True but raises `CheckError` on non-partitioned runs. Use `getattr(context, "has_partition_key", False)`.
4. **OTel reset asymmetry**: TracerProvider reset uses `None` (avoids recursion), MeterProvider needs fresh `_ProxyMeterProvider()` (restores auto-upgrade). See P47.
5. **Cognee API uses camelCase**: `textData` not `data`, `datasetName` not `dataset_name`. Wrong field names silently use defaults.
6. **dbt-fusion shadows dbt-core on PATH**: Resolve CLI tools from venv (`sys.executable` parent), not PATH.
7. **Float equality**: Never use `==` for floats. Use `pytest.approx()` in tests, `math.isclose()` in production.
8. **Calico CNI breaks after suspend**: All pod sandbox ops fail with TLS timeouts. Fix: `kubectl rollout restart daemonset/calico-node -n calico-system`.
9. **CWE-532 in exception handlers**: Never log `str(exc)` from transport errors — may contain credential-bearing URLs. Log `type(exc).__name__` only. See P45.
10. **Test fixtures duplicating OTel reset**: Call `reset_telemetry()` directly, don't duplicate private API manipulation. See P46.
