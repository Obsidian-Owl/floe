# Feature Specification: E2E Platform Testing & Live Demo Mode

**Epic**: 13 (E2E Platform Testing & Live Demo)
**Feature Branch**: `13-e2e-demo-platform`
**Created**: 2026-02-02
**Status**: Draft
**Input**: User description: "Comprehensive E2E testing across ALL platform features with live demo mode showcasing multiple industry data products"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Platform Bootstrap & Service Health (Priority: P1)

As a platform operator, I deploy the floe platform to a Kind cluster and verify all services are healthy before running any workloads. This validates the foundational infrastructure: Dagster webserver/daemon, Polaris catalog, MinIO storage, PostgreSQL, and the OTel collector.

**Why this priority**: Nothing else works if the platform cannot bootstrap. This is the prerequisite for every other test.

**Independent Test**: Deploy `floe-platform` Helm chart to Kind cluster, verify all pods reach Ready state, verify all NodePort services respond on expected ports (Dagster:3000, Polaris:8181, MinIO:9000/9001, Jaeger:16686, Grafana:3001, Prometheus:9090).

**Acceptance Scenarios**:

1. **Given** a clean Kind cluster, **When** `helm install floe-platform` completes, **Then** all pods reach Ready within 120s and liveness probes pass
2. **Given** a running platform, **When** each NodePort service is queried, **Then** HTTP 200 responses are returned from Dagster UI, Polaris health, MinIO console, Jaeger UI, Grafana, and Prometheus
3. **Given** a running platform, **When** PostgreSQL is queried, **Then** Dagster and Polaris databases exist with correct schemas
4. **Given** a running platform, **When** MinIO is queried, **Then** the configured S3 buckets (warehouse, staging) exist

---

### User Story 2 - Compilation & Artifact Generation (Priority: P1)

As a data engineer, I write a `floe.yaml` configuration and compile it into `CompiledArtifacts` that drive all downstream platform behavior. This validates the 6-stage compilation pipeline (LOAD→VALIDATE→RESOLVE→ENFORCE→COMPILE→GENERATE), schema validation, and artifact integrity.

**Why this priority**: Compilation is the entry point for all data work. If artifacts are invalid, nothing downstream functions.

**Independent Test**: Run `floe compile` against demo `floe.yaml` files, validate output matches `CompiledArtifacts` schema v0.5.0, verify dbt profiles and Dagster config are generated correctly.

**Acceptance Scenarios**:

1. **Given** a valid `floe.yaml` with dbt models, warehouses, and environments, **When** `floe compile` runs, **Then** `CompiledArtifacts` JSON is produced matching schema v0.5.0
2. **Given** compiled artifacts, **When** the output is loaded by `floe-dagster`, **Then** Dagster assets and resources are created without errors
3. **Given** an invalid `floe.yaml` (missing required fields), **When** `floe compile` runs, **Then** Pydantic `ValidationError` is raised with descriptive messages
4. **Given** a `manifest.yaml` + `floe.yaml` pair, **When** compiled together, **Then** platform-team defaults are merged with data-engineer overrides correctly

---

### User Story 3 - Data Pipeline Execution (Priority: P1)

As a data engineer, I execute a complete data pipeline through all medallion layers (Bronze -> Silver -> Gold) and verify data lands correctly in Iceberg tables via Polaris catalog.

**Why this priority**: Data processing is the core value of the platform. This validates the entire data flow end-to-end.

**Independent Test**: Trigger a dbt run via Dagster, verify source ingestion, staging models, intermediate transforms, and mart outputs all complete successfully with data in Iceberg tables.

**Acceptance Scenarios**:

1. **Given** a compiled data product with dbt models, **When** a Dagster run is triggered, **Then** all dbt models execute successfully in dependency order
2. **Given** a completed dbt run, **When** Polaris catalog is queried, **Then** Iceberg tables exist with correct schemas and row counts > 0
3. **Given** a pipeline with Bronze/Silver/Gold models, **When** executed, **Then** each layer transforms data correctly (Bronze=raw, Silver=cleaned, Gold=aggregated)
4. **Given** seed data files, **When** `dbt seed` runs, **Then** data is loaded into staging tables and available for downstream models

---

### User Story 4 - Observability & Lineage (Priority: P2)

As a platform operator, I verify that every pipeline execution produces OpenTelemetry traces, OpenLineage events, and structured logs that are queryable through the observability stack.

**Why this priority**: Without observability, operators cannot debug failures or understand data flow. Critical for production readiness but not blocking basic functionality.

**Independent Test**: Run a pipeline, then query Jaeger for traces, verify OpenLineage events were emitted at all 4 emission points, check Grafana dashboards show metrics.

**Acceptance Scenarios**:

1. **Given** a completed pipeline run, **When** Jaeger is queried, **Then** traces exist with spans for each dbt model execution including parent-child relationships
2. **Given** a completed pipeline run, **When** OpenLineage events are queried, **Then** START/COMPLETE/FAIL events exist for each job with correct input/output dataset facets
3. **Given** the OTel collector is running, **When** metrics are scraped by Prometheus, **Then** pipeline duration, model count, and error rate metrics are available
4. **Given** a pipeline failure, **When** logs are queried, **Then** structured log entries with trace_id correlation exist for root cause analysis

