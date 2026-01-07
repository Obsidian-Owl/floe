# ADR-0016: Platform Enforcement Architecture

## Status

Accepted

## Context

Traditional data platform configurations mix platform concerns (compute targets, governance, service selection) with pipeline concerns (transforms, schedules) in a single configuration file. This leads to:

- Data engineers making platform decisions they shouldn't
- Inconsistent governance across teams
- Configuration drift between environments
- No clear ownership boundaries

We need an architecture that:
- Separates platform configuration from pipeline configuration
- Enforces platform guardrails at compile time
- Provides clear ownership boundaries between Platform Team and Data Team
- Prevents environment drift (same compute in dev/staging/prod)

## Decision

Adopt a **platform enforcement architecture** with:

1. **Two-File Configuration Model**
   - `manifest.yaml` - Platform Team defines guardrails (immutable)
   - `floe.yaml` - Data Engineers define pipelines (inherits platform constraints)

2. **Immutable Platform Artifacts**
   - Platform configuration is compiled to versioned OCI artifacts
   - Data pipelines reference and inherit from these artifacts
   - Non-compliant pipelines fail at compile time

3. **Environment-Agnostic Compute**
   - Compute target is set ONCE at platform level
   - Same compute across dev/staging/prod (no drift)
   - DuckDB is a viable production choice

4. **Four-Layer Architecture**
   - Layer 1: Foundation (framework code, open source)
   - Layer 2: Configuration (platform enforcement, immutable)
   - Layer 3: Services (long-lived, stateful)
   - Layer 4: Data (ephemeral jobs)

## Consequences

### Positive

- **Clear separation of concerns** - Platform Team owns infrastructure, Data Team owns transforms
- **Compile-time enforcement** - Non-compliant pipelines fail before runtime
- **No environment drift** - Same compute/policies across all environments
- **Versioned platform** - Platform changes are auditable via OCI registry
- **Governance by default** - Naming conventions, quality gates enforced automatically

### Negative

- **Two workflows** - Platform Team and Data Team have separate processes
- **Upfront planning** - Platform decisions must be made before data engineering starts
- **Version coordination** - Platform upgrades require data pipeline validation

### Neutral

- Platform Team uses `floe platform compile/publish/deploy`
- Data Team uses `floe init/compile/run`
- OCI registry becomes infrastructure requirement

## Configuration Model

### manifest.yaml (Platform Team)

```yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-data-platform
  version: "1.2.3"
  scope: enterprise

plugins:
  compute:
    type: duckdb        # Set ONCE, inherited by all pipelines
  orchestrator:
    type: dagster
  catalog:
    type: polaris
  semantic_layer:
    type: cube
  ingestion:
    type: dlt

data_architecture:
  pattern: medallion
  naming:
    enforcement: strict  # off | warn | strict

governance:
  quality_gates:
    minimum_test_coverage: 80
    block_on_failure: true
```

### floe.yaml (Data Team)

```yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-analytics
  version: "1.0"

platform:
  ref: oci://registry.acme.com/floe-platform:v1.2.3

# Data engineers ONLY define transforms and schedules
# All platform concerns are inherited
transforms:
  - type: dbt
    path: models/

schedule:
  cron: "0 6 * * *"
```

## Compile-Time Enforcement

```bash
$ floe compile

[1/4] Loading platform artifacts from oci://registry.acme.com/floe-platform:v1.2.3
      ✓ Platform version: 1.2.3
      ✓ Compute: duckdb
      ✓ Architecture: medallion (strict enforcement)

[2/4] Validating transforms
      ✓ 12 dbt models found

[3/4] Enforcing naming conventions
      ✓ bronze_customers: valid
      ✗ ERROR: 'stg_payments' violates naming convention
              Expected: bronze_*, silver_*, or gold_* prefix

[4/4] Compilation FAILED
```

## Four-Layer Architecture (Detailed)

