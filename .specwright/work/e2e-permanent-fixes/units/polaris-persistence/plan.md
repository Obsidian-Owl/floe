# Plan: Polaris PostgreSQL Persistence

## Tasks

### Task 1: Add conditional JDBC properties to configmap template
Modify `charts/floe-platform/templates/configmap-polaris.yaml` to include Quarkus datasource properties when `polaris.persistence.type` is set.

**File change map:**
| File | Change |
|---|---|
| `charts/floe-platform/templates/configmap-polaris.yaml` | Add conditional JDBC block |

**Config example:**
```yaml
{{- if eq (.Values.polaris.persistence.type | default "in-memory") "relational-jdbc" }}
# JDBC persistence
polaris.persistence.type=relational-jdbc
quarkus.datasource.db-kind=postgresql
{{- end }}
```

### Task 2: Configure Polaris JDBC and PostgreSQL PVC in test values
Update `charts/floe-platform/values-test.yaml`:
1. Add `polaris.persistence.type: relational-jdbc`
2. Add `polaris.env` entries for QUARKUS_DATASOURCE_* env vars
3. Set `postgresql.persistence.enabled: true` with PVC size

**File change map:**
| File | Change |
|---|---|
| `charts/floe-platform/values-test.yaml` | Add persistence config, enable PG PVC |

**Config example:**
```yaml
polaris:
  persistence:
    type: relational-jdbc
  env:
    - name: QUARKUS_DATASOURCE_JDBC_URL
      value: "jdbc:postgresql://floe-platform-postgresql:5432/polaris"
    - name: QUARKUS_DATASOURCE_USERNAME
      value: "polaris"
    - name: QUARKUS_DATASOURCE_PASSWORD
      value: "polaris"

postgresql:
  persistence:
    enabled: true
    size: 1Gi
```

### Task 3: Initialize Polaris database in PostgreSQL
Ensure the `polaris` database exists in PostgreSQL before Polaris starts. Options:
- Use PostgreSQL subchart's `initdb` scripts
- Or rely on Quarkus auto-schema-creation (if supported)

**File change map:**
| File | Change |
|---|---|
| `charts/floe-platform/values-test.yaml` | Add PostgreSQL initdb for polaris database |
| `testing/ci/test-e2e.sh` | May need to create database via psql before Helm install (if initdb not sufficient) |