---

### User Story 5 - Plugin System Validation (Priority: P2)

As a plugin developer, I verify that all 15 plugin types are discoverable via entry points, comply with their ABCs, and can be swapped at runtime without code changes.

**Why this priority**: The plugin system is the extensibility foundation. Validating it ensures the platform architecture is sound.

**Independent Test**: Load each plugin type via entry point discovery, verify ABC compliance, test that swapping plugin implementations (e.g., DuckDB -> Spark compute) works without code changes.

**Acceptance Scenarios**:

1. **Given** the plugin registry, **When** all entry points are loaded, **Then** all 15 plugin ABCs are defined and at least 12 have registered implementations (Ingestion, Semantic, Storage may be unimplemented)
2. **Given** a plugin ABC (e.g., `CatalogPlugin`), **When** each implementation is instantiated, **Then** all abstract methods are implemented and callable
3. **Given** a `floe.yaml` specifying `compute: duckdb`, **When** changed to `compute: spark`, **Then** compilation succeeds and Dagster assets use the new compute backend
4. **Given** a custom plugin package installed via pip, **When** `floe compile` runs, **Then** the custom plugin is discovered and integrated automatically

---

### User Story 6 - Governance & Security (Priority: P2)

As a platform operator, I verify that RBAC, network policies, secret management, and security scanning are correctly configured and enforced across the platform.

**Why this priority**: Security is non-negotiable for production but can be validated after basic functionality works.

**Independent Test**: Verify K8s NetworkPolicies restrict traffic, secrets are managed via K8s Secrets (not hardcoded), RBAC roles limit access, and security scanning passes.

**Acceptance Scenarios**:

1. **Given** deployed NetworkPolicies, **When** a pod attempts to reach an unauthorized service, **Then** the connection is denied
2. **Given** platform secrets (DB passwords, API keys), **When** pod specs are inspected, **Then** all secrets are referenced via K8s Secret objects, never hardcoded
3. **Given** Polaris catalog, **When** a principal without `TABLE_READ` privilege queries a table, **Then** access is denied with 403
4. **Given** the platform codebase, **When** Bandit and pip-audit run, **Then** zero critical/high vulnerabilities are reported

---

### User Story 7 - Artifact Promotion Lifecycle (Priority: P2)

As a platform operator, I promote artifacts through dev -> staging -> prod environments, verifying that promotion gates (policy checks, security scan, signature verification) are enforced at each stage.

**Why this priority**: Promotion is essential for production workflows but depends on compilation and deployment working first.

**Independent Test**: Compile artifacts for dev, promote to staging with gate checks, then to prod. Verify each gate blocks on failure.

**Acceptance Scenarios**:

1. **Given** a compiled artifact in dev, **When** promotion to staging is requested, **Then** policy checks and security scan gates execute before promotion
2. **Given** a promotion with a failing gate (e.g., security vulnerability), **When** promotion is attempted, **Then** it is blocked with a descriptive reason
3. **Given** a successfully promoted artifact, **When** the staging environment is inspected, **Then** the artifact version matches and deployment succeeds
4. **Given** a promotion history, **When** queried, **Then** an audit trail shows who promoted what, when, and which gates passed

---

### User Story 8 - Live Demo Mode (Priority: P3)

As a sales engineer, I run a live demo showing the floe platform processing real data across 3 industry verticals (retail customer-360, manufacturing IoT telemetry, financial risk scoring), with observable outputs on dashboards.

**Why this priority**: Demo mode is the highest-visibility feature but depends on all other stories working. It's the showcase, not the foundation.

**Independent Test**: Run `make demo` which bootstraps the platform, loads seed data for all 3 industries, executes pipelines, and opens dashboards showing live results.

**Acceptance Scenarios**:

1. **Given** a clean Kind cluster, **When** `make demo` runs, **Then** the platform bootstraps, loads all 3 data products, and pipelines complete within 10 minutes
2. **Given** the demo is running, **When** Dagster UI is opened, **Then** 3 data products are visible with asset lineage graphs showing Bronze->Silver->Gold flow
3. **Given** the demo is running, **When** Grafana dashboards are opened, **Then** pipeline metrics, data quality scores, and lineage visualizations are displayed
4. **Given** the demo is running, **When** Jaeger UI is opened, **Then** traces for all 3 data products are visible with cross-pipeline correlation

---

### User Story 9 - Multi-Product Coexistence & Schema Evolution (Priority: P3)

As a data engineer, I deploy multiple data products simultaneously and evolve their schemas over time, verifying that Iceberg schema evolution and partition management work correctly without breaking existing consumers.

**Why this priority**: Multi-tenancy and schema evolution are advanced platform capabilities needed for production but not for initial validation.