The platform enforcement model defines four distinct layers with clear ownership and lifecycle:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: DATA (Ephemeral Jobs)                                              │
│  Owner: Data Engineers                                                       │
│  K8s Resources: Jobs (run-to-completion)                                    │
│  Config: floe.yaml                                                          │
│                                                                              │
│  • dbt run pods                                                             │
│  • Pipeline job executions                                                  │
│  • Quality check jobs                                                       │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ Connects to
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: SERVICES (Long-lived)                                              │
│  Owner: Platform Engineers                                                   │
│  K8s Resources: Deployments, StatefulSets                                   │
│  Deployment: `floe platform deploy`                                         │
│                                                                              │
│  • Orchestrator services (Dagster/Airflow webserver, daemon, PostgreSQL)   │
│  • Catalog services (Polaris server, PostgreSQL)                           │
│  • Semantic layer (Cube server, Redis cache)                               │
│  • Observability (OTLP Collector, Prometheus, Grafana)                     │
│  • Object storage (MinIO or cloud S3/GCS/ADLS)                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ Configured by
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: CONFIGURATION (Enforcement)                                        │
│  Owner: Platform Engineers                                                   │
│  Storage: OCI Registry (immutable, versioned)                               │
│  Config: manifest.yaml                                             │
│                                                                              │
│  • Plugin selection (compute, orchestrator, catalog, semantic, ingestion)  │
│  • Governance policies (classification, access control, retention)         │
│  • Data architecture rules (naming conventions, layer constraints)         │
│  • Quality gates (test coverage, required tests, block/warn/notify)        │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ Built on
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: FOUNDATION (Framework Code)                                        │
│  Owner: floe Maintainers                                            │
│  Distribution: PyPI, Helm registry                                          │
│                                                                              │
│  • floe-core: Schemas, interfaces, enforcement engine                      │
│  • floe-dbt: dbt integration (enforced)                                    │
│  • floe-iceberg: Iceberg utilities (enforced)                              │
│  • plugins/*: Pluggable implementations                                    │
│  • charts/*: Helm charts for deployment                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer Boundaries

| Aspect | Layer 3 (Services) | Layer 4 (Data) |
|--------|-------------------|----------------|
| **K8s Resource** | Deployment, StatefulSet | Job |
| **Lifecycle** | Long-lived, upgraded | Run-to-completion |
| **State** | Stateful (databases, caches) | Stateless |
| **Scaling** | Fixed replicas or HPA | Per-execution |
| **Owner** | Platform Team | Data Team (execution) |
| **Deployment** | `floe platform deploy` | Triggered by orchestrator |
| **Upgrades** | Rolling updates | New job pods per run |

## Platform Artifacts: OCI Registry Storage

Platform artifacts are stored in OCI-compliant registries. This enables:

- **Immutability**: Once published, artifacts cannot be modified
- **Versioning**: Semantic versioning (v1.2.3) with tags
- **Signing**: Content signing via cosign for supply chain security
- **Enterprise-ready**: All cloud providers offer OCI registries

### Artifact Structure

```
oci://registry.example.com/floe-platform:v1.2.3
├── manifest.json               # Platform metadata
├── policies/                   # Compiled governance policies
│   ├── classification.json     # Data classification rules
│   ├── access-control.json     # RBAC definitions
│   └── quality-gates.json      # Quality requirements
├── catalog/                    # Catalog configuration
│   ├── namespaces.json         # Approved namespaces
│   └── schema-registry.json    # Schema constraints
└── architecture/               # Data architecture rules
    ├── naming-rules.json       # Naming conventions
    └── layer-constraints.json  # Medallion/Kimball rules
```

### Platform Team Workflow

```bash
# 1. Edit platform configuration
vim manifest.yaml

# 2. Validate and build artifacts
floe platform compile

# 3. Run policy tests
floe platform test

# 4. Version control
git commit -m "Update platform v1.2.3" && git push

# 5. Publish to OCI registry
floe platform publish v1.2.3
# Output: oci://registry.example.com/floe-platform:v1.2.3

# 6. Deploy long-lived services to K8s
floe platform deploy
```

### Data Team Workflow

```bash
# 1. Pull platform artifacts
floe init --platform=v1.2.3
# Pulls from oci://registry.example.com/floe-platform:v1.2.3

# 2. Edit pipeline configuration
vim floe.yaml

# 3. Validate against platform constraints
floe compile
# Validates naming, quality gates, etc.

# 4. Execute pipeline
floe run
```

## Why OCI Registry?

| Consideration | OCI Registry | Alternatives |
|---------------|--------------|--------------|
| K8s-native | ✅ ORAS, Helm 3.8+ standard | S3 requires custom tooling |
| Versioning | ✅ Built-in tags + digests | Manual version management |
| Signing | ✅ cosign integration | Varies by provider |
| Enterprise | ✅ ECR, ACR, GCR, Harbor | Additional infra needed |
| Caching | ✅ CDN-backed by registries | Custom CDN setup |

## Data Mesh Extension

For organizations adopting Data Mesh, the two-file model extends to a **three-tier hierarchy**:

```
Enterprise Platform (enterprise-manifest.yaml)
       │ Global governance, approved plugins
       ▼
Domain Platform (domain-manifest.yaml)
       │ Domain-specific choices, domain namespace
       ▼
Data Products (floe.yaml)
       │ Input/output ports, SLAs, contracts
```

Each tier inherits from its parent and can add domain-specific policies. See [ADR-0021: Data Architecture Patterns](0021-data-architecture-patterns.md) for full Data Mesh documentation.

## References

- [04-building-blocks.md](../../guides/04-building-blocks.md) - Four-layer architecture details
- [03-solution-strategy.md](../../guides/03-solution-strategy.md) - Opinionation boundaries
- [ADR-0008](0008-repository-split.md) - Repository structure
- [ORAS (OCI Registry As Storage)](https://oras.land/)
- [Helm OCI Support](https://helm.sh/docs/topics/registries/)
