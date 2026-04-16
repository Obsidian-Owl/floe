# Spec: Polaris PostgreSQL Persistence

## Acceptance Criteria

### AC-1: Polaris configured for relational-jdbc in test values
`charts/floe-platform/values-test.yaml` MUST configure Polaris with `relational-jdbc` persistence type, including JDBC env vars pointing to the existing PostgreSQL StatefulSet.

**How to verify:** `values-test.yaml` contains Polaris env vars for QUARKUS_DATASOURCE_* and polaris.persistence.type is set to relational-jdbc.

### AC-2: Configmap includes conditional JDBC properties
`charts/floe-platform/templates/configmap-polaris.yaml` MUST include Quarkus datasource properties ONLY when persistence type is configured as relational-jdbc. The in-memory mode MUST remain unchanged.

**How to verify:** Template has a conditional block gated on `.Values.polaris.persistence.type`. In-memory deployments render the same configmap as before.

### AC-3: PostgreSQL persistence enabled with PVC
`charts/floe-platform/values-test.yaml` MUST set `postgresql.persistence.enabled: true` with a PVC size. Without this, PostgreSQL uses emptyDir and Polaris JDBC persistence gives no benefit on PostgreSQL restart.

**How to verify:** `postgresql.persistence.enabled` is `true` and `postgresql.persistence.size` is set.

### AC-4: JDBC credentials managed via K8s secret or values
JDBC credentials (username, password, URL) MUST be provided via values env vars referencing the existing PostgreSQL credentials, not hardcoded in the configmap.

**How to verify:** Credentials are injected via `polaris.env` values referencing K8s secrets or using the PostgreSQL subchart's credential mechanism.

### AC-5: Bootstrap Job remains functional
The existing Polaris bootstrap Job MUST continue to work with relational-jdbc persistence. It creates catalogs and grants idempotently.

**How to verify:** `helm template` with the new values produces a valid bootstrap Job spec. The Job's wait-for-ready loop still targets `/q/health/ready`.

### AC-6: In-memory mode backward-compatible
Deployments that do NOT set `polaris.persistence.type` MUST continue to use in-memory persistence with no behavior change.

**How to verify:** `helm template` with the existing values (no persistence block) produces the same configmap and deployment as before the change.