**Independent Test**: Deploy 2+ data products, evolve one schema (add column), verify existing queries still work and new column is available.

**Acceptance Scenarios**:

1. **Given** 3 data products deployed simultaneously, **When** each pipeline runs, **Then** all complete without resource conflicts or namespace collisions
2. **Given** an Iceberg table with schema v1, **When** a column is added (schema v2), **Then** existing queries return results (with null for new column) and new queries can use the column
3. **Given** multiple data products sharing a Polaris catalog, **When** namespaces are listed, **Then** each product has its own namespace with isolated tables
4. **Given** a partitioned Iceberg table, **When** partition spec is evolved, **Then** new data uses new partitioning while old data remains queryable

---

### Edge Cases

- What happens when a pod crashes mid-pipeline? Verify Dagster run failure is recorded and pipeline can be retried
- What happens when Polaris catalog is temporarily unavailable? Verify graceful degradation and retry
- What happens when MinIO storage runs out of space? Verify descriptive error and pipeline failure (not silent data loss)
- What happens when two pipelines write to the same Iceberg table concurrently? Verify Iceberg ACID guarantees prevent corruption
- What happens when a dbt model has a SQL syntax error? Verify compilation catches it before execution
- What happens when OTel collector is down? Verify pipelines still execute (observability is non-blocking)
- What happens when a promotion gate service is unreachable? Verify promotion blocks (fail-closed)
- What happens when seed data files are malformed? Verify descriptive validation errors before pipeline starts

## Requirements *(mandatory)*

### Functional Requirements

#### Platform Bootstrap (FR-001 to FR-008)

- **FR-001**: System MUST deploy all platform services (Dagster, Polaris 1.1.0+ Quarkus-based, MinIO, PostgreSQL, OTel Collector) via `floe-platform` Helm chart to a Kind cluster
- **FR-002**: System MUST verify all pods reach Ready state within a configurable timeout (default 120s)
- **FR-003**: System MUST verify all NodePort services respond on expected ports with health checks
- **FR-004**: System MUST verify PostgreSQL databases (dagster, polaris) are created with correct schemas
- **FR-005**: System MUST verify MinIO buckets (warehouse, staging) are created
- **FR-006**: System MUST verify OTel Collector receives and forwards telemetry data
- **FR-007**: System MUST verify Jaeger, Grafana, and Prometheus UIs are accessible
- **FR-008**: System MUST provide a single `make e2e` command that runs all E2E tests in dependency order, with full namespace teardown between test suites to ensure isolation

#### Compilation & Artifacts (FR-010 to FR-017)

- **FR-010**: System MUST compile `floe.yaml` into `CompiledArtifacts` matching schema v0.5.0
- **FR-011**: System MUST validate all 6 compilation stages (LOAD→VALIDATE→RESOLVE→ENFORCE→COMPILE→GENERATE) execute in order
- **FR-012**: System MUST merge `manifest.yaml` (platform defaults) with `floe.yaml` (engineer overrides)
- **FR-013**: System MUST generate valid dbt `profiles.yml` from compiled artifacts
- **FR-014**: System MUST generate valid Dagster resource configuration from compiled artifacts. Each data product MUST be a separate code location in workspace.yaml, discovered via `python_file` pointing to its generated `definitions.py`. Supports independent deployment per FR-086
- **FR-015**: System MUST reject invalid `floe.yaml` with Pydantic ValidationError and descriptive messages
- **FR-016**: System MUST produce deterministic output (same input = same output, byte-for-byte)
- **FR-017**: System MUST export JSON Schema for IDE autocomplete of `floe.yaml`

#### Data Pipeline (FR-020 to FR-033)

- **FR-020**: System MUST execute dbt models in correct dependency order via Dagster orchestration
- **FR-021**: System MUST support Bronze (raw), Silver (cleaned), and Gold (aggregated) medallion layers
- **FR-022**: System MUST write all model outputs to Iceberg tables via Polaris catalog, with S3FileIO configured to persist data in MinIO buckets (NOT InMemoryFileIO)
- **FR-023**: System MUST support dbt seed files for loading test/demo data
- **FR-024**: System MUST support dbt tests (schema tests + data tests) executing after model runs
- **FR-025**: System MUST support incremental models with correct merge behavior
- **FR-026**: System MUST support data quality checks via dbt-expectations or Great Expectations plugin
- **FR-027**: System MUST handle pipeline failures gracefully with Dagster run failure recording
- **FR-028**: System MUST support pipeline retry from failure point (not full re-run)
- **FR-029**: System MUST auto-trigger the first pipeline run once all platform services are healthy (sensor-based). E2E test MUST validate full sensor execution: deploy platform → sensor detects health → sensor fires RunRequest → Dagster run completes successfully
- **FR-030**: System MUST support recurring scheduled execution at a configurable interval (default: 10 minutes)
- **FR-031**: System MUST enforce data retention of 1 hour maximum, with timestamp-based cleanup removing older records
- **FR-032**: System MUST support Iceberg snapshot expiry to prevent unbounded storage growth in long-running demos
- **FR-033**: System MUST support sensor-triggered pipeline execution via Dagster sensors

