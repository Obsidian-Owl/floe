# Context: Polaris PostgreSQL Persistence

baselineCommit: f1f1e25c00fe64845da9166b06c9b4654670bd8d

## Problem
Polaris uses in-memory storage. Pod restart = total state loss. Bootstrap Job only fires on Helm install/upgrade, not pod restart. 73+ minute test suites make Polaris restarts likely.

## Key Files
- `charts/floe-platform/values-test.yaml:129-169` — Polaris config (no persistence block)
- `charts/floe-platform/values-test.yaml:201-204` — PostgreSQL config (`persistence.enabled: false`)
- `charts/floe-platform/templates/configmap-polaris.yaml` — Quarkus application.properties
- `charts/floe-platform/templates/deployment-polaris.yaml:96-98` — `{{- with .Values.polaris.env }}` escape hatch

## Technical Facts
- Polaris 1.2.0-incubating supports `relational-jdbc` persistence via Quarkus datasource
- PostgreSQL StatefulSet (`floe-platform-postgresql`) is already deployed
- Deployment template has `.Values.polaris.env` for injecting custom env vars
- Configmap template renders `application.properties` from values
- Quarkus JDBC properties: `QUARKUS_DATASOURCE_USERNAME`, `QUARKUS_DATASOURCE_PASSWORD`, `QUARKUS_DATASOURCE_JDBC_URL`, `QUARKUS_DATASOURCE_DB_KIND=postgresql`
- Polaris persistence type property: `polaris.persistence.type=relational-jdbc`
- PostgreSQL `persistence.enabled: false` means emptyDir — PostgreSQL pod restart also loses data
- Must enable PostgreSQL PVC persistence for the chain to be durable

## Gotchas
- P55: Helm `--atomic` for test upgrades
- Configmap change affects all chart consumers — use conditional block
- Quarkus may auto-create schema on first boot (hibernate-orm generation)
- Bootstrap Job is idempotent — safe to run after JDBC migration
