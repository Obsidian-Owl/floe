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

## Pending Publisher Checklist

Register only the packages in `python_packages.publish` from
`release/floe-release.yaml` for the alpha release.

- [x] `floe-core` — Core plugin registry and interfaces for the Floe data platform
- [x] `floe-iceberg` — IcebergTableManager utility for PyIceberg table operations
- [ ] `floe-orchestrator-dagster` — Dagster orchestrator plugin
- [ ] `floe-catalog-polaris` — Apache Polaris catalog plugin
- [ ] `floe-storage-minio` — MinIO object storage plugin
- [ ] `floe-compute-duckdb` — DuckDB compute plugin
- [ ] `floe-dbt-core` — DBT plugin using dbt-core Python API
- [ ] `floe-ingestion-dlt` — dlt ingestion plugin
- [ ] `floe-telemetry-jaeger` — Jaeger telemetry backend plugin (OTLP exporter)
- [ ] `floe-rbac-k8s` — Kubernetes RBAC plugin
- [ ] `floe-network-security-k8s` — Kubernetes Network Security plugin
- [ ] `floe-lineage-marquez` — Marquez lineage backend plugin (OpenLineage)
- [ ] `floe-quality-gx` — Great Expectations data quality plugin
- [ ] `floe-storage-aws-s3` — AWS S3 storage plugin
- [ ] `floe-catalog-glue` — AWS Glue catalog plugin

## Excluded from alpha

These packages are listed under `python_packages.exclude` in
`release/floe-release.yaml` and must not be registered as alpha pending
publishers until their composition path is proven.

- `floe-alert-slack`
- `floe-alert-email`
- `floe-alert-alertmanager`
- `floe-alert-webhook`
- `floe-identity-keycloak`
- `floe-secrets-infisical`
- `floe-secrets-k8s`
- `floe-semantic-cube`
- `floe-dbt-fusion`
- `floe-telemetry-console`
- `floe-quality-dbt`

## Common fields (copy-paste reference)

```
Owner:           Obsidian-Owl
Repository name: floe
Workflow name:   pypi-publish.yml
Environment:     pypi
```

## After all packages are registered

1. Verify all 15 alpha pending publishers appear at <https://pypi.org/manage/account/publishing/>
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