#### Observability (FR-040 to FR-048)

- **FR-040**: System MUST emit OpenTelemetry traces for every pipeline execution with span-per-model granularity
- **FR-041**: System MUST emit OpenLineage START/COMPLETE/FAIL events at all 4 emission points (dbt model start, dbt model complete, Dagster asset materialization, pipeline run completion)
- **FR-042**: System MUST correlate trace_id between OTel traces and OpenLineage events
- **FR-043**: System MUST expose pipeline metrics (duration, model count, error rate) via Prometheus
- **FR-044**: System MUST provide Grafana dashboards for pipeline monitoring
- **FR-045**: System MUST provide structured logs with trace_id correlation via structlog
- **FR-046**: System MUST ensure observability is non-blocking (pipeline executes even if collector is down)
- **FR-047**: System MUST forward traces to Jaeger and make them queryable by service name
- **FR-048**: System MUST provide lineage visualization via both Dagster UI (asset lineage) and Marquez (OpenLineage server) showing data flow across models and tables
- **FR-049**: System MUST include Marquez as a sub-chart in the `floe-platform` Helm chart with NodePort access. Marquez database backend MUST be configurable via `manifest.yaml` (shared PostgreSQL with separate database, or dedicated instance). Default: shared PostgreSQL. Platform engineers own this decision, not tests/demos

#### Plugin System (FR-050 to FR-056)

- **FR-050**: System MUST discover all 15 plugin types via Python entry points at runtime (12 with implementations, 3 ABCs only: Ingestion, Semantic, Storage)
- **FR-051**: System MUST validate each plugin implementation against its ABC interface
- **FR-052**: System MUST support plugin swapping via `floe.yaml` configuration without code changes
- **FR-053**: System MUST support custom third-party plugins installed via pip
- **FR-054**: System MUST validate plugin compatibility at compile time (not runtime)
- **FR-055**: System MUST provide plugin health checks verifiable during platform bootstrap
- **FR-056**: System MUST maintain backwards compatibility for plugin ABCs within a major version

#### Governance & Security (FR-060 to FR-067)

- **FR-060**: System MUST deploy K8s NetworkPolicies restricting inter-service traffic to declared dependencies
- **FR-061**: System MUST manage all secrets via K8s Secret objects (no hardcoded credentials)
- **FR-062**: System MUST enforce Polaris RBAC (principals, roles, privileges) for catalog access
- **FR-063**: System MUST pass Bandit security scanning with zero critical/high findings
- **FR-064**: System MUST pass pip-audit with zero critical/high vulnerabilities
- **FR-065**: System MUST use SecretStr for all password/API key fields in Pydantic models
- **FR-066**: System MUST never expose stack traces or internal paths in user-facing error messages
- **FR-067**: System MUST log security events (auth failures, privilege violations) via structured logging

#### Artifact Promotion (FR-070 to FR-075)

- **FR-070**: System MUST support artifact promotion through dev -> staging -> prod environments, represented as K8s namespaces (`floe-dev`, `floe-staging`, `floe-prod`) within a single Kind cluster
- **FR-071**: System MUST enforce promotion gates (policy check, security scan, signature verification) at each stage, deployed as real K8s services (OPA, Sigstore, etc.) in the Kind cluster — not mock responses
- **FR-072**: System MUST block promotion when any gate fails (fail-closed)
- **FR-073**: System MUST maintain an audit trail of all promotions (who, what, when, gates passed)
- **FR-074**: System MUST support rollback to a previous artifact version
- **FR-075**: System MUST support manual approval gate for production promotion

#### Demo Data Products (FR-080 to FR-088)

- **FR-080**: System MUST include a `customer-360` data product (retail: customer profiles, transactions, segments)
- **FR-081**: System MUST include an `iot-telemetry` data product (manufacturing: sensor readings, anomaly detection, maintenance alerts)
- **FR-082**: System MUST include a `financial-risk` data product (finance: positions, risk scores, regulatory reports)
- **FR-083**: Each data product MUST include seed data for reproducible demos, with configurable volume (default: 100-1K rows per table, configurable via `FLOE_DEMO_SEED_SCALE` env var)
- **FR-084**: Each data product MUST include Bronze, Silver, and Gold layer models
- **FR-085**: Each data product MUST include dbt tests validating data quality at each layer
- **FR-086**: Each data product MUST be deployable independently or as part of the full demo
- **FR-087**: System MUST provide a `make demo` command that deploys all 3 products and opens dashboards
- **FR-088**: Demo MUST complete end-to-end within 10 minutes on a standard developer machine

#### Schema Evolution (FR-090 to FR-094)

