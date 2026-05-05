# PyPI Trusted Publisher Setup

Register each Floe package as a **pending publisher** so the first GitHub Actions
upload auto-creates the PyPI project. No API tokens are needed — authentication
uses short-lived OIDC tokens.

## Prerequisites

- PyPI account with Owner/Maintainer role on the Obsidian Owl organisation
- GitHub environment `pypi` created on `Obsidian-Owl/floe` (Settings > Environments)

## Steps (per package)

1. Go to <https://pypi.org/manage/account/publishing/>
2. Under **"Add a new pending publisher"**, fill in:

   | Field | Value |
   |-------|-------|
   | PyPI project name | *(see table below)* |
   | Owner | `Obsidian-Owl` |
   | Repository name | `floe` |
   | Workflow name | `pypi-publish.yml` |
   | Environment name | `pypi` |

3. Click **"Add"**
4. Tick the package off in the checklist below

## Package Checklist

### Core packages (2)

- [x] `floe-core` — Core plugin registry and interfaces for the floe data platform
- [x] `floe-iceberg` — IcebergTableManager utility for PyIceberg table operations

### Alert plugins (4)

- [ ] `floe-alert-alertmanager` — Alertmanager alert channel plugin
- [ ] `floe-alert-email` — Email alert channel plugin
- [ ] `floe-alert-slack` — Slack alert channel plugin
- [ ] `floe-alert-webhook` — Webhook alert channel plugin

### Catalog plugins (1)

- [ ] `floe-catalog-polaris` — Apache Polaris catalog plugin

### Compute plugins (1)

- [ ] `floe-compute-duckdb` — DuckDB compute plugin

### dbt plugins (2)

- [ ] `floe-dbt-core` — DBT plugin using dbt-core Python API
- [ ] `floe-dbt-fusion` — DBT plugin using dbt Fusion CLI

### Identity plugins (1)

- [ ] `floe-identity-keycloak` — Keycloak OIDC identity provider plugin

### Ingestion plugins (1)

- [ ] `floe-ingestion-dlt` — dlt ingestion plugin

### Lineage plugins (1)

- [ ] `floe-lineage-marquez` — Marquez lineage backend plugin (OpenLineage)

### Network security plugins (1)

- [ ] `floe-network-security-k8s` — Kubernetes Network Security plugin

### Orchestrator plugins (1)

- [ ] `floe-orchestrator-dagster` — Dagster orchestrator plugin

### Quality plugins (2)

- [ ] `floe-quality-dbt` — dbt-expectations data quality plugin
- [ ] `floe-quality-gx` — Great Expectations data quality plugin

### RBAC plugins (1)

- [ ] `floe-rbac-k8s` — Kubernetes RBAC plugin

### Secrets plugins (2)

- [ ] `floe-secrets-infisical` — Infisical OSS secrets backend plugin
- [ ] `floe-secrets-k8s` — Kubernetes Secrets backend plugin

### Semantic layer plugins (1)

- [ ] `floe-semantic-cube` — Cube semantic layer plugin

### Storage plugins (1)

- [ ] `floe-storage-s3` — S3-compatible object storage plugin

### Telemetry plugins (2)

- [ ] `floe-telemetry-console` — Console telemetry backend plugin
- [ ] `floe-telemetry-jaeger` — Jaeger telemetry backend plugin (OTLP exporter)

## Common fields (copy-paste reference)

```
Owner:           Obsidian-Owl
Repository name: floe
Workflow name:   pypi-publish.yml
Environment:     pypi
```

## After all packages are registered

1. Verify all 24 pending publishers appear at <https://pypi.org/manage/account/publishing/>
2. The `pypi-publish.yml` workflow (triggered by version tags) will handle building,
   uploading, and converting each pending publisher into a full trusted publisher
   on first successful publish.

## Metadata (already in pyproject.toml)

All packages share this metadata — no need to enter it in PyPI manually:

| Field | Value |
|-------|-------|
| Author | Obsidian Owl |
| Email | team@obsidianowl.dev |
| License | Apache-2.0 |
| Python | >=3.10 |
| Homepage | https://github.com/Obsidian-Owl/floe |
| Repository | https://github.com/Obsidian-Owl/floe |
| Version | 0.1.0 (alpha) |
