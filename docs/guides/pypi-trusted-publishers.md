# PyPI Token Publisher Setup

This file currently documents the implemented PyPI token setup and alpha package
registration cutline. Trusted publishing/OIDC migration is future work; the
current `pypi-publish.yml` workflow uploads with `secrets.PYPI_API_TOKEN`.

## Prerequisites

- PyPI account with Owner/Maintainer role on the Obsidian Owl organisation
- GitHub environment `pypi` created on `Obsidian-Owl/floe` (Settings > Environments)
- Account-scoped PyPI API token stored as `PYPI_API_TOKEN` in the `pypi`
  environment

## Steps (per package)

1. Confirm the PyPI project is owned by the Obsidian Owl organisation or can be
   created by the first alpha upload.
2. Confirm the `pypi` GitHub environment has a `PYPI_API_TOKEN` secret that can
   publish the package.
3. Record the package in the checklist below.

## Alpha Publish Checklist

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
`release/floe-release.yaml` and must not be registered or published for alpha
until their composition path is proven.

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

## GitHub environment fields

```
Environment:        pypi
Secret name:        PYPI_API_TOKEN
Workflow file:      pypi-publish.yml
Publishing package: pypa/gh-action-pypi-publish
```

## After all packages are registered

1. Verify all 15 alpha packages are covered by the PyPI account token and
   project ownership.
2. A successful non-dry-run `prepare-release.yml` run uploads release metadata.
3. The downstream `pypi-publish.yml` workflow builds only the manifest package
   set and uploads artifacts with `PYPI_API_TOKEN`.

If the GitHub Release already exists and the downstream publish workflow needs
to be retried after a workflow fix, dispatch `pypi-publish.yml` manually with:

```bash
gh workflow run pypi-publish.yml \
  -f release_tag=v0.1.0-alpha.1 \
  -f dry_run=false
```

Manual publishing must always provide an existing `release_tag`; manual runs
default to `dry_run=true`.

## Metadata

Package metadata is read from each package's `pyproject.toml`; the alpha release
version comes from `release/floe-release.yaml`.

| Field | Value |
|-------|-------|
| Author | Obsidian Owl |
| Email | team@obsidianowl.dev |
| License | Apache-2.0 |
| Python | >=3.10 |
| Homepage | https://github.com/Obsidian-Owl/floe |
| Repository | https://github.com/Obsidian-Owl/floe |
| Version | 0.1.0a1 |