- **FR-090**: System MUST support Iceberg schema evolution (add column) without breaking existing queries — old queries return null for new column, new queries can use it
- **FR-091**: System MUST support Iceberg partition spec evolution — new data uses new partitioning while old data remains queryable under old spec
- **FR-092**: System MUST support Iceberg time-travel queries — users can query a table as of a specific snapshot ID or timestamp
- **FR-093**: System MUST isolate multiple data products in separate Polaris namespaces — no table name collisions, independent schema evolution per product
- **FR-094**: System MUST ensure backward-compatible schema changes only — dropping columns or changing types MUST be rejected at compile time with descriptive error

### Key Entities

- **DataProduct**: A self-contained set of dbt models, seeds, tests, and configuration representing a business domain (e.g., customer-360). Key attributes: name, industry, layers (Bronze/Silver/Gold), seed data, quality checks.
- **CompiledArtifacts**: The sole cross-package contract (v0.5.0). Contains dbt profiles, Dagster config, environment config, and plugin configuration. Produced by floe-core, consumed by floe-dagster.
- **PromotionRecord**: An audit entry tracking artifact movement between environments. Key attributes: artifact version, source env, target env, gates passed, promoter, timestamp.
- **PlatformService**: A K8s-deployed service (Dagster, Polaris 1.1.0+ Quarkus-based, MinIO, PostgreSQL, OTel Collector). Key attributes: name, port, health endpoint, readiness probe, dependencies.
- **Plugin**: An implementation of one of 15 plugin ABCs. Key attributes: type, name, entry point, ABC interface, configuration schema, health check. The 15 types are: Catalog, Compute, DBT, Identity, Ingestion, Lineage, NetworkSecurity, Orchestrator, Quality, RBAC, Secrets, SemanticLayer, Storage, Telemetry, plus PluginLoader (registry). 12 have concrete implementations; Ingestion, Semantic, and Storage are ABC-only.

## Test Quality Requirements *(mandatory)*

**Context**: Research analysis (2026-02-03) revealed critical gaps in E2E test design. Tests were validating "infrastructure exists" rather than "platform works as promised". This section establishes non-negotiable quality standards.

### Test Quality Score Target

**Minimum acceptable score: 80/100** (current baseline: 20/100)

| Dimension | Weight | Requirement |
|-----------|--------|-------------|
| Behavioral Validation | 30% | Tests MUST validate platform BEHAVIOR, not just existence |
| Promise Coverage | 25% | Every platform promise MUST have test coverage |
| Anti-Pattern Free | 20% | Zero instances of prohibited patterns |
| Edge Case Coverage | 15% | Error paths, failures, retries tested |
| Determinism | 10% | No flaky tests, no timing dependencies |

### Behavioral Validation Requirements (MANDATORY)

**TQR-001**: Tests MUST validate actual behavior, not just object existence.

```python
# ❌ FORBIDDEN - Existence-only validation
def test_compilation():
    artifacts = compile_spec(spec)
    assert artifacts is not None  # MEANINGLESS

# ✅ REQUIRED - Behavioral validation
def test_compilation():
    artifacts = compile_spec(spec)
    assert artifacts.metadata.product_name == "customer-360"
    assert len(artifacts.transforms) == 6  # Expected model count
    assert artifacts.plugins.orchestrator.type == "dagster"
    assert "stg_customers" in [t.name for t in artifacts.transforms]
```

**TQR-002**: Tests MUST validate data content, not just table existence.

```python
# ❌ FORBIDDEN - Table existence only
def test_iceberg_tables():
    tables = catalog.list_tables("customer-360")
    assert len(tables) > 0  # PROVES NOTHING

# ✅ REQUIRED - Data content validation
def test_iceberg_tables():
    table = catalog.load_table("customer-360.mart_customer_360")
    df = table.scan().to_pandas()
    assert len(df) > 0, "Table must have data"
    assert "customer_id" in df.columns
    assert df["customer_id"].nunique() > 0, "Must have distinct customers"
    assert df["total_orders"].sum() > 0, "Must have order aggregations"
```

**TQR-003**: Tests MUST validate orchestration execution, not just asset creation.

```python
# ❌ FORBIDDEN - Asset existence only
def test_dagster_assets():
    assets = load_assets_from_artifacts(artifacts)
    assert len(assets) > 0  # MEANINGLESS

# ✅ REQUIRED - Actual orchestration execution
def test_dagster_pipeline_execution():
    with DagsterInstance.get() as instance:
        result = execute_job(
            job=create_dbt_assets_job(artifacts),
            instance=instance
        )
        assert result.success, f"Job failed: {result.all_events}"
        # Validate actual materialization
        for event in result.get_asset_materialization_events():
            assert event.asset_key is not None
            metadata = event.materialization.metadata
            assert "row_count" in metadata
            assert metadata["row_count"].value > 0
```

**TQR-004**: Tests MUST use REAL compilation pipeline, not fixtures/mocks.

```python
# ❌ FORBIDDEN - Fixture bypass
@pytest.fixture
def compiled_artifacts():
    return CompiledArtifacts(...)  # Hand-crafted mock

# ✅ REQUIRED - Real compilation
@pytest.fixture
def compiled_artifacts(demo_data_product_path):
    """Compile REAL floe.yaml through REAL pipeline."""
    return compile_pipeline(
        spec_path=demo_data_product_path / "floe.yaml",
        manifest_path=demo_data_product_path / "manifest.yaml"
    )
```

