# 01. Constraints

This document describes the technical and organizational constraints that shape floe's architecture.

---

## 1. Open Source Constraints

### 1.1 No Vendor Lock-In

| Constraint | Rationale |
|------------|-----------|
| No cloud-specific dependencies | Must run on AWS, GCP, Azure, or on-premises |
| No proprietary formats | Use Iceberg, not Delta Lake (Databricks) |
| No proprietary dependencies | 100% open-source stack |
| Standard protocols | OpenTelemetry (not Datadog SDK), OpenLineage (not custom) |

### 1.2 Portability Requirements

| Environment | Support Level |
|-------------|---------------|
| macOS (Apple Silicon) | First-class |
| macOS (Intel) | First-class |
| Linux (x86_64) | First-class |
| Linux (ARM64) | First-class |
| Windows (WSL2) | Supported |
| Windows (native) | Best-effort |

### 1.3 Air-Gapped Support

For enterprise environments without internet access:

- All dependencies must be installable from internal mirrors
- No runtime phone-home or telemetry (opt-in only)
- Container images work without registry access (offline load)
- Documentation available offline

---

## 2. Technical Constraints

### 2.1 Python Ecosystem

| Constraint | Rationale |
|------------|-----------|
| Python 3.10+ required | Dagster and dbt requirements |
| Pure Python packages | No compiled extensions for portability |
| Standard packaging (pyproject.toml) | Modern Python tooling support |
| uv as preferred package manager | Fast, modern Python tooling (pip-compatible) |

### 2.2 Database Compatibility

floe must work with:

| Database | Role | Constraint |
|----------|------|------------|
| DuckDB | Default compute (any scale) | Embedded, no server required |
| PostgreSQL | Metadata storage | Required for Dagster |
| Snowflake | Production warehouse | Via dbt-snowflake adapter |
| BigQuery | Production warehouse | Via dbt-bigquery adapter |
| Redshift | Production warehouse | Via dbt-redshift adapter |
| Databricks | Production warehouse | Via dbt-databricks adapter |

### 2.3 Container Requirements

| Constraint | Value |
|------------|-------|
| Base image | Python 3.11-slim |
| Max image size | < 2GB (all-in-one) |
| Multi-arch | linux/amd64, linux/arm64 |
| Rootless | Support running as non-root |
| Read-only filesystem | Support for security-hardened K8s |

### 2.4 Kubernetes Compatibility

| K8s Version | Support |
|-------------|---------|
| 1.27+ | Full support |
| 1.25-1.26 | Best-effort |
| < 1.25 | Unsupported |

Helm chart constraints:
- Helm 3.10+
- No Helm hooks that require cluster-admin
- Support for restricted PSP/PSA
- Compatible with GitOps (ArgoCD, Flux)

---

## 3. Integration Constraints

### 3.1 dbt Constraints

| Constraint | Value |
|------------|-------|
| dbt-core version | 1.7+ |
| dbt Cloud | Not supported (use dbt-core) |
| Adapter discovery | Via installed packages |
| profiles.yml | Generated, not user-managed |

### 3.2 Dagster Constraints

| Constraint | Value |
|------------|-------|
| Dagster version | 1.6+ |
| Dagster Cloud | Not required (optional integration) |
| Asset factory | Recommended pattern |
| Sensors/Schedules | Via floe.yaml configuration |

### 3.3 Iceberg Constraints

| Constraint | Value |
|------------|-------|
| Iceberg version | 1.4+ |
| Table format version | v2 |
| Catalog type | REST (Polaris), Hive, Glue |
| Storage | S3, GCS, Azure Blob, local filesystem |

### 3.4 Polaris Constraints

| Constraint | Value |
|------------|-------|
| Polaris version | 0.1+ (Apache incubating) |
| Authentication | OAuth2, or none (development) |
| Deployment | Self-hosted or managed |

---

## 4. Organizational Constraints

### 4.1 Development Process

| Constraint | Rationale |
|------------|-----------|
| All changes via PR | Code review required |
| CI must pass | Automated testing gate |
| Documentation required | For all public APIs |
| ADR for architecture changes | Decision traceability |

### 4.2 Release Process

| Constraint | Value |
|------------|-------|
| Semantic versioning | MAJOR.MINOR.PATCH |
| Changelog required | For every release |
| Breaking changes | Major version only |
| Deprecation period | 2 minor versions |

### 4.3 Security Requirements

| Requirement | Implementation |
|-------------|----------------|
| Dependency scanning | Dependabot, Snyk |
| Secret management | Never in code, environment vars or secret refs |
| CVE response | < 7 days for critical |
| Security advisories | GitHub Security Advisories |

---

## 5. Performance Constraints

### 5.1 CLI Performance

| Operation | Target |
|-----------|--------|
| `floe --help` | < 500ms |
| `floe validate` | < 2s |
| `floe compile` | < 5s |
| `floe run` startup | < 10s |

### 5.2 Runtime Performance

| Metric | Target |
|--------|--------|
| Asset materialization overhead | < 1s per asset |
| Lineage event emission | < 100ms |
| Trace span overhead | < 10ms |

---

## 6. Backward Compatibility

### 6.1 floe.yaml Schema

| Version | Support |
|---------|---------|
| Current | Full |
| Current - 1 | Full (with deprecation warnings) |
| Current - 2 | Migration tool available |
| Older | Unsupported |

### 6.2 CompiledArtifacts Contract

| Change Type | Allowed |
|-------------|---------|
| Add optional field | Yes (minor version) |
| Add required field | No (major version only) |
| Remove field | No (major version only) |
| Change field type | No (major version only) |

### 6.3 API Stability

| Package | Stability |
|---------|-----------|
| floe-core | Stable (1.x) |
| floe-cli | Stable (1.x) |
| floe-dbt | Stable (1.x) |
| floe-iceberg | Beta |
| plugins/floe-orchestrator-dagster | Stable (1.x) |
| plugins/floe-catalog-polaris | Beta |
| plugins/floe-semantic-cube | Beta |
| plugins/floe-compute-* | Beta |