### Prohibited Anti-Patterns (ZERO TOLERANCE)

**TQR-010**: NEVER use `dry_run=True` in E2E tests.

```python
# ❌ FORBIDDEN
result = helm_install(chart="floe-platform", dry_run=True)
assert result.success  # Tests NOTHING

# ✅ REQUIRED - Real deployment
result = helm_install(chart="floe-platform", namespace="floe-test")
wait_for_pods_ready(namespace="floe-test", timeout=120)
```

**TQR-011**: NEVER use existence checks without value validation.

```python
# ❌ FORBIDDEN patterns
assert obj is not None
assert len(items) > 0
assert result.success  # Without checking what succeeded

# ✅ REQUIRED - Value validation
assert obj.name == expected_name
assert items == expected_items
assert result.output["tables_created"] == 6
```

**TQR-012**: NEVER leave TODO comments in production test code.

```python
# ❌ FORBIDDEN
def test_observability():
    # TODO: Add actual trace validation
    assert True  # Placeholder

# ✅ REQUIRED - Complete implementation or remove test
def test_observability():
    traces = jaeger_client.search(service="floe-dagster", limit=10)
    assert len(traces) >= 1, "Must have at least one trace"
    trace = traces[0]
    assert len(trace.spans) >= 3, "Must have spans for each dbt model"
```

**TQR-013**: NEVER use `pytest.skip()` or `@pytest.mark.skip` in E2E tests.

```python
# ❌ FORBIDDEN
@pytest.mark.skip("Service not deployed")
def test_polaris_integration():
    ...

# ✅ REQUIRED - Test FAILS if infrastructure missing
def test_polaris_integration(polaris_client):
    """Test FAILS if Polaris not available - this is correct behavior."""
    catalogs = polaris_client.list_catalogs()
    assert "floe" in [c.name for c in catalogs]
```

**TQR-014**: NEVER test wrong technology for the platform promise.

```python
# ❌ FORBIDDEN - Testing DuckDB when promise is Iceberg via Polaris
def test_iceberg_tables():
    conn = duckdb.connect()
    result = conn.execute("SELECT * FROM customer_360").fetchall()
    # This tests DuckDB, NOT Iceberg table via Polaris!

# ✅ REQUIRED - Test the actual promised technology
def test_iceberg_tables(polaris_catalog):
    table = polaris_catalog.load_table("customer-360.mart_customer_360")
    snapshots = table.metadata.snapshots
    assert len(snapshots) >= 1, "Must have at least one snapshot"
    df = table.scan().to_pandas()
    assert len(df) > 0
```

### Platform Promise Coverage Requirements (MANDATORY)

Each platform promise MUST have explicit test coverage:

**TQR-020: Compilation Promise** - Tests: `test_compilation.py`
- [ ] 6-stage pipeline executes in order (LOAD→VALIDATE→RESOLVE→ENFORCE→COMPILE→GENERATE)
- [ ] Invalid spec produces Pydantic ValidationError with actionable message
- [ ] CompiledArtifacts schema v0.5.0 validated
- [ ] Deterministic output (same input = same output)

**TQR-021: Bootstrap Promise** - Tests: `test_platform_bootstrap.py`
- [ ] All pods reach Ready state within 120s
- [ ] All services respond on health endpoints
- [ ] Database schemas created correctly
- [ ] S3 buckets exist

**TQR-022: Pipeline Promise** - Tests: `test_data_pipeline.py`
- [ ] dbt models execute in dependency order via Dagster
- [ ] Data lands in Iceberg tables via Polaris (NOT DuckDB directly)
- [ ] Bronze→Silver→Gold transformation produces expected output
- [ ] Row counts and data quality match expectations

**TQR-023: Observability Promise** - Tests: `test_observability.py`
- [ ] OpenTelemetry traces queryable in Jaeger with span-per-model
- [ ] OpenLineage events at all 4 emission points
- [ ] Trace ID correlation between OTel and OpenLineage
- [ ] Grafana dashboards show pipeline metrics

**TQR-024: Governance Promise** - Tests: `test_governance.py`
- [ ] NetworkPolicies actually block unauthorized traffic (not just exist)
- [ ] Polaris RBAC denies unauthorized access (real auth test)
- [ ] Secrets not hardcoded in any pod spec
- [ ] Security scanning passes

**TQR-025: Plugin Promise** - Tests: `test_plugin_system.py`
- [ ] All 15 plugin ABCs defined; 12 with implementations discoverable via entry points
- [ ] ABC compliance validated for each implementation
- [ ] Plugin swap works without code changes (actual swap test)

**TQR-026: Promotion Promise** - Tests: `test_promotion.py`
- [ ] Artifacts promote through dev→staging→prod namespaces
- [ ] Gates block on failure (actually test blocking)
- [ ] Audit trail captures all promotions

**TQR-027: Demo Promise** - Tests: `test_demo_mode.py`, `test_demo_flow.py`
- [ ] All 3 data products deploy and execute
- [ ] Pipelines complete within 10 minutes
- [ ] Dashboards show real data (not just load)

### Critical Gap Tests (MUST IMPLEMENT)

The following gaps were identified by research and MUST have tests before epic completion:

| Gap ID | Description | Required Test |
|--------|-------------|---------------|
| GAP-001 | Auto-trigger pipeline on service health (FR-029) | `test_auto_trigger_sensor.py` |
| GAP-002 | Data retention enforcement (FR-031) | `test_data_retention.py` |
| GAP-003 | Iceberg snapshot expiry (FR-032) | `test_snapshot_retention.py` |
| GAP-004 | Trace content validation (not just existence) | `test_trace_content.py` |
| GAP-005 | OpenLineage emission at 4 points (FR-041) | `test_openlineage_events.py` |
| GAP-006 | Compilation fixture bypass | Fix existing tests |
| GAP-007 | DuckDB testing instead of Iceberg | Fix existing tests |
| GAP-008 | Plugin swap test (actual swap) | `test_plugin_swap.py` |
| GAP-009 | Promotion gate blocking (actual block) | `test_promotion_gates.py` |
| GAP-010 | Schema evolution test (FR-090-094) | `test_schema_evolution.py` |

### Test Review Checklist

Before any E2E test is considered complete:

- [ ] **Behavioral**: Does it test WHAT the platform does, not just THAT something exists?
- [ ] **Real**: Does it use real compilation/deployment, not fixtures/mocks?
- [ ] **Technology**: Does it test the promised technology (Iceberg via Polaris, not DuckDB)?
- [ ] **Complete**: No TODOs, no placeholders, no `assert True`?
- [ ] **Anti-pattern free**: No `dry_run`, no `is not None` without value check?
- [ ] **Requirement linked**: Has `@pytest.mark.requirement()` marker?
- [ ] **Documented**: Has docstring explaining what behavior is validated?

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All platform services reach Ready state within 120s of Helm install on a Kind cluster
- **SC-002**: `floe compile` produces valid `CompiledArtifacts` for all 3 demo data products without errors
- **SC-003**: All 3 demo pipelines (customer-360, iot-telemetry, financial-risk) complete successfully with data in Iceberg tables
- **SC-004**: OTel traces are queryable in Jaeger for every pipeline execution with <5s latency
- **SC-005**: OpenLineage events are emitted at all 4 emission points with correct dataset facets
- **SC-006**: All 15 plugin ABCs are defined; at least 12 have discoverable implementations passing ABC compliance (Ingestion, Semantic, Storage are ABC-only)
- **SC-007**: `make demo` completes end-to-end (bootstrap + 3 data products + dashboards) within 10 minutes
- **SC-008**: Zero critical/high security findings from Bandit + pip-audit + NetworkPolicy validation
- **SC-009**: Artifact promotion gates block on failure and pass on success with audit trail
- **SC-010**: `make e2e` runs all E2E tests in CI with 100% pass rate and requirement traceability

## Clarifications

- Q: How should dev/staging/prod environments be represented for promotion E2E tests in the Kind cluster? A: K8s namespaces within a single Kind cluster (dev/staging/prod as separate namespaces with namespace isolation).
- Q: What seed data volume per demo data product? A: Configurable via environment variable or config flag, defaulting to small (100-1K rows per table) for fast demos with option to increase for realistic volumes.
- Q: For lineage visualization (FR-048), Dagster UI or Marquez? A: Both - Dagster UI for asset lineage plus Marquez as dedicated OpenLineage server (requires adding Marquez sub-chart to floe-platform Helm chart).
- Q: For schedule/sensor E2E tests (FR-029, FR-030), how should schedules work? A: Auto-trigger first job once all services healthy, then 10-minute recurring schedule. Data retention limited to 1 hour - requires timestamp-based cleanup and Iceberg snapshot expiry to prevent unbounded data growth in long-running demos.
- Q: Schema evolution is in US9 but has no dedicated FRs (GAP-010 referenced non-existent FR-155-158). Should explicit FRs be added? A: Yes. Added FR-090 to FR-094 covering: add column evolution, partition spec evolution, time-travel query, multi-product namespace isolation, backward-compatible schema enforcement. All testable.
- Q: What test isolation strategy for E2E tests sharing a Kind cluster? A: Full namespace teardown between test suites. Each suite deploys fresh and tears down everything after. Maximum isolation. Prevents state leakage between test classes.
- Q: Should Polaris use S3FileIO with MinIO or InMemoryFileIO for storage? A: S3FileIO + MinIO required. Polaris MUST be configured with S3FileIO pointing to MinIO. Tests MUST validate data persists in S3 buckets. InMemoryFileIO is forbidden in E2E tests — it doesn't test real data persistence.
- Q: Should the auto-trigger sensor test (FR-029) validate full execution or just sensor definition? A: Full sensor execution. Test must validate: deploy platform → health sensor fires → RunRequest triggered → Dagster run completes successfully. No existence-only checks.
- Q: How should Dagster discover code locations for data products? A: workspace.yaml multi-location. Each data product is a separate code location, discovered via python_file pointing to its generated definitions.py. Supports independent deployment (FR-086). No monolithic single Definitions object.
- Q: Which Polaris version should the spec target? A: Polaris 1.1.0+ (Quarkus-based). Native S3/MinIO FileIO support, actively maintained Apache project. Breaking change from 0.9.0 (different config format). Required to satisfy FR-022 S3FileIO requirement without patching.
- Q: Should Marquez share PostgreSQL or have its own? A: Configurable via manifest.yaml. Default: shared PostgreSQL (separate 'marquez' database). Platform engineers choose, not hardcoded in tests/demos. Tests use whatever the manifest configures.
- Q: Should promotion gates (FR-071) be real external services or simulated in Kind? A: External services in cluster. Deploy OPA server, Sigstore, etc. as K8s services. Maximum fidelity. Tests must prove gates actually block/pass with real services, not mock responses.
- Q: How many plugin types does the platform have (spec referenced 13 and 12 inconsistently)? A: 15 plugin ABCs defined in floe-core (Catalog, Compute, DBT, Identity, Ingestion, Lineage, NetworkSecurity, Orchestrator, Quality, RBAC, Secrets, SemanticLayer, Storage, Telemetry, PluginLoader). 12 have concrete implementations across 15 plugin packages. 3 are ABC-only (Ingestion, Semantic, Storage). Validated via codebase research 2026-02-04.

---

## Appendix A: Test Quality Research Findings (2026-02-03)

This appendix documents the research analysis that informed the Test Quality Requirements section.

### Research Methodology

Five parallel research stages were conducted:
1. **Vision & Promises Analysis**: Extracted 8 core platform promises from spec and architecture docs
2. **Test Audit**: Graded each existing test file A-F based on behavioral validation
3. **Gap Analysis**: Identified 19 gaps (13 critical) between promises and test coverage
4. **Anti-Pattern Detection**: Found 14 anti-pattern instances across test files
5. **Best Practices Research**: Compiled 35+ patterns from industry standards

### Test Quality Scores (Pre-Research)

| Test File | Grade | Issue |
|-----------|-------|-------|
| `test_platform_bootstrap.py` | C | Tests pod existence, not service behavior |
| `test_compilation.py` | D | Fixture bypasses real compilation pipeline |
| `test_data_pipeline.py` | B | Best test - actually runs dbt and validates data |
| `test_observability.py` | D | Tests trace existence, not content/correlation |
| `test_governance.py` | C | Tests resource existence, not enforcement |
| `test_plugin_system.py` | D | Tests entry point loading, not actual plugin behavior |
| `test_promotion.py` | C | Tests namespace existence, not actual promotion flow |
| `test_demo_flow.py` | D | Uses `dry_run=True`, tests nothing real |
| `test_demo_mode.py` | C | Limited behavioral validation |
| `test_schema_evolution.py` | D | Tests DuckDB, not Iceberg schema evolution |

**Overall Score**: 20/100

### Critical Anti-Patterns Found

1. **`dry_run=True` usage** (test_demo_flow.py:45) - Tests nothing real
2. **Compilation fixture bypass** (conftest.py) - Creates fake CompiledArtifacts
3. **`is not None` without value check** (9 instances across tests)
4. **TODO comments as placeholders** (4 instances)
5. **Testing wrong technology** (test_schema_evolution tests DuckDB, not Iceberg via Polaris)

### Platform Promises Not Covered

| Promise | FR | Test Coverage |
|---------|-----|---------------|
| Auto-trigger on health | FR-029 | ❌ None |
| Data retention | FR-031 | ❌ None |
| Snapshot expiry | FR-032 | ❌ None |
| OpenLineage 4 emission points | FR-041 | ❌ Partial (existence only) |
| Trace correlation | FR-042 | ❌ None |
| Plugin swap at runtime | FR-052 | ❌ None |
| Promotion gate blocking | FR-072 | ❌ None |

### Key Insight

> "Tests validate that infrastructure exists, not that the platform works as promised."

The floe platform makes 8 core promises to users:
1. Compile floe.yaml into platform-ready artifacts
2. Bootstrap all services reliably
3. Execute data pipelines through medallion layers
4. Provide full observability (traces, lineage, metrics)
5. Enforce governance (RBAC, policies, security)
6. Support pluggable architecture
7. Enable artifact promotion with gates
8. Demonstrate with real industry data products

Each promise requires behavioral validation tests - not existence checks.

### Research Impact

This research directly informed:
- TQR-001 through TQR-014 (behavioral validation requirements)
- TQR-020 through TQR-027 (promise coverage requirements)
- GAP-001 through GAP-010 (critical gap tests)
- Test Review Checklist (quality gates)

**Target**: Raise test quality score from 20/100 to 80/100 minimum before epic completion.
